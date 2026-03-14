"""Contacts API router."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from backend.api.dependencies import get_store
from src.data.notion_store import NotionStore
from src.models.contact import Contact

router = APIRouter(prefix="/api/contacts", tags=["contacts"])


class CreateContactRequest(BaseModel):
    name: str
    linkedin_url: str = ""
    company_current: str = ""
    title_current: str = ""
    relationship_strength: str = "Medium"
    tags: list[str] = []
    status: str = "Active"
    notes: str = ""


class UpdateContactRequest(BaseModel):
    company_current: str | None = None
    title_current: str | None = None
    relationship_strength: str | None = None
    tags: list[str] | None = None
    status: str | None = None
    linkedin_url: str | None = None
    notes: str | None = None


@router.get("")
def list_contacts(
    status: str = "Active",
    store: NotionStore = Depends(get_store),
) -> list[Contact]:
    return store.get_all_contacts(status=status)


@router.post("", status_code=201)
def create_contact(
    body: CreateContactRequest,
    store: NotionStore = Depends(get_store),
) -> Contact:
    contact = Contact(**body.model_dump())
    store.create_contact(contact)
    return contact


@router.patch("/{page_id}")
def update_contact(
    page_id: str,
    body: UpdateContactRequest,
    store: NotionStore = Depends(get_store),
) -> dict:
    fields = {k: v for k, v in body.model_dump().items() if v is not None}
    if not fields:
        raise HTTPException(400, "No fields to update")
    store.update_contact(page_id, **fields)
    return {"updated": True, "page_id": page_id}


@router.delete("/{page_id}")
def delete_contact(
    page_id: str,
    person_name: str,
    store: NotionStore = Depends(get_store),
) -> dict:
    store.delete_contact(page_id, person_name=person_name)
    return {"deleted": True, "page_id": page_id}
