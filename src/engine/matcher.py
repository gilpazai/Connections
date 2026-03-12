"""Matcher orchestrator: builds index, runs rules, deduplicates results.

This is the top-level entry point for the matching engine.
It coordinates the CompanyTimeIndex, RuleRegistry, and
produces deduplicated Match results.
"""

from __future__ import annotations

import logging
from datetime import date

from src.engine.index import CompanyTimeIndex
from src.engine.rules.registry import RuleRegistry, create_default_registry
from src.models.contact import WorkHistoryEntry
from src.models.match import Match

logger = logging.getLogger(__name__)

# Avoid circular import — TYPE_CHECKING block for type hints only
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from src.data.notion_store import NotionStore


def deduplicate_matches(matches: list[Match]) -> list[Match]:
    """Remove duplicate matches, keeping the one with the longest overlap."""
    best: dict[tuple, Match] = {}
    for match in matches:
        key = match.dedup_key
        if key not in best or match.overlap_months > best[key].overlap_months:
            best[key] = match
    return list(best.values())


def run_matching(
    contact_histories: dict[str, list[WorkHistoryEntry]],
    lead_histories: dict[str, list[WorkHistoryEntry]],
    registry: RuleRegistry | None = None,
) -> list[Match]:
    """Run all registered rules and return deduplicated matches.

    Args:
        contact_histories: person_id -> work history entries for contacts
        lead_histories: person_id -> work history entries for leads
        registry: Optional custom registry. Uses default if not provided.

    Returns:
        Deduplicated list of Match results from all rules.
    """
    if registry is None:
        registry = create_default_registry()

    # Build the inverted index
    index = CompanyTimeIndex.build(contact_histories, lead_histories)
    logger.info(
        "Built index: %d companies, %d entries",
        index.company_count,
        index.entry_count,
    )

    # Run all rules
    all_matches: list[Match] = []
    for rule in registry.get_all():
        logger.info("Running rule: %s", rule.name)
        matches = rule.find_matches(contact_histories, lead_histories, index)
        logger.info("Rule %s found %d raw matches", rule.name, len(matches))
        all_matches.extend(matches)

    # Deduplicate
    unique = deduplicate_matches(all_matches)
    logger.info(
        "Total: %d raw matches -> %d unique after dedup",
        len(all_matches),
        len(unique),
    )

    # Exclude stealth companies — generic placeholder, not a real shared employer
    filtered = [m for m in unique if "stealth" not in m.shared_company.lower()]
    if len(filtered) < len(unique):
        logger.info("Excluded %d stealth-company match(es)", len(unique) - len(filtered))
    return filtered


def _group_histories_by_name(
    entries: list[WorkHistoryEntry],
) -> dict[str, list[WorkHistoryEntry]]:
    """Group work history entries by person name."""
    grouped: dict[str, list[WorkHistoryEntry]] = {}
    for e in entries:
        grouped.setdefault(e.person_name, []).append(e)
    return grouped


def match_new_person(
    person_name: str,
    person_history: list[WorkHistoryEntry],
    person_type: str,
    store: NotionStore,
) -> list[Match]:
    """Match a single person against all existing people of the opposite type.

    If person_type == "Contact": loads all Lead histories and matches.
    If person_type == "Lead": loads all Contact histories and matches.
    Returns empty list if no work history or no opposite-type people exist.
    """
    if not person_history:
        return []

    if person_type == "Contact":
        opposite_entries = store.get_all_work_history(person_type="Lead")
        opposite_histories = _group_histories_by_name(opposite_entries)
        if not opposite_histories:
            return []
        return run_matching({person_name: person_history}, opposite_histories)
    elif person_type == "Lead":
        opposite_entries = store.get_all_work_history(person_type="Contact")
        opposite_histories = _group_histories_by_name(opposite_entries)
        if not opposite_histories:
            return []
        return run_matching(opposite_histories, {person_name: person_history})
    return []


def store_new_matches(
    matches: list[Match],
    store: NotionStore,
) -> tuple[int, int]:
    """Store matches with dedup and LinkedIn/company population.

    Loads all contacts, leads, and existing matches once to populate metadata
    and deduplicate in-memory (avoids N individual match_exists API calls).

    Returns (created_count, skipped_count).
    """
    if not matches:
        return 0, 0

    contacts = store.get_all_contacts()
    leads = store.get_all_leads()
    existing = store.get_all_matches()

    contact_map = {c.name: c for c in contacts}
    lead_map = {l.name: l for l in leads}
    existing_keys = {
        (m.contact_name, m.lead_name, m.shared_company)
        for m in existing
    }

    created = 0
    skipped = 0

    for match in matches:
        contact = contact_map.get(match.contact_name)
        lead = lead_map.get(match.lead_name)

        if contact:
            match.contact_linkedin = contact.linkedin_url
        if lead:
            match.lead_linkedin = lead.linkedin_url
            match.lead_company = lead.company_current
            match.lead_title = lead.title_current

        match.date_updated = date.today()

        key = (match.contact_name, match.lead_name, match.shared_company)
        if key in existing_keys:
            skipped += 1
            continue

        store.create_match(match)
        existing_keys.add(key)
        created += 1

    logger.info("Stored matches: %d created, %d skipped (dupes)", created, skipped)
    return created, skipped
