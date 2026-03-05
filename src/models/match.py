from __future__ import annotations

from datetime import date
from pydantic import BaseModel


class Match(BaseModel):
    """A discovered warm introduction path between a contact and a lead."""

    contact_name: str
    contact_id: str  # Dealigence person ID or Notion page ID
    lead_name: str
    lead_id: str
    shared_company: str
    overlap_start: date | None = None
    overlap_end: date | None = None
    overlap_months: int = 0
    contact_role: str = ""
    lead_role: str = ""
    rule_name: str = ""  # Which MatchRule produced this
    confidence: str = "Medium"  # High, Medium, Low
    status: str = "New"  # New, Request Intro, Intro, In CRM
    intro_draft: str = ""

    # New fields for enhanced match tracking
    date_updated: date | None = None
    notes: str = ""
    contact_linkedin: str = ""
    lead_linkedin: str = ""
    lead_company: str = ""
    lead_title: str = ""

    # Notion page ID once stored
    notion_page_id: str = ""

    @property
    def dedup_key(self) -> tuple[str, str, str]:
        """Unique key for deduplication: (contact_id, lead_id, company)."""
        return (self.contact_id, self.lead_id, self.shared_company)
