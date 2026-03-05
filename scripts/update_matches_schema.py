#!/usr/bin/env python3
"""Add new properties to the Matches DB and update Status options.

Run once to migrate the Notion schema for the matching overhaul.

Usage:
    python scripts/update_matches_schema.py
"""

from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from notion_client import Client
from src.config import settings


def main():
    client = Client(auth=settings.notion_token)
    db_id = settings.notion_matches_db_id

    if not db_id:
        print("Error: NOTION_MATCHES_DB_ID not set in .env")
        sys.exit(1)

    print(f"Updating Matches DB: {db_id}")

    # Add new properties and update Status options
    client.databases.update(
        database_id=db_id,
        properties={
            "Date Updated": {"date": {}},
            "Notes": {"rich_text": {}},
            "Contact LinkedIn": {"url": {}},
            "Lead LinkedIn": {"url": {}},
            "Lead Company": {"rich_text": {}},
            "Lead Title": {"rich_text": {}},
            "Status": {
                "select": {
                    "options": [
                        {"name": "New"},
                        {"name": "Request Intro", "color": "yellow"},
                        {"name": "Intro", "color": "orange"},
                        {"name": "In CRM", "color": "green"},
                        {"name": "Reviewed"},
                        {"name": "Acting"},
                        {"name": "Done"},
                        {"name": "Dismissed"},
                    ]
                }
            },
        },
    )

    # Also add Archived status to Leads DB
    leads_db_id = settings.notion_leads_db_id
    if leads_db_id:
        print(f"Updating Leads DB Status options: {leads_db_id}")
        client.databases.update(
            database_id=leads_db_id,
            properties={
                "Status": {
                    "select": {
                        "options": [
                            {"name": "New"},
                            {"name": "Enriched"},
                            {"name": "Matched"},
                            {"name": "Contacted"},
                            {"name": "Converted"},
                            {"name": "Archived", "color": "gray"},
                        ]
                    }
                },
            },
        )

    print("Done! Schema updated successfully.")


if __name__ == "__main__":
    main()
