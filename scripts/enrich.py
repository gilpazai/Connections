"""Enrich contacts/leads work history and store to Notion.

Works with any data source (LinkedIn text via LLM, manual JSON, Dealigence CSV).

Enrichment workflow (LinkedIn via LLM):
    1. Navigate to a LinkedIn profile, Cmd+A to copy all text
    2. Save text to a file (or pipe via stdin)
    3. Run: python scripts/enrich.py --enrich NAME TYPE FILE
    The LLM parses the text, stores work history, and auto-matches.

Usage:
    python scripts/enrich.py --list           List unenriched contacts/leads
    python scripts/enrich.py --enrich N T F   Parse LinkedIn text with LLM + store + match
    python scripts/enrich.py --store N T J    Store pre-parsed JSON + auto-match
    python scripts/enrich.py --match-all      Re-run full matching
"""

from __future__ import annotations

import argparse
import json
import sys

sys.path.insert(0, ".")

from src.data.notion_store import NotionStore
from src.models.contact import WorkHistoryEntry
from src.data.dealigence import parse_date
from src.data.linkedin import parse_linkedin_date


def list_unenriched():
    """Print all contacts and leads that need enrichment."""
    store = NotionStore()

    contacts = store.get_all_contacts(status="Active")
    unenriched_contacts = [c for c in contacts if c.last_enriched is None]

    leads = store.get_all_leads()
    unenriched_leads = [l for l in leads if l.last_enriched is None]

    print(f"\n=== Unenriched Contacts ({len(unenriched_contacts)}) ===")
    for c in unenriched_contacts:
        print(f"  {c.name} | {c.company_current} | {c.linkedin_url}")

    print(f"\n=== Unenriched Leads ({len(unenriched_leads)}) ===")
    for l in unenriched_leads:
        print(f"  {l.name} | {l.company_current} | {l.linkedin_url}")

    print(f"\nTotal: {len(unenriched_contacts)} contacts + {len(unenriched_leads)} leads need enrichment")


def store_work_history(person_name: str, person_type: str, positions_json: str):
    """Store work history from MCP tool results and auto-match.

    positions_json should be a JSON array of position objects with:
    - employer_name, employer_id, title, seniority, started_at, ended_at, tenure_years
    """
    store = NotionStore()
    positions = json.loads(positions_json)

    # Delete old work history for this person (replaces CSV data with richer MCP data)
    deleted = store.delete_work_history(person_name=person_name)
    if deleted:
        print(f"Deleted {deleted} old work history entries for {person_name}")

    def _parse_any_date(value):
        """Parse date from either ISO format or LinkedIn format."""
        d = parse_date(value)
        if d is None and value:
            d = parse_linkedin_date(value)
        return d

    entries = []
    for pos in positions:
        entries.append(WorkHistoryEntry(
            person_name=person_name,
            person_type=person_type,
            employer_name=pos.get("employer_name", ""),
            employer_dealigence_id=pos.get("employer_id", ""),
            role_title=pos.get("title", ""),
            seniority=pos.get("seniority", ""),
            start_date=_parse_any_date(pos.get("started_at")),
            end_date=_parse_any_date(pos.get("ended_at")),
            is_advisory=bool(pos.get("is_advisory", False)),
            tenure_years=float(pos.get("tenure_years", 0) or 0),
            source_person_id=pos.get("person_id", ""),
        ))

    count = store.store_work_history(entries)
    print(f"Stored {count} work history entries for {person_name}")

    # Mark as enriched
    if person_type == "Contact":
        contacts = store.get_all_contacts()
        for c in contacts:
            if c.name == person_name and c.notion_page_id:
                person_id = entries[0].source_person_id if entries else ""
                store.mark_contact_enriched(c.notion_page_id, person_id)
                print(f"Marked {person_name} as enriched")
                break
    elif person_type == "Lead":
        leads = store.get_all_leads()
        for l in leads:
            if l.name == person_name and l.notion_page_id:
                person_id = entries[0].source_person_id if entries else ""
                store.mark_lead_enriched(l.notion_page_id, person_id)
                print(f"Marked {person_name} as enriched")
                break

    # Auto-match after enrichment
    from src.engine.matcher import match_new_person, store_new_matches

    all_history = store.get_work_history_for_person(person_name)
    if all_history:
        matches = match_new_person(person_name, all_history, person_type, store)
        if matches:
            created, skipped = store_new_matches(matches, store)
            print(f"Matching: {created} new matches, {skipped} duplicates skipped")
            for m in matches:
                if not store.match_exists(m) or created > 0:
                    print(f"  {m.contact_name} -> {m.lead_name} via {m.shared_company} ({m.overlap_months}mo, {m.confidence})")
        else:
            print("No matches found for this person")
    else:
        print("No work history available for matching")

    return count


def enrich_from_text(person_name: str, person_type: str, text_file: str):
    """Parse raw LinkedIn text with LLM and store work history.

    Reads raw text from a file (or stdin if '-'), sends to Claude for
    structured extraction, then stores + matches via the normal pipeline.
    """
    from src.data.llm_parser import parse_linkedin_with_llm

    if text_file == "-":
        raw_text = sys.stdin.read()
    else:
        with open(text_file, "r") as f:
            raw_text = f.read()

    if not raw_text.strip():
        print("Error: empty input text")
        return

    print(f"Parsing LinkedIn text for {person_name} ({len(raw_text)} chars)...")
    positions = parse_linkedin_with_llm(raw_text)
    print(f"LLM extracted {len(positions)} positions")

    for p in positions:
        advisory = " [advisory]" if p.get("is_advisory") else ""
        print(f"  {p.get('title', '?')} @ {p.get('employer_name', '?')}{advisory}")

    positions_json = json.dumps(positions)
    store_work_history(person_name, person_type, positions_json)


def match_all():
    """Re-run full matching: all contacts vs all leads."""
    from src.engine.matcher import run_matching, store_new_matches, _group_histories_by_name

    store = NotionStore()

    contact_entries = store.get_all_work_history(person_type="Contact")
    lead_entries = store.get_all_work_history(person_type="Lead")

    if not contact_entries:
        print("No contact work history found. Enrich contacts first.")
        return
    if not lead_entries:
        print("No lead work history found. Import leads with CSV or enrich them first.")
        return

    contact_histories = _group_histories_by_name(contact_entries)
    lead_histories = _group_histories_by_name(lead_entries)

    print(f"Matching {len(contact_histories)} contacts against {len(lead_histories)} leads...")
    matches = run_matching(contact_histories, lead_histories)
    print(f"Found {len(matches)} matches")

    created, skipped = store_new_matches(matches, store)
    print(f"Result: {created} new matches stored, {skipped} duplicates skipped")

    for m in matches:
        print(f"  {m.contact_name} -> {m.lead_name} via {m.shared_company} ({m.overlap_months}mo, {m.confidence})")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Enrich contacts/leads work history")
    parser.add_argument("--list", action="store_true", help="List unenriched contacts/leads")
    parser.add_argument("--enrich", nargs=3, metavar=("NAME", "TYPE", "FILE"),
                        help="Parse LinkedIn text with LLM + store: NAME TYPE TEXT_FILE (use - for stdin)")
    parser.add_argument("--store", nargs=3, metavar=("NAME", "TYPE", "JSON"),
                        help="Store pre-parsed JSON: NAME TYPE JSON_POSITIONS")
    parser.add_argument("--match-all", action="store_true",
                        help="Re-run full matching: all contacts vs all leads")
    args = parser.parse_args()

    if args.list:
        list_unenriched()
    elif args.enrich:
        enrich_from_text(args.enrich[0], args.enrich[1], args.enrich[2])
    elif args.store:
        store_work_history(args.store[0], args.store[1], args.store[2])
    elif args.match_all:
        match_all()
    else:
        parser.print_help()
