"""V1 matching rule: shared workplace with overlapping employment dates.

Identifies contacts and leads who worked at the same company during
overlapping time periods. Confidence is based on overlap duration
and seniority proximity.
"""

from __future__ import annotations

from datetime import date

from src.data.dealigence import normalize_company_name
from src.engine.index import CompanyTimeIndex, fill_end_dates, is_stealth_company, month_diff
from src.models.contact import WorkHistoryEntry
from src.models.match import Match


def _compute_confidence(overlap_months: int, contact_seniority: str, lead_seniority: str) -> str:
    """Determine match confidence based on overlap duration and seniority.

    High: >24 months overlap, or >12 months with similar seniority levels.
    Medium: 6-24 months overlap.
    Low: <6 months overlap.
    """
    senior_levels = {"founder", "vp-c-level"}
    same_seniority_tier = (
        (contact_seniority in senior_levels and lead_seniority in senior_levels)
        or contact_seniority == lead_seniority
    )

    if overlap_months > 24:
        return "High"
    if overlap_months > 12 and same_seniority_tier:
        return "High"
    if overlap_months >= 6:
        return "Medium"
    return "Low"


class SharedWorkplaceRule:
    """Matches contacts and leads who worked at the same company during overlapping dates."""

    name = "SharedWorkplace"
    description = (
        "Finds contacts and leads who worked at the same company "
        "during overlapping time periods."
    )

    def find_matches(
        self,
        contact_histories: dict[str, list[WorkHistoryEntry]],
        lead_histories: dict[str, list[WorkHistoryEntry]],
        index: CompanyTimeIndex,
    ) -> list[Match]:
        matches: list[Match] = []

        for lead_id, lead_entries in lead_histories.items():
            for lead_entry, lead_effective_end in fill_end_dates(lead_entries):
                if not lead_entry.start_date and not lead_entry.is_advisory:
                    continue
                if is_stealth_company(lead_entry.employer_name):
                    continue

                # Look up company in the index
                company_key = (
                    lead_entry.employer_dealigence_id
                    or normalize_company_name(lead_entry.employer_name)
                )
                if not company_key:
                    continue

                overlaps = index.find_overlaps(
                    company_key=company_key,
                    start=lead_entry.start_date or date(2000, 1, 1),
                    end=lead_effective_end,
                    target_type="contact",
                    query_is_advisory=lead_entry.is_advisory,
                )

                for contact_entry, overlap_start, overlap_end in overlaps:
                    is_advisory_match = lead_entry.is_advisory or contact_entry.is_advisory
                    months = month_diff(overlap_start, overlap_end)
                    if is_advisory_match:
                        confidence = "High"
                    else:
                        confidence = _compute_confidence(
                            months,
                            contact_entry.seniority,
                            lead_entry.seniority,
                        )
                    matches.append(Match(
                        contact_name=contact_entry.person_name,
                        contact_id=contact_entry.person_id,
                        lead_name=lead_entry.person_name,
                        lead_id=lead_id,
                        shared_company=lead_entry.employer_name,
                        overlap_start=overlap_start,
                        overlap_end=overlap_end,
                        overlap_months=months,
                        contact_role=contact_entry.role_title,
                        lead_role=lead_entry.role_title,
                        rule_name=self.name,
                        confidence=confidence,
                    ))

        return matches
