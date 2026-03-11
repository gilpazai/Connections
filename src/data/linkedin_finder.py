"""DuckDuckGo-based LinkedIn profile URL finder."""

from __future__ import annotations

import logging
from urllib.parse import urlparse, urlunparse

logger = logging.getLogger(__name__)


def find_linkedin_url(name: str, company: str | None = None) -> str | None:
    """Search DuckDuckGo for a LinkedIn profile URL.

    Queries: site:linkedin.com/in "{name}" ["{company}"]
    Returns the first linkedin.com/in/ URL found, query-params stripped.
    Returns None if nothing found or on any search error.
    """
    from ddgs import DDGS

    query = f'site:linkedin.com/in "{name}"'
    if company:
        query += f' "{company}"'

    logger.info("LinkedIn URL search: %s", query)
    try:
        results = DDGS().text(query, max_results=5)
        for r in results:
            url = r.get("href", "")
            if "linkedin.com/in/" in url:
                # Normalise country subdomains (il.linkedin.com → www.linkedin.com)
                p = urlparse(url)
                clean = urlunparse(p._replace(netloc="www.linkedin.com", query="", fragment=""))
                logger.info("Found LinkedIn URL: %s", clean)
                return clean
    except Exception as exc:
        logger.warning("LinkedIn URL search failed: %s", exc)
    return None
