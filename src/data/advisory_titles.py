"""Configurable advisory role title list.

Advisory roles (Investor, Board Member, etc.) are matched without date-overlap
requirements and displayed in a separate table cell rather than the position slots.

Titles are stored in .env as ADVISORY_TITLES (comma-separated) and can be
managed via the Settings page.
"""

from __future__ import annotations

import os

DEFAULT_ADVISORY_TITLES: list[str] = [
    "Investor",
    "Board Member",
    "Board Observer",
    "Advisor",
    "Adviser",
    "Chairman",
    "Chairwoman",
    "Chairperson",
    "President",
]


def load_advisory_titles() -> list[str]:
    """Return the current advisory title list from .env, or defaults."""
    raw = os.getenv("ADVISORY_TITLES", "")
    if raw.strip():
        return [t.strip() for t in raw.split(",") if t.strip()]
    return list(DEFAULT_ADVISORY_TITLES)


def save_advisory_titles(titles: list[str]) -> None:
    """Persist titles to .env as ADVISORY_TITLES=comma,separated."""
    from dotenv import set_key
    env_path = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "..", ".env")
    )
    set_key(env_path, "ADVISORY_TITLES", ",".join(titles))
