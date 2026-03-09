from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field

from investigator.config import InvestigatorConfig
from investigator.extraction.dedup import Deduplicator
from investigator.extraction.extractor import ExtractedPage, TextExtractor
from investigator.extraction.fetcher import PageFetcher
from investigator.llm.chunker import TextChunker
from investigator.llm.client import LLMClient
from investigator.llm.prompts import (
    EXTRACT_FACTS_SYSTEM,
    make_extract_facts_prompt,
)
from investigator.search.engine import SearchEngine, SearchRateLimitError
from investigator.search.queries import SearchResult

logger = logging.getLogger(__name__)


@dataclass
class SectionResult:
    section_name: str
    markdown: str
    sources: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    query_count: int = 0
    pages_fetched: int = 0
    pages_after_dedup: int = 0


class BaseSection(ABC):
    """Template method implementing the shared search→extract→synthesize pipeline."""

    def __init__(
        self,
        config: InvestigatorConfig,
        search_engine: SearchEngine,
        fetcher: PageFetcher,
        extractor: TextExtractor,
        deduplicator: Deduplicator,
        llm: LLMClient,
        chunker: TextChunker,
    ) -> None:
        self._config = config
        self._search = search_engine
        self._fetcher = fetcher
        self._extractor = extractor
        self._dedup = deduplicator
        self._llm = llm
        self._chunker = chunker

    @abstractmethod
    def section_name(self) -> str: ...

    @abstractmethod
    def generate_queries(self) -> list[str]: ...

    @abstractmethod
    def get_system_prompt(self) -> str: ...

    @abstractmethod
    def get_user_prompt(self, text: str) -> str: ...

    async def execute(self) -> SectionResult:
        name = self.section_name()
        errors: list[str] = []

        # 1. Search
        logger.info("[%s] Searching...", name)
        queries = self.generate_queries()
        all_results: list[SearchResult] = []
        for q in queries:
            try:
                results = await self._search.search(q)
                all_results.extend(results)
            except SearchRateLimitError:
                errors.append(f"Rate limited: {q}")
            except Exception as exc:
                errors.append(f"Search error: {exc}")

        if not all_results:
            logger.info("[%s] No search results found.", name)
            return SectionResult(
                section_name=name,
                markdown="*No public information found for this section.*",
                errors=errors,
                query_count=len(queries),
            )

        # 2. Deduplicate URLs
        urls = [r.url for r in all_results if r.url]
        unique_urls = self._dedup.deduplicate_urls(urls)
        urls_to_fetch = unique_urls[: self._config.max_urls_per_section]

        # 3. Fetch pages
        logger.info("[%s] Fetching %d pages...", name, len(urls_to_fetch))
        html_map = await self._fetcher.fetch_many(urls_to_fetch)
        fetched_count = sum(1 for v in html_map.values() if v is not None)

        # 4. Extract text
        pages = await self._extractor.extract_many(html_map)

        # 5. Content dedup
        pages = self._dedup.deduplicate_content(pages)

        if not pages:
            # Fall back to using search snippets
            snippet_text = self._format_snippets(all_results)
            logger.info("[%s] No extractable pages, using search snippets.", name)
            return await self._synthesize(
                name, snippet_text, all_results, errors, len(queries), fetched_count, 0
            )

        # 6. Chunk + LLM
        logger.info("[%s] Synthesizing with LLM (%d pages)...", name, len(pages))
        chunks = self._chunker.prepare(pages)
        sources = [p.url for p in pages]

        return await self._synthesize_from_chunks(
            name, chunks, sources, errors, len(queries), fetched_count, len(pages)
        )

    async def _synthesize_from_chunks(
        self,
        name: str,
        chunks: list[str],
        sources: list[str],
        errors: list[str],
        query_count: int,
        fetched: int,
        deduped: int,
    ) -> SectionResult:
        try:
            if len(chunks) == 1:
                text = chunks[0]
            else:
                # Map-reduce: extract facts from each chunk, then combine
                intermediates = []
                for chunk in chunks:
                    facts = await self._llm.generate(
                        EXTRACT_FACTS_SYSTEM,
                        make_extract_facts_prompt(self._config.name, chunk),
                    )
                    intermediates.append(facts)
                text = "\n\n".join(intermediates)

            markdown = await self._llm.generate(
                self.get_system_prompt(),
                self.get_user_prompt(text),
            )
        except Exception as exc:
            errors.append(f"LLM synthesis failed: {exc}")
            markdown = "*Data was collected but LLM synthesis failed.*"

        return SectionResult(
            section_name=name,
            markdown=markdown,
            sources=sources,
            errors=errors,
            query_count=query_count,
            pages_fetched=fetched,
            pages_after_dedup=deduped,
        )

    async def _synthesize(
        self,
        name: str,
        text: str,
        results: list[SearchResult],
        errors: list[str],
        query_count: int,
        fetched: int,
        deduped: int,
    ) -> SectionResult:
        sources = list({r.url for r in results if r.url})
        try:
            markdown = await self._llm.generate(
                self.get_system_prompt(),
                self.get_user_prompt(text),
            )
        except Exception as exc:
            errors.append(f"LLM synthesis failed: {exc}")
            markdown = "*Data was collected but LLM synthesis failed.*"

        return SectionResult(
            section_name=name,
            markdown=markdown,
            sources=sources,
            errors=errors,
            query_count=query_count,
            pages_fetched=fetched,
            pages_after_dedup=deduped,
        )

    @staticmethod
    def _format_snippets(results: list[SearchResult]) -> str:
        lines: list[str] = []
        seen: set[str] = set()
        for r in results:
            if r.url in seen:
                continue
            seen.add(r.url)
            lines.append(f"Title: {r.title}\nURL: {r.url}\nSnippet: {r.snippet}\n")
        return "\n---\n".join(lines)
