"""Research API router — web research with investigator."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from backend.api.dependencies import get_store
from src.data.investigator_runner import run_research, get_cached_report, delete_cached_report
from src.data.notion_store import NotionStore

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/research", tags=["research"])


class ResearchRequest(BaseModel):
    person_name: str
    company: str = ""
    force_refresh: bool = False


class ResearchResponse(BaseModel):
    report: str
    cached: bool


@router.post("")
def run_person_research(
    body: ResearchRequest,
    store: NotionStore = Depends(get_store),
) -> ResearchResponse:
    """Run web research for a person. Returns markdown report."""
    # Check cache first
    if not body.force_refresh:
        cached = get_cached_report(body.person_name)
        if cached:
            return ResearchResponse(report=cached, cached=True)

    report = run_research(body.person_name, body.company, force_refresh=body.force_refresh)
    return ResearchResponse(report=report or "", cached=False)


@router.get("/{person_name}")
def get_report(person_name: str) -> ResearchResponse:
    """Get cached research report for a person."""
    cached = get_cached_report(person_name)
    if not cached:
        return ResearchResponse(report="", cached=False)
    return ResearchResponse(report=cached, cached=True)


@router.delete("/{person_name}")
def delete_report(person_name: str) -> dict:
    """Delete cached research report."""
    delete_cached_report(person_name)
    return {"deleted": True, "person_name": person_name}
