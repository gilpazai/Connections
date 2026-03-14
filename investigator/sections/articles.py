from __future__ import annotations

import logging
from typing import TypedDict

from investigator.llm.prompts import ARTICLES_SYSTEM
from investigator.sections.base import BaseSection, SectionResult

logger = logging.getLogger(__name__)


class ArticleData(TypedDict):
    title: str
    url: str
    text: str


class ArticlesSection(BaseSection):
    def section_name(self) -> str:
        return "News & Articles"

    def generate_queries(self) -> list[str]:
        # Generating queries specifically tuned for DDGS News or Web
        # It's better to cast a tight net using quotes.
        company = self._config.company or ""
        return [f'"{self._config.name}" "{company}"']

    def get_system_prompt(self) -> str:
        return ARTICLES_SYSTEM

    def get_user_prompt(self, text: str) -> str:
        # text will be the JSON-ish formatted string of multiple articles
        return f"Synthesize this into a report section as instructed.\n\n=== ARTICLES SOURCE MATERIAL ===\n{text}\n=== END ARTICLES SOURCE MATERIAL ==="

    async def execute(self) -> SectionResult:
        name = self.section_name()
        errors: list[str] = []
        sources: list[str] = []

        queries = self.generate_queries()
        if not queries:
            return SectionResult(
                section_name=name, markdown="*Insufficient data to query for articles.*", errors=[]
            )

        query = queries[0]
        logger.info("[%s] Searching for news/articles for: %s", name, query)

        try:
            # We use search_news to target articles specifically
            results = await self._search.search_news(query, max_results=5)
            # If news yields nothing, fallback to regular web search
            if not results:
                logger.info("[%s] No news found, falling back to web search...", name)
                results = await self._search.search(query, max_results=5)
        except Exception as exc:
            errors.append(f"Search error: {exc}")
            results = []

        if not results:
            return SectionResult(
                section_name=name,
                markdown="*No articles found for the target.*",
                errors=errors,
            )

        # Fetch the content of the URLs we found
        found_articles: list[ArticleData] = []
        
        # Limit to top 5 articles max just to be safe with context windows and speed
        articles_to_fetch = results[:5] if results else []
        urls_to_fetch = [r.url for r in articles_to_fetch if r.url]
        
        html_map = await self._fetcher.fetch_many(urls_to_fetch)
        extracted_pages = await self._extractor.extract_many(html_map)

        for page in extracted_pages:
            if page.url not in sources:
                sources.append(page.url)
            found_articles.append({
                "title": page.title or "Untitled",
                "url": page.url,
                "text": page.text[:self._config.llm_max_context_chars // len(results)] # Distribute token budget
            })

        if not found_articles:
            return SectionResult(
                section_name=name,
                markdown="*Articles found in search, but failed to fetch or parse content.*",
                errors=errors,
                query_count=1,
            )

        # Build a structured text string for the LLM
        combined_text = ""
        for i, art in enumerate(found_articles):
            combined_text += f"\n--- ARTICLE {i+1} ---\nTITLE: {art['title']}\nURL: {art['url']}\nCONTENT:\n{art['text']}\n"

        logger.info("[%s] Synthesizing %d articles with LLM...", name, len(found_articles))
        try:
            markdown = await self._llm.generate(
                self.get_system_prompt(),
                self.get_user_prompt(combined_text)
            )
        except Exception as exc:
            errors.append(f"LLM synthesis failed: {exc}")
            markdown = "*Data collected but LLM synthesis failed.*"

        return SectionResult(
            section_name=name,
            markdown=markdown,
            sources=list(sources),
            errors=errors,
            query_count=1,
        )
