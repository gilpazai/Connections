"""Batch lead enrichment helper for Dealigence MCP workflows.

Two modes:

  --plan              Generate an enrichment plan: group unenriched leads
                      by their previous employer so Claude can call MCP
                      get-people once per company (instead of once per lead).

  --store-batch FILE  Accept a JSON file with enrichment results and store
                      all of them into Notion, re-running matching for each.

Usage from Claude Code:
    python scripts/batch_enrich.py --plan
    python scripts/batch_enrich.py --plan --plan-out plan.json
    python scripts/batch_enrich.py --store-batch enriched.json
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict

sys.path.insert(0, ".")

from src.data.notion_store import NotionStore
from src.models.contact import WorkHistoryEntry
from src.data.dealigence import parse_date
from src.engine.matcher import match_new_person, store_new_matches

# Companies to skip when looking for a searchable previous employer
_SKIP_COMPANIES = {
    "stealth",
    "confidential",
    "self-employed",
    "israel defense forces",
    "idf",
}


def _should_skip(company_name: str) -> bool:
    """Return True if this company name is unsearchable."""
    lower = company_name.strip().lower()
    for skip in _SKIP_COMPANIES:
        if skip in lower:
            return True
    return False


# -----------------------------------------------------------------------
# --plan
# -----------------------------------------------------------------------

def plan(plan_out: str | None = None) -> None:
    """Generate an enrichment plan grouped by previous company."""
    store = NotionStore()

    # 1. Load unenriched leads
    all_leads = store.get_all_leads()
    unenriched = [l for l in all_leads if l.last_enriched is None]
    if not unenriched:
        print("All leads are already enriched. Nothing to do.")
        return

    # 2. Load existing work history for leads
    all_wh = store.get_all_work_history(person_type="Lead")
    wh_by_name: dict[str, list[WorkHistoryEntry]] = defaultdict(list)
    for entry in all_wh:
        wh_by_name[entry.person_name].append(entry)

    # 3. For each lead, find first non-skip previous company
    #    (positions are ordered current-first, so the second entry is the
    #     most recent *previous* employer when there are 2 from CSV import)
    by_company: dict[str, list[dict]] = defaultdict(list)
    no_searchable: list[dict] = []

    for lead in unenriched:
        positions = wh_by_name.get(lead.name, [])

        # Find a previous employer that is not the current company and not skipped
        search_company = None
        for pos in positions:
            employer = pos.employer_name.strip()
            if not employer:
                continue
            # Skip current company
            if employer.lower() == (lead.company_current or "").strip().lower():
                continue
            if _should_skip(employer):
                continue
            search_company = employer
            break

        lead_info = {
            "name": lead.name,
            "current_company": lead.company_current,
            "notion_page_id": lead.notion_page_id,
            "existing_positions": len(positions),
        }

        if search_company:
            by_company[search_company].append(lead_info)
        else:
            no_searchable.append(lead_info)

    # 4. Print summary
    print(f"\n=== Enrichment Plan: {len(unenriched)} unenriched leads ===\n")

    sorted_companies = sorted(by_company.keys(), key=lambda c: (-len(by_company[c]), c))
    total_searchable = sum(len(v) for v in by_company.values())
    print(f"Searchable by previous company: {total_searchable} leads across {len(by_company)} companies\n")

    for company in sorted_companies:
        leads_at = by_company[company]
        print(f"  {company} ({len(leads_at)} leads):")
        for info in leads_at:
            print(f"    - {info['name']}  (current: {info['current_company']}, {info['existing_positions']} positions)")

    if no_searchable:
        print(f"\n  No searchable previous company ({len(no_searchable)} leads):")
        for info in no_searchable:
            print(f"    - {info['name']}  (current: {info['current_company']}, {info['existing_positions']} positions)")

    print(f"\nSummary: {total_searchable} searchable + {len(no_searchable)} unsearchable = {len(unenriched)} total")

    # 5. Write JSON plan if requested
    if plan_out:
        plan_data = {
            "by_company": {c: by_company[c] for c in sorted_companies},
            "no_searchable": no_searchable,
            "total_unenriched": len(unenriched),
        }
        with open(plan_out, "w") as f:
            json.dump(plan_data, f, indent=2)
        print(f"\nPlan written to {plan_out}")


# -----------------------------------------------------------------------
# --store-batch
# -----------------------------------------------------------------------

def store_batch(filepath: str) -> None:
    """Read enrichment results from JSON and store them all in Notion."""
    with open(filepath) as f:
        records = json.load(f)

    if not isinstance(records, list):
        print("Error: expected a JSON array of enrichment records.")
        sys.exit(1)

    store = NotionStore()

    # Pre-load leads for page-id lookup
    all_leads = store.get_all_leads()
    lead_map = {l.name: l for l in all_leads}

    total_stored = 0
    total_deleted = 0
    total_matches_created = 0
    total_matches_skipped = 0

    for i, record in enumerate(records, 1):
        person_name = record["person_name"]
        person_type = record.get("person_type", "Lead")
        positions = record.get("positions", [])

        print(f"\n[{i}/{len(records)}] {person_name} ({len(positions)} positions)")

        # Delete old work history
        deleted = store.delete_work_history(person_name=person_name)
        total_deleted += deleted
        if deleted:
            print(f"  Deleted {deleted} old entries")

        # Build WorkHistoryEntry objects
        entries = []
        for pos in positions:
            entries.append(WorkHistoryEntry(
                person_name=person_name,
                person_type=person_type,
                employer_name=pos.get("employer_name", ""),
                employer_dealigence_id=pos.get("employer_id", ""),
                role_title=pos.get("title", ""),
                seniority=pos.get("seniority", ""),
                start_date=parse_date(pos.get("started_at")),
                end_date=parse_date(pos.get("ended_at")),
                tenure_years=float(pos.get("tenure_years", 0) or 0),
                source_person_id=pos.get("person_id", ""),
            ))

        # Store new entries
        count = store.store_work_history(entries)
        total_stored += count
        print(f"  Stored {count} entries")

        # Mark as enriched
        lead = lead_map.get(person_name)
        if lead and lead.notion_page_id:
            dealigence_id = entries[0].source_person_id if entries else ""
            store.mark_lead_enriched(lead.notion_page_id, dealigence_id)
            print(f"  Marked enriched")

        # Run matching
        all_history = store.get_work_history_for_person(person_name)
        if all_history:
            matches = match_new_person(person_name, all_history, person_type, store)
            if matches:
                created, skipped = store_new_matches(matches, store)
                total_matches_created += created
                total_matches_skipped += skipped
                print(f"  Matching: {created} new, {skipped} skipped")
                for m in matches:
                    print(f"    {m.contact_name} -> {m.lead_name} via {m.shared_company} ({m.overlap_months}mo)")
            else:
                print(f"  No matches found")
        else:
            print(f"  No work history for matching")

    # Final summary
    print(f"\n{'=' * 60}")
    print(f"Batch complete: {len(records)} leads processed")
    print(f"  Work history: {total_deleted} deleted, {total_stored} stored")
    print(f"  Matches: {total_matches_created} created, {total_matches_skipped} skipped")


# -----------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------

if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Batch lead enrichment for Dealigence MCP workflows"
    )
    parser.add_argument(
        "--plan", action="store_true",
        help="Generate enrichment plan: group leads by previous company",
    )
    parser.add_argument(
        "--plan-out", metavar="FILE",
        help="Write plan as JSON to FILE (used with --plan)",
    )
    parser.add_argument(
        "--store-batch", metavar="FILE",
        help="Store enrichment results from JSON file",
    )
    args = parser.parse_args()

    if args.plan:
        plan(plan_out=args.plan_out)
    elif args.store_batch:
        store_batch(args.store_batch)
    else:
        parser.print_help()
