"""Shared FastAPI dependencies — store singleton, auth, etc."""

from __future__ import annotations

import os
from functools import lru_cache

from src.data.notion_store import NotionStore


@lru_cache(maxsize=1)
def get_store() -> NotionStore:
    """Return a singleton NotionStore instance."""
    return NotionStore()


def get_allowed_emails() -> set[str]:
    """Return the set of allowed team member emails."""
    raw = os.getenv("ALLOWED_EMAILS", "")
    return {e.strip().lower() for e in raw.split(",") if e.strip()}
