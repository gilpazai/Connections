"""Enrichment API router — LLM parsing of LinkedIn text."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.dependencies import get_store
from src.data.notion_store import NotionStore
from src.data.llm_parser import parse_linkedin_with_llm
from src.engine.matcher import match_new_person, store_new_matches

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/enrich", tags=["enrichment"])


class EnrichRequest(BaseModel):
    person_name: str
    person_type: str  # "Contact" or "Lead"
    raw_text: str
    notion_page_id: str = ""


class EnrichResponse(BaseModel):
    positions_stored: int
    new_matches: int


@router.post("")
def enrich_person(
    body: EnrichRequest,
    store: NotionStore = Depends(get_store),
) -> EnrichResponse:
    """Parse raw LinkedIn text with LLM, store work history, and auto-match."""
    # Parse LinkedIn text into structured positions
    positions = parse_linkedin_with_llm(body.raw_text, body.person_name)
    if not positions:
        return EnrichResponse(positions_stored=0, new_matches=0)

    # Delete existing work history for this person
    store.delete_work_history(person_name=body.person_name)

    # Build WorkHistoryEntry objects
    from src.models.contact import WorkHistoryEntry
    entries = []
    for pos in positions:
        entry = WorkHistoryEntry(
            person_name=body.person_name,
            person_type=body.person_type,
            employer_name=pos.get("employer_name", ""),
            role_title=pos.get("title", ""),
            seniority=pos.get("seniority", ""),
            start_date=pos.get("started_at"),
            end_date=pos.get("ended_at"),
            is_advisory=pos.get("is_advisory", False),
            tenure_years=pos.get("tenure_years", 0.0),
            source_person_id=body.notion_page_id,
        )
        entries.append(entry)

    count = store.store_work_history(entries)

    # Mark as enriched
    if body.notion_page_id:
        from datetime import date
        if body.person_type == "Contact":
            store.mark_contact_enriched(body.notion_page_id)
        else:
            store.mark_lead_enriched(body.notion_page_id)

    # Auto-match
    new_matches = 0
    history = store.get_work_history_for_person(body.person_name)
    if history:
        matches = match_new_person(body.person_name, history, body.person_type, store)
        if matches:
            created, _ = store_new_matches(matches, store)
            new_matches = created

    return EnrichResponse(positions_stored=count, new_matches=new_matches)
