"""Import leads from Dealigence CSV exports.

Parses the Dealigence "Stealth Co-Founders Report" CSV format and creates
Lead records + WorkHistoryEntry records from the CSV data.
"""

from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime

from src.data.linkedin import is_advisory_role
from src.models.contact import WorkHistoryEntry
from src.models.lead import Lead

logger = logging.getLogger(__name__)

# Column mappings for the Dealigence CSV export
COL_LINKEDIN = "Person Linkedin"
COL_NAME = "Person Name"
COL_TITLE = "Employee Title"
COL_DEPARTMENT = "Department"
COL_TENURE = "Tenure (Years)"
COL_GEOGRAPHY = "Geography"
COL_STARTED = "Started At"
COL_COMPANY = "Company Name"
COL_PRV_COMPANY = "Prv. Company Name"
COL_PRV_LINKEDIN = "Prv. Company Linkedin"
COL_PRV_TITLE = "Prv. Employee Title"
COL_PRV_DEPT = "Prv. Department"
COL_PRV_TENURE = "Prv. Tenure (Years)"
COL_VP = "VP / C-Level?"
COL_PRV_VP = "Prv. VP / C-Level?"
COL_MID = "Mid-Management?"
COL_PRV_MID = "Prv. Mid-Management?"
COL_REPEAT = "Is Repeat Founder?"


def _parse_date(value: str) -> date | None:
    if not value:
        return None
    try:
        return datetime.strptime(value.strip(), "%Y-%m-%d").date()
    except ValueError:
        pass
    try:
        return datetime.strptime(value.strip(), "%Y-%m").date()
    except ValueError:
        return None


def _parse_float(value: str) -> float:
    try:
        return float(value.strip())
    except (ValueError, AttributeError):
        return 0.0


def _seniority_from_flags(vp: str, mid: str, title: str) -> str:
    title_lower = title.lower()
    if "founder" in title_lower or "co-founder" in title_lower:
        return "Founder"
    if vp and vp.upper() == "TRUE":
        return "VP-C-Level"
    if mid and mid.upper() == "TRUE":
        return "Managerial"
    return "Hands-on"


def parse_dealigence_csv(
    csv_content: str,
    batch: str = "",
    default_priority: str = "Medium",
) -> tuple[list[Lead], list[WorkHistoryEntry]]:
    """Parse a Dealigence CSV export into Lead and WorkHistoryEntry lists.

    Returns:
        Tuple of (leads, work_history_entries)
    """
    leads: list[Lead] = []
    entries: list[WorkHistoryEntry] = []

    reader = csv.DictReader(io.StringIO(csv_content))

    for row in reader:
        name = row.get(COL_NAME, "").strip()
        if not name:
            continue

        linkedin = row.get(COL_LINKEDIN, "").strip()
        company = row.get(COL_COMPANY, "").strip()
        title = row.get(COL_TITLE, "").strip()

        lead = Lead(
            name=name,
            linkedin_url=linkedin,
            company_current=company,
            title_current=title,
            priority=default_priority,
            batch=batch,
            status="New",
        )
        leads.append(lead)

        # Current position work history
        started = _parse_date(row.get(COL_STARTED, ""))
        tenure = _parse_float(row.get(COL_TENURE, ""))
        seniority = _seniority_from_flags(
            row.get(COL_VP, ""), row.get(COL_MID, ""), title,
        )
        if company:
            entries.append(WorkHistoryEntry(
                person_name=name,
                person_type="Lead",
                employer_name=company,
                role_title=title,
                seniority=seniority,
                start_date=started,
                end_date=None,
                tenure_years=tenure,
                is_advisory=is_advisory_role(title),
            ))

        # Previous position work history
        prv_company = row.get(COL_PRV_COMPANY, "").strip()
        prv_title = row.get(COL_PRV_TITLE, "").strip()
        prv_tenure = _parse_float(row.get(COL_PRV_TENURE, ""))
        prv_seniority = _seniority_from_flags(
            row.get(COL_PRV_VP, ""), row.get(COL_PRV_MID, ""), prv_title,
        )
        # Only add previous position if we know its end date (= current position's start).
        # If started is None we can't determine when the previous job ended, so omitting
        # it prevents the entry from being mistakenly treated as "current employment".
        if prv_company and started is not None:
            prv_end = started
            prv_start = None
            if prv_tenure > 0:
                months_back = int(prv_tenure * 12)
                year = prv_end.year
                month = prv_end.month - months_back
                while month <= 0:
                    year -= 1
                    month += 12
                prv_start = date(year, month, 1)

            entries.append(WorkHistoryEntry(
                person_name=name,
                person_type="Lead",
                employer_name=prv_company,
                role_title=prv_title,
                seniority=prv_seniority,
                start_date=prv_start,
                end_date=prv_end,
                tenure_years=prv_tenure,
                is_advisory=is_advisory_role(prv_title),
            ))

    logger.info(
        "Parsed CSV: %d leads, %d work history entries",
        len(leads), len(entries),
    )
    return leads, entries
