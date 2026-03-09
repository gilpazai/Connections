from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import asdict

from ddgs import DDGS

from investigator.cache.store import CacheStore
from investigator.config import InvestigatorConfig
from investigator.search.queries import SearchResult

logger = logging.getLogger(__name__)


class SearchRateLimitError(Exception):
    pass


class SearchEngine:
    """DDGS wrapper with rate-limit serialization and caching."""

    def __init__(self, config: InvestigatorConfig, cache: CacheStore) -> None:
        self._config = config
        self._cache = cache
        self._lock = asyncio.Lock()

    async def search(
        self, query: str, max_results: int | None = None
    ) -> list[SearchResult]:
        max_results = max_results or self._config.max_results_per_query

        cached = self._cache.get(f"search:{query}")
        if cached is not None:
            logger.debug("Cache hit for query: %s", query)
            return [SearchResult(**r) for r in cached]

        async with self._lock:
            results = await self._execute_with_retry(
                self._text_search, query, max_results
            )
            await asyncio.sleep(self._config.rate_limit_delay)

        self._cache.set(f"search:{query}", [asdict(r) for r in results])
        return results

    async def search_news(
        self, query: str, max_results: int = 5
    ) -> list[SearchResult]:
        cached = self._cache.get(f"news:{query}")
        if cached is not None:
            logger.debug("Cache hit for news query: %s", query)
            return [SearchResult(**r) for r in cached]

        async with self._lock:
            results = await self._execute_with_retry(
                self._news_search, query, max_results
            )
            await asyncio.sleep(self._config.rate_limit_delay)

        self._cache.set(f"news:{query}", [asdict(r) for r in results])
        return results

    async def _execute_with_retry(
        self,
        fn,
        query: str,
        max_results: int,
        max_retries: int = 3,
    ) -> list[SearchResult]:
        for attempt in range(max_retries):
            try:
                return await asyncio.to_thread(fn, query, max_results)
            except Exception as exc:
                exc_str = str(exc).lower()
                if "ratelimit" in exc_str or "429" in exc_str or "403" in exc_str:
                    wait = 2 ** (attempt + 1)
                    logger.warning(
                        "Rate limited on '%s', retrying in %ds (attempt %d/%d)",
                        query,
                        wait,
                        attempt + 1,
                        max_retries,
                    )
                    await asyncio.sleep(wait)
                else:
                    logger.error("Search error on '%s': %s", query, exc)
                    return []
        raise SearchRateLimitError(f"Rate limited after {max_retries} retries: {query}")

    @staticmethod
    def _text_search(query: str, max_results: int) -> list[SearchResult]:
        ddgs = DDGS()
        raw = ddgs.text(query, max_results=max_results)
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("href", ""),
                snippet=r.get("body", ""),
                source_query=query,
            )
            for r in raw
        ]

    @staticmethod
    def _news_search(query: str, max_results: int) -> list[SearchResult]:
        ddgs = DDGS()
        raw = ddgs.news(query, max_results=max_results)
        return [
            SearchResult(
                title=r.get("title", ""),
                url=r.get("url", ""),
                snippet=r.get("body", ""),
                source_query=query,
            )
            for r in raw
        ]
