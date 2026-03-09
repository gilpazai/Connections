from __future__ import annotations

import logging

from investigator.llm.prompts import NEWS_SYSTEM, make_user_prompt
from investigator.search.engine import SearchRateLimitError
from investigator.search.queries import QueryGenerator, SearchResult
from investigator.sections.base import BaseSection, SectionResult

logger = logging.getLogger(__name__)


class NewsSection(BaseSection):
    """News section — combines DDGS.text() and DDGS.news() results."""

    def section_name(self) -> str:
        return "News & Public Claims"

    def generate_queries(self) -> list[str]:
        qg = QueryGenerator(self._config.name, self._config.company)
        return qg.news_queries()

    def get_system_prompt(self) -> str:
        return NEWS_SYSTEM

    def get_user_prompt(self, text: str) -> str:
        return make_user_prompt(self._config.name, self._config.company, text)

    async def execute(self) -> SectionResult:
        """Override: also run DDGS.news() alongside standard text search."""
        name = self.section_name()
        errors: list[str] = []

        # Standard text search queries
        queries = self.generate_queries()
        all_results: list[SearchResult] = []

        logger.info("[%s] Searching (text + news)...", name)
        for q in queries:
            try:
                results = await self._search.search(q)
                all_results.extend(results)
            except SearchRateLimitError:
                errors.append(f"Rate limited: {q}")
            except Exception as exc:
                errors.append(f"Search error: {exc}")

        # News-specific queries via DDGS.news()
        qg = QueryGenerator(self._config.name, self._config.company)
        for q in qg.news_headline_queries():
            try:
                results = await self._search.search_news(q)
                all_results.extend(results)
            except SearchRateLimitError:
                errors.append(f"Rate limited (news): {q}")
            except Exception as exc:
                errors.append(f"News search error: {exc}")

        if not all_results:
            return SectionResult(
                section_name=name,
                markdown="*No news coverage found.*",
                errors=errors,
                query_count=len(queries) + len(qg.news_headline_queries()),
            )

        # Deduplicate URLs and fetch
        urls = [r.url for r in all_results if r.url]
        unique_urls = self._dedup.deduplicate_urls(urls)
        urls_to_fetch = unique_urls[: self._config.max_urls_per_section]

        logger.info("[%s] Fetching %d pages...", name, len(urls_to_fetch))
        html_map = await self._fetcher.fetch_many(urls_to_fetch)
        fetched_count = sum(1 for v in html_map.values() if v is not None)

        pages = await self._extractor.extract_many(html_map)
        pages = self._dedup.deduplicate_content(pages)

        total_queries = len(queries) + len(qg.news_headline_queries())

        if not pages:
            # Fall back to snippets
            snippet_text = self._format_snippets(all_results)
            return await self._synthesize(
                name, snippet_text, all_results, errors,
                total_queries, fetched_count, 0,
            )

        logger.info("[%s] Synthesizing with LLM (%d pages)...", name, len(pages))
        chunks = self._chunker.prepare(pages)
        sources = [p.url for p in pages]

        return await self._synthesize_from_chunks(
            name, chunks, sources, errors, total_queries, fetched_count, len(pages),
        )
