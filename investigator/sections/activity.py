from __future__ import annotations

from investigator.llm.prompts import ACTIVITY_SYSTEM, make_activity_user_prompt
from investigator.search.queries import QueryGenerator
from investigator.sections.base import BaseSection, SectionResult
from src.data.linkedin_scraper import scrape_linkedin_activity
import asyncio


class ActivitySection(BaseSection):
    def section_name(self) -> str:
        return "Recent Activity"

    def generate_queries(self) -> list[str]:
        qg = QueryGenerator(self._config.name, self._config.company)
        return qg.activity_queries()

    def get_system_prompt(self) -> str:
        return ACTIVITY_SYSTEM

    def get_user_prompt(self, text: str) -> str:
        return make_activity_user_prompt(self._config.name, self._config.company, text)

    async def execute(self) -> SectionResult:
        name = self.section_name()
        errors: list[str] = []
        
        # 1. Find LinkedIn URL
        q = f'site:linkedin.com/in "{self._config.name}"'
        if self._config.company:
            q += f' "{self._config.company}"'
            
        import logging
        logger = logging.getLogger(__name__)
        logger.info("[%s] Searching for LinkedIn profile...", name)
        
        # We need to manually search since generating queries doesn't get this explicit DDGS result
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
                markdown="*No LinkedIn profile found to scrape activity from.*",
                errors=errors + ["No LinkedIn profile found"],
            )

        # 2. Scrape activity using Chrome
        logger.info("[%s] Scraping activity from %s", name, linkedin_url)
        try:
            posts_text = await asyncio.to_thread(scrape_linkedin_activity, linkedin_url, "shares")
            comments_text = await asyncio.to_thread(scrape_linkedin_activity, linkedin_url, "comments")
            page_text = f"=== PUBLIC POSTS ===\n{posts_text}\n\n=== PUBLIC COMMENTS ===\n{comments_text}"
        except Exception as exc:
            errors.append(f"Scraper error: {exc}")
            page_text = ""
            
        if not page_text or len(page_text.strip()) < 50:
            return SectionResult(
                section_name=name,
                markdown="*Failed to extract meaningful recent activity.*",
                errors=errors,
                query_count=1,
            )

        # Limit text length just in case it's huge
        page_text = page_text[:self._config.llm_max_context_chars]

        # 3. LLM synthesis
        logger.info("[%s] Synthesizing activity with LLM...", name)
        try:
            markdown = await self._llm.generate(
                self.get_system_prompt(),
                self.get_user_prompt(page_text),
            )
        except Exception as exc:
            errors.append(f"LLM synthesis failed: {exc}")
            markdown = "*Data collected but LLM synthesis failed.*"

        # Final Activity Section 
        return SectionResult(
            section_name=name,
            markdown=markdown,
            sources=[linkedin_url.strip().rstrip("/") + "/recent-activity/all/"],
            errors=errors,
            query_count=1,
        )
