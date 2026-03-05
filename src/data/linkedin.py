"""LinkedIn utility functions for date parsing and role classification."""

from __future__ import annotations

import re
from datetime import date

_MONTHS = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
    "january": 1, "february": 2, "march": 3, "april": 4,
    "june": 6, "july": 7, "august": 8, "september": 9,
    "october": 10, "november": 11, "december": 12,
}

_ADVISORY_PATTERNS = re.compile(
    r"\b(?:investor|board\b|chairman|chairwoman|chairperson|"
    r"advisor[y]?|adviser)\b",
    re.IGNORECASE,
)


def parse_linkedin_date(date_str: str) -> date | None:
    """Parse LinkedIn date formats into a date object.

    Handles: "Jan 2020", "January 2020", "2020", "Present" → None
    """
    if not date_str:
        return None

    text = date_str.strip()

    if text.lower() == "present":
        return None

    # Try "Mon YYYY" or "Month YYYY"
    parts = text.split()
    if len(parts) == 2:
        month_str, year_str = parts
        month = _MONTHS.get(month_str.lower())
        if month:
            try:
                return date(int(year_str), month, 1)
            except (ValueError, TypeError):
                pass

    # Try "YYYY" only
    if text.isdigit() and len(text) == 4:
        try:
            return date(int(text), 1, 1)
        except ValueError:
            pass

    return None


def is_advisory_role(title: str) -> bool:
    """Check if a title represents a governance/advisory role.

    Advisory roles (investor, board, chairman, president, advisor)
    indicate ongoing connections — not time-bounded employment.
    """
    if _ADVISORY_PATTERNS.search(title):
        return True
    t = title.lower()
    if "president" in t and "vice" not in t:
        return True
    return False


