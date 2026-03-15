"""Leads API router."""

from __future__ import annotations

import threading
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from backend.api.dependencies import get_store
from src.data.notion_store import NotionStore
from src.data.csv_import import parse_dealigence_csv
from src.models.lead import Lead

router = APIRouter(prefix="/api/leads", tags=["leads"])

# In-memory import task tracker
_import_tasks: dict[str, dict] = {}


class CreateLeadRequest(BaseModel):
    name: str
    linkedin_url: str = ""
    company_current: str = ""
    title_current: str = ""
    priority: str = "Medium"
    batch: str = ""
    status: str = "New"
    notes: str = ""


class UpdateLeadRequest(BaseModel):
    company_current: str | None = None
    title_current: str | None = None
    priority: str | None = None
    batch: str | None = None
    status: str | None = None
    linkedin_url: str | None = None
    notes: str | None = None


class PasteImportRequest(BaseModel):
    lines: list[str]
    batch: str = ""
    priority: str = "Medium"


class ArchiveBatchRequest(BaseModel):
    batch: str


@router.get("")
def list_leads(
    batch: Optional[str] = None,
    status: Optional[str] = None,
    store: NotionStore = Depends(get_store),
) -> list[Lead]:
    if status == "Archived":
        return store.get_all_leads(batch=batch, status="Archived")
    leads = store.get_active_leads(batch=batch)
    if status and status != "All":
        leads = [l for l in leads if l.status == status]
    return leads


@router.post("", status_code=201)
def create_lead(
    body: CreateLeadRequest,
    store: NotionStore = Depends(get_store),
) -> Lead:
    lead = Lead(**body.model_dump())
    store.create_lead(lead)
    return lead


def _run_import(task_id: str, text: str, batch: str, priority: str, store: NotionStore) -> None:
    """Background worker that processes CSV import."""
    task = _import_tasks[task_id]
    try:
        leads, work_history = parse_dealigence_csv(text, batch=batch, default_priority=priority)
        task["total"] = len(leads)

        for lead in leads:
            try:
                store.create_lead(lead)
                task["created"] += 1
                task["imported_names"].append(lead.name)
            except (ValueError, Exception):
                task["skipped"] += 1
            task["processed"] += 1

        if work_history:
            try:
                store.store_work_history(work_history)
            except Exception:
                pass

        task["status"] = "done"
    except Exception as exc:
        task["status"] = "error"
        task["error"] = str(exc)


@router.post("/import-csv", status_code=202)
async def import_csv(
    file: UploadFile = File(...),
    batch: str = Form(""),
    priority: str = Form("Medium"),
    store: NotionStore = Depends(get_store),
) -> dict:
    content = await file.read()
    text = content.decode("utf-8")

    task_id = uuid.uuid4().hex[:12]
    _import_tasks[task_id] = {
        "status": "running",
        "total": 0,
        "processed": 0,
        "created": 0,
        "skipped": 0,
        "imported_names": [],
        "error": None,
    }

    thread = threading.Thread(
        target=_run_import,
        args=(task_id, text, batch, priority, store),
        daemon=True,
    )
    thread.start()

    return {"task_id": task_id}


@router.get("/import-status/{task_id}")
def import_status(task_id: str) -> dict:
    task = _import_tasks.get(task_id)
    if not task:
        raise HTTPException(404, "Import task not found")
    return {"task_id": task_id, **task}


@router.post("/import-paste", status_code=201)
def import_paste(
    body: PasteImportRequest,
    store: NotionStore = Depends(get_store),
) -> dict:
    created = 0
    skipped = 0
    imported_names: list[str] = []

    for line in body.lines:
        name = line.strip()
        if not name:
            continue
        lead = Lead(name=name, priority=body.priority, batch=body.batch)
        try:
            store.create_lead(lead)
            created += 1
            imported_names.append(name)
        except ValueError:
            skipped += 1

    return {"created": created, "skipped": skipped, "imported_names": imported_names}


@router.patch("/{page_id}")
def update_lead(
    page_id: str,
    body: UpdateLeadRequest,
    store: NotionStore = Depends(get_store),
) -> dict:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "No fields to update")
    store.update_lead(page_id, **fields)
    return {"updated": True, "page_id": page_id}


@router.delete("/{page_id}")
def delete_lead(
    page_id: str,
    person_name: str,
    store: NotionStore = Depends(get_store),
) -> dict:
    store.delete_lead(page_id, person_name=person_name)
    return {"deleted": True, "page_id": page_id}


@router.post("/archive-batch")
def archive_batch(
    body: ArchiveBatchRequest,
    store: NotionStore = Depends(get_store),
) -> dict:
    count = store.archive_batch(body.batch)
    return {"archived": count, "batch": body.batch}


@router.delete("")
def delete_all_leads(store: NotionStore = Depends(get_store)) -> dict:
    count = store.delete_all_leads()
    return {"deleted": count}
