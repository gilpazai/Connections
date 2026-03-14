"""Work History API router."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends

from backend.api.dependencies import get_store
from src.data.notion_store import NotionStore
from src.models.contact import WorkHistoryEntry

router = APIRouter(prefix="/api/work-history", tags=["work-history"])


@router.get("")
def list_work_history(
    person_type: Optional[str] = None,
    store: NotionStore = Depends(get_store),
) -> dict[str, list[WorkHistoryEntry]]:
    """Return work history grouped by person name."""
    return store.get_work_histories_grouped(person_type=person_type)


@router.get("/{person_name}")
def get_person_work_history(
    person_name: str,
    store: NotionStore = Depends(get_store),
) -> list[WorkHistoryEntry]:
    return store.get_work_history_for_person(person_name)
