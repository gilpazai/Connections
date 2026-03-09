from __future__ import annotations

import asyncio
import logging

import httpx
from fake_useragent import UserAgent

from investigator.config import InvestigatorConfig

logger = logging.getLogger(__name__)


class PageFetcher:
    """Async HTTP fetcher with UA rotation and concurrency control."""

    def __init__(self, config: InvestigatorConfig) -> None:
        self._timeout = config.fetch_timeout_seconds
        self._ua = UserAgent()
        self._semaphore = asyncio.Semaphore(5)

    async def fetch_many(self, urls: list[str]) -> dict[str, str | None]:
        async with httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=True,
            http2=True,
        ) as client:
            tasks = [self._fetch_one(client, url) for url in urls]
            pairs = await asyncio.gather(*tasks)
        return dict(pairs)

    async def _fetch_one(
        self, client: httpx.AsyncClient, url: str
    ) -> tuple[str, str | None]:
        async with self._semaphore:
            try:
                resp = await client.get(
                    url,
                    headers={"User-Agent": self._ua.random},
                )
                if resp.status_code == 200:
                    return url, resp.text
                logger.debug("HTTP %d for %s", resp.status_code, url)
            except httpx.TimeoutException:
                logger.debug("Timeout fetching %s", url)
            except Exception as exc:
                logger.debug("Fetch error for %s: %s", url, exc)
            return url, None
