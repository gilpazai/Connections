"""Matches API router."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.dependencies import get_store
from src.data.notion_store import NotionStore
from src.engine.matcher import run_matching, store_new_matches, _group_histories_by_name
from src.models.match import Match

router = APIRouter(prefix="/api/matches", tags=["matches"])


class UpdateMatchRequest(BaseModel):
    status: str | None = None
    notes: str | None = None


@router.get("")
def list_matches(
    status: Optional[str] = None,
    confidence: Optional[str] = None,
    store: NotionStore = Depends(get_store),
) -> list[Match]:
    return store.get_all_matches(status=status, confidence=confidence)


@router.patch("/{page_id}")
def update_match(
    page_id: str,
    body: UpdateMatchRequest,
    store: NotionStore = Depends(get_store),
) -> dict:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if fields:
        store.update_match(page_id, **fields)
    return {"updated": True, "page_id": page_id}


@router.post("/recheck")
def recheck_matches(store: NotionStore = Depends(get_store)) -> dict:
    """Re-run the matching engine across all contacts and leads."""
    contact_entries = store.get_all_work_history(person_type="Contact")
    lead_entries = store.get_all_work_history(person_type="Lead")

    contact_histories = _group_histories_by_name(contact_entries)
    lead_histories = _group_histories_by_name(lead_entries)

    if not contact_histories or not lead_histories:
        return {"created": 0, "skipped": 0, "message": "No work history to match"}

    matches = run_matching(contact_histories, lead_histories)
    created, skipped = store_new_matches(matches, store)

    return {"created": created, "skipped": skipped}


@router.delete("")
def delete_all_matches(store: NotionStore = Depends(get_store)) -> dict:
    count = store.delete_all_matches()
    return {"deleted": count}
