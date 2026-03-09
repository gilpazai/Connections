from __future__ import annotations

from investigator.extraction.extractor import ExtractedPage


class TextChunker:
    """Splits extracted pages into chunks that fit in the LLM context window."""

    def __init__(self, max_chars: int) -> None:
        self._max = max_chars

    def prepare(self, pages: list[ExtractedPage]) -> list[str]:
        """Return a list of text chunks.

        If all pages fit in one chunk, returns a single-element list.
        Otherwise splits into multiple chunks for map-reduce processing.
        """
        if not pages:
            return []

        combined = self._combine(pages)
        if len(combined) <= self._max:
            return [combined]

        # Split into chunks that each fit the limit
        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for page in pages:
            entry = self._format_page(page)
            if current_len + len(entry) > self._max and current:
                chunks.append("\n\n---\n\n".join(current))
                current = []
                current_len = 0
            current.append(entry)
            current_len += len(entry)

        if current:
            chunks.append("\n\n---\n\n".join(current))

        return chunks

    def _combine(self, pages: list[ExtractedPage]) -> str:
        return "\n\n---\n\n".join(self._format_page(p) for p in pages)

    @staticmethod
    def _format_page(page: ExtractedPage) -> str:
        header_parts = []
        if page.title:
            header_parts.append(f"Title: {page.title}")
        header_parts.append(f"URL: {page.url}")
        if page.date:
            header_parts.append(f"Date: {page.date}")
        header = " | ".join(header_parts)
        return f"[{header}]\n{page.text}"
