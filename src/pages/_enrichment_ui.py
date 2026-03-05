"""Reusable per-person enrichment helpers for contacts and leads pages."""

from __future__ import annotations

import logging

logger = logging.getLogger(__name__)


def do_enrich(store, person_name: str, person_type: str, raw_text: str):
    """Parse LinkedIn text, store work history, mark enriched, auto-match.

    Returns (stored_count, positions, new_matches).
    """
    from src.data.llm_parser import parse_linkedin_with_llm
    from src.models.contact import WorkHistoryEntry
    from src.data.dealigence import parse_date
    from src.data.linkedin import parse_linkedin_date
    from src.engine.matcher import match_new_person, store_new_matches

    positions = parse_linkedin_with_llm(raw_text)

    store.delete_work_history_by_name(person_name)

    def _parse_any_date(value):
        if not value:
            return None
        d = parse_date(value)
        if d is None:
            d = parse_linkedin_date(value)
        return d

    entries = [
        WorkHistoryEntry(
            person_name=person_name,
            person_type=person_type,
            employer_name=pos.get("employer_name", ""),
            employer_dealigence_id=pos.get("employer_id", ""),
            role_title=pos.get("title", ""),
            seniority=pos.get("seniority", ""),
            start_date=_parse_any_date(pos.get("started_at")),
            end_date=_parse_any_date(pos.get("ended_at")),
            is_advisory=bool(pos.get("is_advisory", False)),
            tenure_years=float(pos.get("tenure_years") or 0),
            source_person_id=pos.get("person_id", ""),
        )
        for pos in positions
    ]

    count = store.store_work_history(entries)
    person_id = entries[0].source_person_id if entries else ""

    if person_type == "Contact":
        for c in store.get_all_contacts():
            if c.name == person_name and c.notion_page_id:
                store.mark_contact_enriched(c.notion_page_id, person_id)
                break
    else:
        for l in store.get_all_leads():
            if l.name == person_name and l.notion_page_id:
                store.mark_lead_enriched(l.notion_page_id, person_id)
                break

    new_matches = 0
    history = store.get_work_history_for_person(person_name)
    if history:
        matches = match_new_person(person_name, history, person_type, store)
        if matches:
            created, _ = store_new_matches(matches, store)
            new_matches = created

    return count, positions, new_matches


def enrich_from_linkedin_url(store, person_name: str, person_type: str, linkedin_url: str):
    """Scrape LinkedIn experience page and enrich a person immediately.

    Opens a headed Chromium browser (reusing saved session), navigates to the
    experience page, extracts text, parses with LLM, stores work history, and
    auto-matches.  Returns (stored_count, positions, new_matches).
    """
    from src.data.linkedin_scraper import scrape_linkedin_experience
    raw_text = scrape_linkedin_experience(linkedin_url)
    return do_enrich(store, person_name, person_type, raw_text)
