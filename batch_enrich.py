#!/usr/bin/env python3
"""Batch enrich LinkedIn profiles from CSV using OpenAI and store in Notion."""

import csv
import sys
import time
from datetime import date, datetime
from pathlib import Path
from typing import Optional

from src.config import settings
from src.data.linkedin_scraper import scrape_linkedin_experience
from src.data.llm_parser import parse_linkedin_with_llm
from src.data.notion_store import NotionStore
from src.models.contact import Contact, WorkHistoryEntry


def enrich_from_csv(csv_path: str, max_people: int = None, skip_errors: bool = False):
    """Enrich all LinkedIn profiles from CSV and store in Notion.

    Args:
        csv_path: Path to CSV file
        max_people: Limit number of people to enrich (None = all)
        skip_errors: Continue on scrape/LLM errors (True) or stop (False)
    """
    print("=" * 80)
    print("CSV BATCH ENRICHMENT — OpenAI LLM Provider")
    print("=" * 80)
    print(f"CSV: {csv_path}")
    print(f"LLM Provider: {settings.llm_provider.upper()}")
    print(f"Model: {settings.openai_model}")
    print()

    csv_file = Path(csv_path)
    if not csv_file.exists():
        print(f"❌ ERROR: CSV file not found: {csv_path}")
        return False

    # Read CSV
    rows = []
    with open(csv_file, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    total = len(rows)
    if max_people:
        rows = rows[:max_people]
        print(f"Processing {len(rows)} of {total} people (limited by --max-people)")
    else:
        print(f"Processing {total} people")

    print()

    # Validate config
    if not settings.openai_api_key:
        print("❌ ERROR: OPENAI_API_KEY not set in .env")
        return False
    if not settings.notion_token:
        print("❌ ERROR: NOTION_TOKEN not set in .env")
        return False

    # Initialize Notion store
    store = NotionStore()

    succeeded = 0
    failed = 0
    skipped = 0
    start_time = time.time()

    for idx, row in enumerate(rows, 1):
        linkedin_url = row.get("Person Linkedin", "").strip()
        person_name = row.get("Person Name", "Unknown").strip()

        if not linkedin_url or not linkedin_url.startswith("http"):
            print(f"[{idx}/{len(rows)}] ⊘ {person_name} — no valid LinkedIn URL, skipping")
            skipped += 1
            continue

        print(f"[{idx}/{len(rows)}] {person_name}...", end=" ", flush=True)
        step_start = time.time()

        try:
            # Scrape LinkedIn profile
            print("scraping...", end=" ", flush=True)
            profile_text = scrape_linkedin_experience(linkedin_url, timeout_secs=30)

            if not profile_text or len(profile_text) < 100:
                print(f"✗ (empty profile)")
                failed += 1
                continue

            # Parse with OpenAI LLM
            print("parsing...", end=" ", flush=True)
            positions = parse_linkedin_with_llm(profile_text)

            if not positions:
                print(f"✗ (no positions parsed)")
                failed += 1
                continue

            # Get or create contact in Notion
            print("storing...", end=" ", flush=True)

            # Create new contact (skip duplicate check)
            contact = Contact(
                name=person_name,
                linkedin_url=linkedin_url,
                company_current="",
                title_current="",
                relationship_strength="Unknown",
                tags=[],
                dealigence_person_id="",
                status="Active",
                notes="",
            )
            try:
                contact_id = store.create_contact(contact, skip_duplicate_check=True)
            except Exception as e:
                print(f"✗ (contact creation failed: {str(e)[:40]})")
                failed += 1
                continue

            # Convert positions to WorkHistoryEntry objects
            work_entries = [
                WorkHistoryEntry(
                    person_name=person_name,
                    person_type="Lead",
                    employer_name=pos.get("employer_name", ""),
                    employer_dealigence_id="",
                    role_title=pos.get("title", ""),
                    seniority=pos.get("seniority", "hands-on"),
                    start_date=_parse_date(pos.get("started_at")),
                    end_date=_parse_date(pos.get("ended_at")),
                    tenure_years=pos.get("tenure_years", 0),
                    is_advisory=pos.get("is_advisory", False),
                    source_person_id=contact_id,
                )
                for pos in positions
            ]

            # Store work history
            store.store_work_history(work_entries)
            store.mark_contact_enriched(contact_id)

            print(f"✓ ({len(positions)} roles, {time.time() - step_start:.1f}s)")
            succeeded += 1

        except RuntimeError as e:
            print(f"✗ ({str(e)[:60]}...)")
            failed += 1
            if not skip_errors:
                return False
        except Exception as e:
            print(f"✗ (unexpected: {str(e)[:60]}...)")
            failed += 1
            if not skip_errors:
                return False

    elapsed = time.time() - start_time
    print()
    print("=" * 80)
    print(f"RESULTS: {succeeded} succeeded, {failed} failed, {skipped} skipped")
    if len(rows) > 0:
        print(f"Total time: {elapsed/60:.1f} minutes ({elapsed/len(rows):.1f}s per person)")
    print("=" * 80)

    return failed == 0


def _parse_date(date_str: Optional[str]) -> Optional[date]:
    """Parse ISO date string to date object."""
    if not date_str:
        return None
    try:
        return datetime.fromisoformat(date_str).date()
    except (ValueError, TypeError):
        return None


if __name__ == "__main__":
    csv_path = "/Users/gilpaz/Downloads/Dealigence - IN Venture - Stealth Co-Founders Report - Ex-Israelis February 2026.csv"

    # Parse optional arguments
    max_people = None
    skip_errors = True

    if "--max" in sys.argv:
        idx = sys.argv.index("--max")
        if idx + 1 < len(sys.argv):
            max_people = int(sys.argv[idx + 1])

    if "--no-skip" in sys.argv:
        skip_errors = False

    success = enrich_from_csv(csv_path, max_people=max_people, skip_errors=skip_errors)
    sys.exit(0 if success else 1)
