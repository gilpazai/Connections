#!/usr/bin/env python3
"""Create all 4 Notion databases for the VC Connections app.

Usage:
    python scripts/setup_notion.py <parent_page_id>

The parent_page_id is the ID of a Notion page that has been shared
with your integration. You can find it in the page URL:
    https://www.notion.so/Page-Name-<PAGE_ID_HERE>

This script creates:
    1. Contacts DB
    2. Leads DB
    3. Work History DB
    4. Matches DB

And prints the database IDs for your .env file.
"""

from __future__ import annotations

import sys
import os
import re

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from notion_client import Client


def extract_page_id(url_or_id: str) -> str:
    """Extract a Notion page ID from a URL or raw ID string."""
    # Already a clean UUID
    clean = url_or_id.strip().replace("-", "")
    if re.match(r"^[0-9a-f]{32}$", clean):
        return url_or_id.strip()

    # Extract from URL: last 32 hex chars (possibly with dashes)
    match = re.search(r"([0-9a-f]{32})(?:\?|$)", url_or_id.replace("-", ""))
    if match:
        raw = match.group(1)
        # Format as UUID
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"

    # Try extracting from end of URL path
    match = re.search(r"-([0-9a-f]{32})(?:\?|$)", url_or_id.replace("-", "").replace(" ", ""))
    if match:
        raw = match.group(1)
        return f"{raw[:8]}-{raw[8:12]}-{raw[12:16]}-{raw[16:20]}-{raw[20:]}"

    return url_or_id.strip()


def create_contacts_db(client: Client, parent_id: str) -> str:
    """Create the Contacts database."""
    db = client.databases.create(
        parent={"type": "page_id", "page_id": parent_id},
        title=[{"text": {"content": "Contacts"}}],
        properties={
            "Name": {"title": {}},
            "LinkedIn URL": {"url": {}},
            "Company (Current)": {"rich_text": {}},
            "Title (Current)": {"rich_text": {}},
            "Relationship Strength": {
                "select": {
                    "options": [
                        {"name": "Close", "color": "green"},
                        {"name": "Medium", "color": "yellow"},
                        {"name": "Loose", "color": "gray"},
                    ]
                }
            },
            "Tags": {
                "multi_select": {
                    "options": [
                        {"name": "VC", "color": "blue"},
                        {"name": "Founder", "color": "purple"},
                        {"name": "Operator", "color": "orange"},
                        {"name": "Angel", "color": "pink"},
                        {"name": "LP", "color": "green"},
                    ]
                }
            },
            "Dealigence Person ID": {"rich_text": {}},
            "Last Enriched": {"date": {}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "Active", "color": "green"},
                        {"name": "Inactive", "color": "gray"},
                    ]
                }
            },
            "Notes": {"rich_text": {}},
        },
    )
    return db["id"]


def create_leads_db(client: Client, parent_id: str) -> str:
    """Create the Leads database."""
    db = client.databases.create(
        parent={"type": "page_id", "page_id": parent_id},
        title=[{"text": {"content": "Leads"}}],
        properties={
            "Name": {"title": {}},
            "LinkedIn URL": {"url": {}},
            "Company (Current)": {"rich_text": {}},
            "Title (Current)": {"rich_text": {}},
            "Priority": {
                "select": {
                    "options": [
                        {"name": "High", "color": "red"},
                        {"name": "Medium", "color": "yellow"},
                        {"name": "Low", "color": "gray"},
                    ]
                }
            },
            "Batch": {"rich_text": {}},
            "Dealigence Person ID": {"rich_text": {}},
            "Last Enriched": {"date": {}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "New", "color": "blue"},
                        {"name": "Enriched", "color": "yellow"},
                        {"name": "Matched", "color": "green"},
                        {"name": "Contacted", "color": "orange"},
                        {"name": "Converted", "color": "purple"},
                    ]
                }
            },
            "Notes": {"rich_text": {}},
        },
    )
    return db["id"]


def create_work_history_db(client: Client, parent_id: str) -> str:
    """Create the Work History database."""
    db = client.databases.create(
        parent={"type": "page_id", "page_id": parent_id},
        title=[{"text": {"content": "Work History"}}],
        properties={
            "Person Name": {"title": {}},
            "Person Type": {
                "select": {
                    "options": [
                        {"name": "Contact", "color": "blue"},
                        {"name": "Lead", "color": "orange"},
                    ]
                }
            },
            "Employer Name": {"rich_text": {}},
            "Employer Dealigence ID": {"rich_text": {}},
            "Role Title": {"rich_text": {}},
            "Seniority": {
                "select": {
                    "options": [
                        {"name": "Founder", "color": "purple"},
                        {"name": "VP-C-Level", "color": "red"},
                        {"name": "Managerial", "color": "yellow"},
                        {"name": "Hands-on", "color": "blue"},
                    ]
                }
            },
            "Start Date": {"date": {}},
            "End Date": {"date": {}},
            "Tenure Years": {"number": {"format": "number"}},
            "Source Person ID": {"rich_text": {}},
        },
    )
    return db["id"]


def create_matches_db(client: Client, parent_id: str) -> str:
    """Create the Matches database."""
    db = client.databases.create(
        parent={"type": "page_id", "page_id": parent_id},
        title=[{"text": {"content": "Matches"}}],
        properties={
            "Title": {"title": {}},
            "Contact Name": {"rich_text": {}},
            "Lead Name": {"rich_text": {}},
            "Shared Company": {"rich_text": {}},
            "Overlap Start": {"date": {}},
            "Overlap End": {"date": {}},
            "Overlap Months": {"number": {"format": "number"}},
            "Contact Role": {"rich_text": {}},
            "Lead Role": {"rich_text": {}},
            "Match Rule": {
                "select": {
                    "options": [
                        {"name": "SharedWorkplace", "color": "blue"},
                    ]
                }
            },
            "Confidence": {
                "select": {
                    "options": [
                        {"name": "High", "color": "green"},
                        {"name": "Medium", "color": "yellow"},
                        {"name": "Low", "color": "red"},
                    ]
                }
            },
            "Status": {
                "select": {
                    "options": [
                        {"name": "New", "color": "blue"},
                        {"name": "Reviewed", "color": "yellow"},
                        {"name": "Acting", "color": "orange"},
                        {"name": "Done", "color": "green"},
                        {"name": "Dismissed", "color": "gray"},
                    ]
                }
            },
            "Intro Draft": {"rich_text": {}},
        },
    )
    return db["id"]


def update_env_file(db_ids: dict[str, str]) -> None:
    """Update the .env file with database IDs."""
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
    with open(env_path, "r") as f:
        content = f.read()

    replacements = {
        "NOTION_CONTACTS_DB_ID=": f"NOTION_CONTACTS_DB_ID={db_ids['contacts']}",
        "NOTION_LEADS_DB_ID=": f"NOTION_LEADS_DB_ID={db_ids['leads']}",
        "NOTION_WORK_HISTORY_DB_ID=": f"NOTION_WORK_HISTORY_DB_ID={db_ids['work_history']}",
        "NOTION_MATCHES_DB_ID=": f"NOTION_MATCHES_DB_ID={db_ids['matches']}",
    }

    for old_prefix, new_line in replacements.items():
        # Replace the line that starts with the prefix
        lines = content.split("\n")
        for i, line in enumerate(lines):
            if line.startswith(old_prefix):
                lines[i] = new_line
        content = "\n".join(lines)

    with open(env_path, "w") as f:
        f.write(content)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/setup_notion.py <page_url_or_id>")
        print()
        print("Provide the URL or ID of a Notion page shared with your integration.")
        sys.exit(1)

    raw_input = sys.argv[1]
    parent_id = extract_page_id(raw_input)
    print(f"Parent page ID: {parent_id}")

    token = os.environ.get("NOTION_TOKEN", "")
    if not token:
        # Try loading from .env
        env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env")
        if os.path.exists(env_path):
            with open(env_path) as f:
                for line in f:
                    if line.startswith("NOTION_TOKEN="):
                        token = line.strip().split("=", 1)[1]
                        break
    if not token:
        print("Error: NOTION_TOKEN not found in environment or .env file")
        sys.exit(1)

    client = Client(auth=token)

    print("\nCreating Notion databases...")

    print("  1/4 Creating Contacts DB...")
    contacts_id = create_contacts_db(client, parent_id)
    print(f"       -> {contacts_id}")

    print("  2/4 Creating Leads DB...")
    leads_id = create_leads_db(client, parent_id)
    print(f"       -> {leads_id}")

    print("  3/4 Creating Work History DB...")
    work_history_id = create_work_history_db(client, parent_id)
    print(f"       -> {work_history_id}")

    print("  4/4 Creating Matches DB...")
    matches_id = create_matches_db(client, parent_id)
    print(f"       -> {matches_id}")

    db_ids = {
        "contacts": contacts_id,
        "leads": leads_id,
        "work_history": work_history_id,
        "matches": matches_id,
    }

    print("\nUpdating .env file...")
    update_env_file(db_ids)
    print("Done!")

    print("\n--- Add these to your .env if not auto-updated ---")
    print(f"NOTION_CONTACTS_DB_ID={contacts_id}")
    print(f"NOTION_LEADS_DB_ID={leads_id}")
    print(f"NOTION_WORK_HISTORY_DB_ID={work_history_id}")
    print(f"NOTION_MATCHES_DB_ID={matches_id}")


if __name__ == "__main__":
    main()
