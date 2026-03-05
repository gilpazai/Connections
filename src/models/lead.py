from __future__ import annotations

from datetime import date
from pydantic import BaseModel

from src.models.contact import WorkHistoryEntry


class Lead(BaseModel):
    """A target lead for warm introductions."""

    name: str
    linkedin_url: str = ""
    company_current: str = ""
    title_current: str = ""
    priority: str = "Medium"  # High, Medium, Low
    batch: str = ""  # Month identifier, e.g. "2026-03"
    dealigence_person_id: str = ""
    last_enriched: date | None = None
    status: str = "New"  # New, Enriched, Matched, Contacted, Converted
    notes: str = ""

    # Notion page ID once stored
    notion_page_id: str = ""

    # Populated after enrichment
    work_history: list[WorkHistoryEntry] = []
