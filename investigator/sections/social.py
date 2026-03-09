from __future__ import annotations

import logging

from investigator.llm.prompts import SOCIAL_SYSTEM, make_social_user_prompt
from investigator.search.engine import SearchRateLimitError
from investigator.search.queries import QueryGenerator, SearchResult
from investigator.sections.base import BaseSection, SectionResult

logger = logging.getLogger(__name__)


class SocialSection(BaseSection):
    """Social footprint section — works from search snippets, not full pages.

    Social media sites are JS-rendered SPAs that trafilatura can't extract.
    We use the DDGS search result titles, URLs, and snippets directly.
    """

    def section_name(self) -> str:
        return "Social Footprint"

    def generate_queries(self) -> list[str]:
        qg = QueryGenerator(self._config.name, self._config.company)
        return qg.social_queries()

    def get_system_prompt(self) -> str:
        return SOCIAL_SYSTEM

    def get_user_prompt(self, text: str) -> str:
        return make_social_user_prompt(
            self._config.name, self._config.company, text
        )

    async def execute(self) -> SectionResult:
        """Override: skip fetch/extract, use snippets directly."""
        name = self.section_name()
        errors: list[str] = []

        logger.info("[%s] Searching social platforms...", name)
        queries = self.generate_queries()
        all_results: list[SearchResult] = []
        for q in queries:
            try:
                results = await self._search.search(q, max_results=5)
                all_results.extend(results)
            except SearchRateLimitError:
                errors.append(f"Rate limited: {q}")
            except Exception as exc:
                errors.append(f"Search error: {exc}")

        if not all_results:
            return SectionResult(
                section_name=name,
                markdown="*No social media presence found.*",
                errors=errors,
                query_count=len(queries),
            )

        snippet_text = self._format_snippets(all_results)
        sources = list({r.url for r in all_results if r.url})

        logger.info("[%s] Synthesizing from %d search results...", name, len(all_results))
        try:
            markdown = await self._llm.generate(
                self.get_system_prompt(),
                self.get_user_prompt(snippet_text),
            )
        except Exception as exc:
            errors.append(f"LLM synthesis failed: {exc}")
            markdown = "*Data was collected but LLM synthesis failed.*"

        return SectionResult(
            section_name=name,
            markdown=markdown,
            sources=sources,
            errors=errors,
            query_count=len(queries),
            pages_fetched=0,
            pages_after_dedup=0,
        )
