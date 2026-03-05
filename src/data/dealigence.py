"""Dealigence utility functions used by the matching engine."""

from __future__ import annotations

import logging
from datetime import date, datetime

logger = logging.getLogger(__name__)

# Common suffixes to strip during company name normalization
_COMPANY_SUFFIXES = [
    "incorporated", "inc.", "inc", "ltd.", "ltd", "llc", "l.l.c.",
    "corp.", "corp", "corporation", "co.", "co", "company",
    "limited", "gmbh", "ag", "sa", "s.a.", "plc",
]


def normalize_company_name(name: str) -> str:
    """Normalize company name for matching when Dealigence IDs are unavailable.

    Strips common corporate suffixes and extra whitespace,
    lowercases everything, and removes trailing punctuation.
    """
    normalized = name.lower().strip().rstrip(".,")
    for suffix in _COMPANY_SUFFIXES:
        if normalized.endswith(f" {suffix}"):
            normalized = normalized[: -(len(suffix) + 1)].strip().rstrip(".,")
    return normalized


def parse_date(value: str | None) -> date | None:
    """Parse a date string from Dealigence into a date object."""
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except (ValueError, TypeError):
        pass
    for fmt in ("%Y-%m", "%Y"):
        try:
            return datetime.strptime(value, fmt).date()
        except (ValueError, TypeError):
            continue
    logger.warning("Could not parse date: %s", value)
    return None
