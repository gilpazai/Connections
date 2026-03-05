"""CRUD operations for all four Notion databases.

Databases: Contacts, Leads, Work History, Matches.
Uses the official notion-client SDK.
"""

from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Any

from notion_client import Client
from notion_client.helpers import iterate_paginated_api

from src.config import settings
from src.models.contact import Contact, WorkHistoryEntry
from src.models.lead import Lead
from src.models.match import Match

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Helpers for building Notion property dicts
# ---------------------------------------------------------------------------

def _title(text: str) -> dict:
    return {"title": [{"text": {"content": text}}]}


def _rich_text(text: str) -> dict:
    return {"rich_text": [{"text": {"content": text}}]}


def _url(url: str) -> dict:
    if not url:
        return {"url": None}
    return {"url": url}


def _select(value: str) -> dict:
    return {"select": {"name": value}}


def _multi_select(values: list[str]) -> dict:
    return {"multi_select": [{"name": v} for v in values]}


def _number(value: float | int) -> dict:
    return {"number": value}


def _date(d: date | None) -> dict:
    if d is None:
        return {"date": None}
    return {"date": {"start": d.isoformat()}}


def _checkbox(value: bool) -> dict:
    return {"checkbox": value}


# ---------------------------------------------------------------------------
# Helpers for reading Notion property values
# ---------------------------------------------------------------------------

def _read_title(prop: dict) -> str:
    parts = prop.get("title", [])
    return parts[0]["plain_text"] if parts else ""


def _read_rich_text(prop: dict) -> str:
    parts = prop.get("rich_text", [])
    return parts[0]["plain_text"] if parts else ""


def _read_url(prop: dict) -> str:
    return prop.get("url") or ""


def _read_select(prop: dict) -> str:
    sel = prop.get("select")
    return sel["name"] if sel else ""


def _read_multi_select(prop: dict) -> list[str]:
    return [item["name"] for item in prop.get("multi_select", [])]


def _read_number(prop: dict) -> float:
    val = prop.get("number")
    return float(val) if val is not None else 0.0


def _read_date(prop: dict) -> date | None:
    d = prop.get("date")
    if not d or not d.get("start"):
        return None
    return datetime.fromisoformat(d["start"]).date()


def _read_checkbox(prop: dict) -> bool:
    return prop.get("checkbox", False)


# ---------------------------------------------------------------------------
# NotionStore
# ---------------------------------------------------------------------------

class NotionStore:
    """Handles all Notion database operations for the Connections app."""

    def __init__(
        self,
        token: str | None = None,
        contacts_db_id: str | None = None,
        leads_db_id: str | None = None,
        work_history_db_id: str | None = None,
        matches_db_id: str | None = None,
    ):
        self.client = Client(auth=token or settings.notion_token)
        self.contacts_db = contacts_db_id or settings.notion_contacts_db_id
        self.leads_db = leads_db_id or settings.notion_leads_db_id
        self.work_history_db = work_history_db_id or settings.notion_work_history_db_id
        self.matches_db = matches_db_id or settings.notion_matches_db_id
        self._ensure_work_history_schema()

    def _ensure_work_history_schema(self) -> None:
        """Add any missing properties to the Work History database.

        Notion's databases.update is idempotent: existing properties are
        left unchanged, missing ones are created.
        """
        if not self.work_history_db:
            return
        try:
            self.client.databases.update(
                database_id=self.work_history_db,
                properties={"Is Advisory": {"checkbox": {}}},
            )
        except Exception:
            pass  # Non-fatal; store_work_history will surface the real error

    # -----------------------------------------------------------------------
    # Contacts
    # -----------------------------------------------------------------------

    def contact_exists(self, name: str, linkedin_url: str = "") -> bool:
        """Check if a contact with the same name or LinkedIn URL already exists."""
        filters = [{"property": "Name", "title": {"equals": name}}]
        if linkedin_url:
            filters.append({"property": "LinkedIn URL", "url": {"equals": linkedin_url}})
        pages = list(iterate_paginated_api(
            self.client.databases.query,
            database_id=self.contacts_db,
            filter={"or": filters} if len(filters) > 1 else filters[0],
        ))
        return len(pages) > 0

    def create_contact(self, contact: Contact, skip_duplicate_check: bool = False) -> str:
        """Create a contact in Notion. Returns the new page ID.

        Raises ValueError if a contact with the same name or LinkedIn URL
        already exists, unless skip_duplicate_check is True.
        """
        if not skip_duplicate_check:
            if self.contact_exists(contact.name, contact.linkedin_url):
                raise ValueError(f"Contact '{contact.name}' already exists")
        props = {
            "Name": _title(contact.name),
            "LinkedIn URL": _url(contact.linkedin_url),
            "Company (Current)": _rich_text(contact.company_current),
            "Title (Current)": _rich_text(contact.title_current),
            "Relationship Strength": _select(contact.relationship_strength),
            "Tags": _multi_select(contact.tags),
            "Dealigence Person ID": _rich_text(contact.dealigence_person_id),
            "Status": _select(contact.status),
            "Notes": _rich_text(contact.notes),
        }
        if contact.last_enriched:
            props["Last Enriched"] = _date(contact.last_enriched)
        page = self.client.pages.create(
            parent={"database_id": self.contacts_db},
            properties=props,
        )
        return page["id"]

    def get_all_contacts(self, status: str | None = None) -> list[Contact]:
        """Fetch all contacts, optionally filtered by status."""
        kwargs: dict[str, Any] = {"database_id": self.contacts_db}
        if status:
            kwargs["filter"] = {"property": "Status", "select": {"equals": status}}
        pages = list(iterate_paginated_api(
            self.client.databases.query,
            **kwargs,
        ))
        return [self._page_to_contact(p) for p in pages]

    def mark_contact_enriched(self, page_id: str, dealigence_id: str = "") -> None:
        """Update a contact's enrichment timestamp and optional Dealigence ID."""
        props: dict[str, Any] = {"Last Enriched": _date(date.today())}
        if dealigence_id:
            props["Dealigence Person ID"] = _rich_text(dealigence_id)
        self.client.pages.update(page_id=page_id, properties=props)

    def _page_to_contact(self, page: dict) -> Contact:
        p = page["properties"]
        return Contact(
            name=_read_title(p.get("Name", {})),
            linkedin_url=_read_url(p.get("LinkedIn URL", {})),
            company_current=_read_rich_text(p.get("Company (Current)", {})),
            title_current=_read_rich_text(p.get("Title (Current)", {})),
            relationship_strength=_read_select(p.get("Relationship Strength", {})),
            tags=_read_multi_select(p.get("Tags", {})),
            dealigence_person_id=_read_rich_text(p.get("Dealigence Person ID", {})),
            last_enriched=_read_date(p.get("Last Enriched", {})),
            status=_read_select(p.get("Status", {})),
            notes=_read_rich_text(p.get("Notes", {})),
            notion_page_id=page["id"],
        )

    # -----------------------------------------------------------------------
    # Leads
    # -----------------------------------------------------------------------

    def lead_exists(self, name: str, linkedin_url: str = "") -> bool:
        """Check if a lead with the same name or LinkedIn URL already exists."""
        filters = [{"property": "Name", "title": {"equals": name}}]
        if linkedin_url:
            filters.append({"property": "LinkedIn URL", "url": {"equals": linkedin_url}})
        pages = list(iterate_paginated_api(
            self.client.databases.query,
            database_id=self.leads_db,
            filter={"or": filters} if len(filters) > 1 else filters[0],
        ))
        return len(pages) > 0

    def create_lead(self, lead: Lead, skip_duplicate_check: bool = False) -> str:
        """Create a lead in Notion. Returns the new page ID.

        Raises ValueError if a lead with the same name or LinkedIn URL
        already exists, unless skip_duplicate_check is True.
        """
        if not skip_duplicate_check:
            if self.lead_exists(lead.name, lead.linkedin_url):
                raise ValueError(f"Lead '{lead.name}' already exists")
        props = {
            "Name": _title(lead.name),
            "LinkedIn URL": _url(lead.linkedin_url),
            "Company (Current)": _rich_text(lead.company_current),
            "Title (Current)": _rich_text(lead.title_current),
            "Priority": _select(lead.priority),
            "Batch": _rich_text(lead.batch),
            "Dealigence Person ID": _rich_text(lead.dealigence_person_id),
            "Status": _select(lead.status),
            "Notes": _rich_text(lead.notes),
        }
        if lead.last_enriched:
            props["Last Enriched"] = _date(lead.last_enriched)
        page = self.client.pages.create(
            parent={"database_id": self.leads_db},
            properties=props,
        )
        return page["id"]

    def get_all_leads(self, batch: str | None = None, status: str | None = None) -> list[Lead]:
        """Fetch all leads, optionally filtered by batch and/or status."""
        kwargs: dict[str, Any] = {"database_id": self.leads_db}
        filters = []
        if batch:
            filters.append({"property": "Batch", "rich_text": {"equals": batch}})
        if status:
            filters.append({"property": "Status", "select": {"equals": status}})

        if len(filters) == 1:
            kwargs["filter"] = filters[0]
        elif len(filters) > 1:
            kwargs["filter"] = {"and": filters}

        pages = list(iterate_paginated_api(
            self.client.databases.query,
            **kwargs,
        ))
        return [self._page_to_lead(p) for p in pages]

    def mark_lead_enriched(self, page_id: str, dealigence_id: str = "") -> None:
        """Update a lead's enrichment timestamp and status."""
        props: dict[str, Any] = {
            "Last Enriched": _date(date.today()),
            "Status": _select("Enriched"),
        }
        if dealigence_id:
            props["Dealigence Person ID"] = _rich_text(dealigence_id)
        self.client.pages.update(page_id=page_id, properties=props)

    def update_lead_status(self, page_id: str, status: str) -> None:
        self.client.pages.update(
            page_id=page_id,
            properties={"Status": _select(status)},
        )

    def _page_to_lead(self, page: dict) -> Lead:
        p = page["properties"]
        return Lead(
            name=_read_title(p.get("Name", {})),
            linkedin_url=_read_url(p.get("LinkedIn URL", {})),
            company_current=_read_rich_text(p.get("Company (Current)", {})),
            title_current=_read_rich_text(p.get("Title (Current)", {})),
            priority=_read_select(p.get("Priority", {})),
            batch=_read_rich_text(p.get("Batch", {})),
            dealigence_person_id=_read_rich_text(p.get("Dealigence Person ID", {})),
            last_enriched=_read_date(p.get("Last Enriched", {})),
            status=_read_select(p.get("Status", {})),
            notes=_read_rich_text(p.get("Notes", {})),
            notion_page_id=page["id"],
        )

    # -----------------------------------------------------------------------
    # Work History
    # -----------------------------------------------------------------------

    def store_work_history(self, entries: list[WorkHistoryEntry]) -> int:
        """Store work history entries in Notion. Returns count of entries created."""
        created = 0
        for entry in entries:
            props = {
                "Person Name": _title(entry.person_name),
                "Person Type": _select(entry.person_type),
                "Employer Name": _rich_text(entry.employer_name),
                "Employer Dealigence ID": _rich_text(entry.employer_dealigence_id),
                "Role Title": _rich_text(entry.role_title),
                "Seniority": _select(entry.seniority) if entry.seniority else _rich_text(""),
                "Start Date": _date(entry.start_date),
                "End Date": _date(entry.end_date),
                "Tenure Years": _number(entry.tenure_years),
                "Is Advisory": _checkbox(entry.is_advisory),
                "Source Person ID": _rich_text(entry.source_person_id),
            }
            self.client.pages.create(
                parent={"database_id": self.work_history_db},
                properties=props,
            )
            created += 1
        return created

    def delete_work_history_for_person(self, source_person_id: str) -> int:
        """Archive all work history entries for a person (for re-enrichment)."""
        pages = list(iterate_paginated_api(
            self.client.databases.query,
            database_id=self.work_history_db,
            filter={"property": "Source Person ID", "rich_text": {"equals": source_person_id}},
        ))
        for page in pages:
            self.client.pages.update(page_id=page["id"], archived=True)
        return len(pages)

    def delete_work_history_by_name(self, person_name: str) -> int:
        """Archive all work history entries for a person by name."""
        pages = list(iterate_paginated_api(
            self.client.databases.query,
            database_id=self.work_history_db,
            filter={"property": "Person Name", "title": {"equals": person_name}},
        ))
        for page in pages:
            self.client.pages.update(page_id=page["id"], archived=True)
        return len(pages)

    def get_all_work_history(self, person_type: str | None = None) -> list[WorkHistoryEntry]:
        """Fetch all work history entries, optionally filtered by person type."""
        kwargs: dict[str, Any] = {"database_id": self.work_history_db}
        if person_type:
            kwargs["filter"] = {"property": "Person Type", "select": {"equals": person_type}}
        pages = list(iterate_paginated_api(
            self.client.databases.query,
            **kwargs,
        ))
        return [self._page_to_work_history(p) for p in pages]

    def get_work_histories_grouped(
        self, person_type: str | None = None
    ) -> dict[str, list[WorkHistoryEntry]]:
        """Get work histories grouped by source_person_id."""
        entries = self.get_all_work_history(person_type=person_type)
        grouped: dict[str, list[WorkHistoryEntry]] = {}
        for entry in entries:
            key = entry.source_person_id or entry.person_name
            grouped.setdefault(key, []).append(entry)
        return grouped

    def _page_to_work_history(self, page: dict) -> WorkHistoryEntry:
        p = page["properties"]
        # Seniority might be stored as select or rich_text depending on data
        seniority = _read_select(p.get("Seniority", {}))
        if not seniority:
            seniority = _read_rich_text(p.get("Seniority", {}))
        return WorkHistoryEntry(
            person_name=_read_title(p.get("Person Name", {})),
            person_type=_read_select(p.get("Person Type", {})),
            employer_name=_read_rich_text(p.get("Employer Name", {})),
            employer_dealigence_id=_read_rich_text(p.get("Employer Dealigence ID", {})),
            role_title=_read_rich_text(p.get("Role Title", {})),
            seniority=seniority,
            start_date=_read_date(p.get("Start Date", {})),
            end_date=_read_date(p.get("End Date", {})),
            is_advisory=_read_checkbox(p.get("Is Advisory", {})),
            tenure_years=_read_number(p.get("Tenure Years", {})),
            source_person_id=_read_rich_text(p.get("Source Person ID", {})),
            notion_page_id=page["id"],
        )

    def get_work_history_for_person(self, person_name: str) -> list[WorkHistoryEntry]:
        """Get all work history entries for a specific person by name."""
        pages = list(iterate_paginated_api(
            self.client.databases.query,
            database_id=self.work_history_db,
            filter={"property": "Person Name", "title": {"equals": person_name}},
        ))
        return [self._page_to_work_history(p) for p in pages]

    # -----------------------------------------------------------------------
    # Leads — batch archive
    # -----------------------------------------------------------------------

    def archive_batch(self, batch: str) -> int:
        """Set status to 'Archived' on all leads in a batch. Returns count."""
        pages = list(iterate_paginated_api(
            self.client.databases.query,
            database_id=self.leads_db,
            filter={"property": "Batch", "rich_text": {"equals": batch}},
        ))
        count = 0
        for page in pages:
            status = _read_select(page["properties"].get("Status", {}))
            if status != "Archived":
                self.client.pages.update(
                    page_id=page["id"],
                    properties={"Status": _select("Archived")},
                )
                count += 1
        return count

    def get_active_leads(self, batch: str | None = None) -> list[Lead]:
        """Get all leads excluding archived ones."""
        kwargs: dict[str, Any] = {"database_id": self.leads_db}
        filters = [{"property": "Status", "select": {"does_not_equal": "Archived"}}]
        if batch:
            filters.append({"property": "Batch", "rich_text": {"equals": batch}})
        if len(filters) == 1:
            kwargs["filter"] = filters[0]
        else:
            kwargs["filter"] = {"and": filters}
        pages = list(iterate_paginated_api(
            self.client.databases.query,
            **kwargs,
        ))
        return [self._page_to_lead(p) for p in pages]

    # -----------------------------------------------------------------------
    # Matches
    # -----------------------------------------------------------------------

    def create_match(self, match: Match) -> str:
        """Create a match record in Notion. Returns the new page ID."""
        title = f"{match.contact_name} -> {match.lead_name} via {match.shared_company}"
        props = {
            "Title": _title(title),
            "Contact Name": _rich_text(match.contact_name),
            "Lead Name": _rich_text(match.lead_name),
            "Shared Company": _rich_text(match.shared_company),
            "Overlap Start": _date(match.overlap_start),
            "Overlap End": _date(match.overlap_end),
            "Overlap Months": _number(match.overlap_months),
            "Contact Role": _rich_text(match.contact_role),
            "Lead Role": _rich_text(match.lead_role),
            "Match Rule": _select(match.rule_name),
            "Confidence": _select(match.confidence),
            "Status": _select(match.status),
            "Intro Draft": _rich_text(match.intro_draft),
            "Date Updated": _date(match.date_updated),
            "Notes": _rich_text(match.notes),
            "Contact LinkedIn": _url(match.contact_linkedin),
            "Lead LinkedIn": _url(match.lead_linkedin),
            "Lead Company": _rich_text(match.lead_company),
            "Lead Title": _rich_text(match.lead_title),
        }
        page = self.client.pages.create(
            parent={"database_id": self.matches_db},
            properties=props,
        )
        return page["id"]

    def match_exists(self, match: Match) -> bool:
        """Check if a match with the same dedup key already exists."""
        # Filter by contact name + lead name + company (close enough for dedup)
        pages = list(iterate_paginated_api(
            self.client.databases.query,
            database_id=self.matches_db,
            filter={
                "and": [
                    {"property": "Contact Name", "rich_text": {"equals": match.contact_name}},
                    {"property": "Lead Name", "rich_text": {"equals": match.lead_name}},
                    {"property": "Shared Company", "rich_text": {"equals": match.shared_company}},
                ]
            },
        ))
        return len(pages) > 0

    def get_all_matches(
        self,
        status: str | None = None,
        rule_name: str | None = None,
        confidence: str | None = None,
    ) -> list[Match]:
        """Fetch all matches, optionally filtered. Sorted by Date Updated descending."""
        kwargs: dict[str, Any] = {
            "database_id": self.matches_db,
            "sorts": [{"property": "Date Updated", "direction": "descending"}],
        }
        filters = []
        if status:
            filters.append({"property": "Status", "select": {"equals": status}})
        if rule_name:
            filters.append({"property": "Match Rule", "select": {"equals": rule_name}})
        if confidence:
            filters.append({"property": "Confidence", "select": {"equals": confidence}})

        if len(filters) == 1:
            kwargs["filter"] = filters[0]
        elif len(filters) > 1:
            kwargs["filter"] = {"and": filters}

        pages = list(iterate_paginated_api(
            self.client.databases.query,
            **kwargs,
        ))
        return [self._page_to_match(p) for p in pages]

    def update_match(self, page_id: str, **fields: Any) -> None:
        """Update specific fields on a match record.

        Auto-sets date_updated to today when status is changed.
        """
        props: dict[str, Any] = {}
        field_map = {
            "status": ("Status", _select),
            "confidence": ("Confidence", _select),
            "intro_draft": ("Intro Draft", _rich_text),
            "notes": ("Notes", _rich_text),
            "date_updated": ("Date Updated", _date),
            "contact_linkedin": ("Contact LinkedIn", _url),
            "lead_linkedin": ("Lead LinkedIn", _url),
            "lead_company": ("Lead Company", _rich_text),
            "lead_title": ("Lead Title", _rich_text),
        }
        for key, value in fields.items():
            if key in field_map:
                prop_name, builder = field_map[key]
                props[prop_name] = builder(value)
        # Auto-set date_updated when status changes
        if "status" in fields and "date_updated" not in fields:
            props["Date Updated"] = _date(date.today())
        if props:
            self.client.pages.update(page_id=page_id, properties=props)

    @staticmethod
    def _migrate_match_status(raw: str) -> str:
        """Map old status values to new ones."""
        migration = {"Reviewed": "Request Intro", "Acting": "Request Intro", "Done": "In CRM"}
        return migration.get(raw, raw)

    def _page_to_match(self, page: dict) -> Match:
        p = page["properties"]
        raw_status = _read_select(p.get("Status", {}))
        return Match(
            contact_name=_read_rich_text(p.get("Contact Name", {})),
            contact_id=_read_rich_text(p.get("Contact Name", {})),
            lead_name=_read_rich_text(p.get("Lead Name", {})),
            lead_id=_read_rich_text(p.get("Lead Name", {})),
            shared_company=_read_rich_text(p.get("Shared Company", {})),
            overlap_start=_read_date(p.get("Overlap Start", {})),
            overlap_end=_read_date(p.get("Overlap End", {})),
            overlap_months=int(_read_number(p.get("Overlap Months", {}))),
            contact_role=_read_rich_text(p.get("Contact Role", {})),
            lead_role=_read_rich_text(p.get("Lead Role", {})),
            rule_name=_read_select(p.get("Match Rule", {})),
            confidence=_read_select(p.get("Confidence", {})),
            status=self._migrate_match_status(raw_status),
            intro_draft=_read_rich_text(p.get("Intro Draft", {})),
            date_updated=_read_date(p.get("Date Updated", {})),
            notes=_read_rich_text(p.get("Notes", {})),
            contact_linkedin=_read_url(p.get("Contact LinkedIn", {})),
            lead_linkedin=_read_url(p.get("Lead LinkedIn", {})),
            lead_company=_read_rich_text(p.get("Lead Company", {})),
            lead_title=_read_rich_text(p.get("Lead Title", {})),
            notion_page_id=page["id"],
        )
