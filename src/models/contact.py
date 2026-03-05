from __future__ import annotations

from datetime import date
from pydantic import BaseModel


class WorkHistoryEntry(BaseModel):
    """A single employment stint for a person."""

    person_name: str
    person_type: str  # "contact" or "lead"
    employer_name: str
    employer_dealigence_id: str = ""
    role_title: str = ""
    seniority: str = ""  # founder, vp-c-level, managerial, hands-on
    start_date: date | None = None
    end_date: date | None = None  # None means current
    is_advisory: bool = False  # Board, investor, advisor — matches without date overlap
    tenure_years: float = 0.0
    source_person_id: str = ""

    # Notion page ID once stored (empty if not yet persisted)
    notion_page_id: str = ""


class Contact(BaseModel):
    """A person in the core network."""

    name: str
    linkedin_url: str = ""
    company_current: str = ""
    title_current: str = ""
    relationship_strength: str = "Medium"  # Close, Medium, Loose
    tags: list[str] = []
    dealigence_person_id: str = ""
    last_enriched: date | None = None
    status: str = "Active"  # Active, Inactive
    notes: str = ""

    # Notion page ID once stored
    notion_page_id: str = ""

    # Populated after enrichment
    work_history: list[WorkHistoryEntry] = []
