from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import trafilatura

logger = logging.getLogger(__name__)


@dataclass
class ExtractedPage:
    url: str
    title: str | None
    text: str
    date: str | None
    word_count: int


class TextExtractor:
    """Extracts clean article text from HTML via trafilatura."""

    MIN_TEXT_LENGTH = 100

    async def extract_many(
        self, url_html_map: dict[str, str | None]
    ) -> list[ExtractedPage]:
        tasks = []
        for url, html in url_html_map.items():
            if html is not None:
                tasks.append(self._extract_one(url, html))

        results = await asyncio.gather(*tasks)
        return [r for r in results if r is not None]

    async def _extract_one(self, url: str, html: str) -> ExtractedPage | None:
        try:
            result = await asyncio.to_thread(self._do_extract, html)
            if result is None:
                return None

            text, metadata = result
            if len(text) < self.MIN_TEXT_LENGTH:
                logger.debug("Text too short (%d chars) for %s", len(text), url)
                return None

            return ExtractedPage(
                url=url,
                title=metadata.get("title"),
                text=text,
                date=metadata.get("date"),
                word_count=len(text.split()),
            )
        except Exception as exc:
            logger.debug("Extraction error for %s: %s", url, exc)
            return None

    @staticmethod
    def _do_extract(html: str) -> tuple[str, dict] | None:
        # bare_extraction returns a dict with text + metadata in one call
        bare = trafilatura.bare_extraction(html, include_tables=True, favor_recall=True)
        if bare is None:
            return None

        text = bare.get("text", "")
        if not text:
            return None

        meta_dict = {
            "title": bare.get("title", ""),
            "date": bare.get("date", ""),
            "author": bare.get("author", ""),
        }
        return text, meta_dict
