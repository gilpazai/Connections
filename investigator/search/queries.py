from __future__ import annotations

from dataclasses import dataclass


@dataclass
class SearchResult:
    title: str
    url: str
    snippet: str
    source_query: str


class QueryGenerator:
    """Generates search queries for each report section."""

    def __init__(self, name: str, company: str | None) -> None:
        self._name = name
        self._q = f'"{name}"'
        self._c = f' "{company}"' if company else ""

    def professional_queries(self) -> list[str]:
        n, c = self._q, self._c
        return [
            f"{n}{c} professional experience resume -stock -ticker -valuation",
            f"{n}{c} current role title -stock -ticker -valuation",
            f"site:linkedin.com/in {n}{c}",
            f"{n}{c} biography about -stock -ticker -valuation",
            f"{n}{c} skills expertise background -stock -ticker -valuation",
        ]

    def expertise_queries(self) -> list[str]:
        n, c = self._q, self._c
        return [
            f"{n}{c} expert in",
            f"{n}{c} keynote speaker topic",
            f"{n}{c} research interests specialization",
            f"{n}{c} conference talk presentation",
        ]

    def thesis_queries(self) -> list[str]:
        n, c = self._q, self._c
        return [
            f'{n} "the problem with"',
            f"{n} interview podcast",
            f"{n}{c} vision future",
            f"{n} worldview perspective",
        ]

    def activity_queries(self) -> list[str]:
        n, c = self._q, self._c
        return [
            f'site:linkedin.com/recent-activity {n}',
            f'site:x.com {n} status',
        ]

    def social_queries(self) -> list[str]:
        n, c = self._q, self._c
        return [
            f"site:twitter.com {n}{c}",
            f"site:x.com {n}{c}",
            f"site:github.com {n}",
            f"site:reddit.com {n}",
            f"site:bsky.app {n}",
            f"site:linkedin.com {n}{c}",
            f"site:mastodon.social {n}",
            f"site:youtube.com {n}{c}",
        ]

    def news_queries(self) -> list[str]:
        n, c = self._q, self._c
        return [
            f"{n}{c} news",
            f"{n}{c} announced statement",
            f"{n}{c} interview quoted",
        ]

    def news_headline_queries(self) -> list[str]:
        """Queries for DDGS.news() endpoint (recency-focused)."""
        n, c = self._q, self._c
        return [
            f"{n}{c}",
            f"{n} announcement",
        ]
