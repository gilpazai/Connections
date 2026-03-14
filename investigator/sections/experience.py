from __future__ import annotations

import asyncio
import logging

from investigator.llm.prompts import EXPERIENCE_SYSTEM, make_linkedin_user_prompt
from investigator.sections.base import BaseSection, SectionResult
from src.data.linkedin_scraper import scrape_linkedin_experience

logger = logging.getLogger(__name__)


class ExperienceSection(BaseSection):
    def section_name(self) -> str:
        return "Work Experience"

    def generate_queries(self) -> list[str]:
        # We don't really rely on these queries, but it's part of the interface
        company = self._config.company or ""
        return [f"{self._config.name} {company} linkedin".strip()]

    def get_system_prompt(self) -> str:
        return EXPERIENCE_SYSTEM

    def get_user_prompt(self, text: str) -> str:
        return make_linkedin_user_prompt(self._config.name, self._config.company, text)

    async def execute(self) -> SectionResult:
        name = self.section_name()
        errors: list[str] = []

        # 1. Find LinkedIn URL (using DDGS via search engine)
        q = f'site:linkedin.com/in "{self._config.name}"'
        if self._config.company:
            q += f' "{self._config.company}"'

        logger.info("[%s] Searching for LinkedIn profile...", name)
        try:
            results = await self._search.search(q, max_results=3)
        except Exception as exc:
            errors.append(f"Search error: {exc}")
            results = []

        linkedin_url = None
        for r in results:
            if "linkedin.com/in/" in r.url:
                linkedin_url = r.url
                break

        if not linkedin_url:
            return SectionResult(
                section_name=name,
                markdown="*No LinkedIn profile found to scrape work experience from.*",
                errors=errors + ["No LinkedIn profile found"],
            )

        # 2. Scrape Experience using Chrome Scraper
        logger.info("[%s] Scraping experience from %s", name, linkedin_url)
        try:
            page_text = await asyncio.to_thread(
                scrape_linkedin_experience, linkedin_url, timeout_secs=30
            )
        except Exception as exc:
            errors.append(f"Scraper error: {exc}")
            page_text = ""

        if not page_text or len(page_text.strip()) < 50:
            return SectionResult(
                section_name=name,
                markdown="*Failed to extract meaningful work experience.*",
                errors=errors,
                query_count=1,
            )

        # Limit text length
        page_text = page_text[: self._config.llm_max_context_chars]

        # 3. LLM synthesis
        logger.info("[%s] Synthesizing experience with LLM...", name)
        try:
            markdown = await self._llm.generate(
                self.get_system_prompt(),
                self.get_user_prompt(page_text),
            )
        except Exception as exc:
            errors.append(f"LLM synthesis failed: {exc}")
            markdown = "*Data collected but LLM synthesis failed.*"

        return SectionResult(
            section_name=name,
            markdown=markdown,
            sources=[linkedin_url.strip().rstrip("/") + "/details/experience/"],
            errors=errors,
            query_count=1,
        )
