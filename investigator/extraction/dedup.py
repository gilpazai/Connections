from __future__ import annotations

import re
from urllib.parse import urlparse, parse_qs, urlencode, urlunparse

from investigator.extraction.extractor import ExtractedPage

# Tracking params to strip from URLs
_TRACKING_PARAMS = {
    "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
    "fbclid", "gclid", "ref", "source", "mc_cid", "mc_eid",
}


class Deduplicator:
    """URL-level and content-level deduplication."""

    def __init__(self) -> None:
        self._seen_urls: set[str] = set()

    def deduplicate_urls(self, urls: list[str]) -> list[str]:
        unique: list[str] = []
        for url in urls:
            norm = self.normalize_url(url)
            if norm and norm not in self._seen_urls:
                self._seen_urls.add(norm)
                unique.append(url)
        return unique

    def deduplicate_content(
        self, pages: list[ExtractedPage]
    ) -> list[ExtractedPage]:
        if len(pages) <= 1:
            return pages

        kept: list[ExtractedPage] = []
        fingerprints: list[set[str]] = []

        for page in sorted(pages, key=lambda p: -p.word_count):
            fp = self._trigram_set(page.text)
            is_dup = False
            for existing_fp in fingerprints:
                if self._jaccard(fp, existing_fp) > 0.70:
                    is_dup = True
                    break
            if not is_dup:
                kept.append(page)
                fingerprints.append(fp)

        return kept

    @staticmethod
    def normalize_url(url: str) -> str:
        try:
            parsed = urlparse(url)
            # Strip fragments
            # Strip tracking params
            params = parse_qs(parsed.query, keep_blank_values=False)
            cleaned = {
                k: v for k, v in params.items() if k.lower() not in _TRACKING_PARAMS
            }
            new_query = urlencode(cleaned, doseq=True)
            normalized = urlunparse((
                parsed.scheme.lower(),
                parsed.netloc.lower().rstrip("."),
                parsed.path.rstrip("/"),
                parsed.params,
                new_query,
                "",  # no fragment
            ))
            return normalized
        except Exception:
            return url

    @staticmethod
    def _trigram_set(text: str) -> set[str]:
        words = re.findall(r"\w+", text.lower())
        if len(words) < 3:
            return set(words)
        return {
            f"{words[i]} {words[i+1]} {words[i+2]}"
            for i in range(len(words) - 2)
        }

    @staticmethod
    def _jaccard(a: set[str], b: set[str]) -> float:
        if not a or not b:
            return 0.0
        intersection = len(a & b)
        union = len(a | b)
        return intersection / union if union else 0.0
