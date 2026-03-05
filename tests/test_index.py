"""Tests for CompanyTimeIndex."""

from __future__ import annotations

from datetime import date

from src.engine.index import CompanyTimeIndex, IndexedEntry, compute_overlap, month_diff
from src.models.contact import WorkHistoryEntry


def test_compute_overlap_full():
    """Two intervals that fully overlap."""
    result = compute_overlap(
        date(2020, 1, 1), date(2022, 1, 1),
        date(2019, 1, 1), date(2023, 1, 1),
    )
    assert result == (date(2020, 1, 1), date(2022, 1, 1))


def test_compute_overlap_partial():
    """Two intervals that partially overlap."""
    result = compute_overlap(
        date(2020, 1, 1), date(2022, 6, 1),
        date(2021, 3, 1), date(2023, 1, 1),
    )
    assert result == (date(2021, 3, 1), date(2022, 6, 1))


def test_compute_overlap_none():
    """Two intervals that don't overlap."""
    result = compute_overlap(
        date(2018, 1, 1), date(2019, 1, 1),
        date(2020, 1, 1), date(2021, 1, 1),
    )
    assert result is None


def test_compute_overlap_adjacent():
    """Two intervals that are exactly adjacent (no overlap)."""
    result = compute_overlap(
        date(2020, 1, 1), date(2021, 1, 1),
        date(2021, 1, 1), date(2022, 1, 1),
    )
    assert result is None


def test_compute_overlap_current_employment():
    """One interval has None end date (still employed)."""
    result = compute_overlap(
        date(2020, 1, 1), None,  # still employed
        date(2021, 6, 1), date(2022, 6, 1),
    )
    assert result is not None
    assert result[0] == date(2021, 6, 1)
    assert result[1] == date(2022, 6, 1)


def test_month_diff():
    assert month_diff(date(2020, 1, 1), date(2020, 7, 1)) == 6
    assert month_diff(date(2020, 1, 1), date(2022, 1, 1)) == 24
    assert month_diff(date(2020, 6, 1), date(2020, 6, 1)) == 0


def test_index_build_and_lookup():
    """Build an index and verify overlap lookup works."""
    contact_histories = {
        "contact-1": [
            WorkHistoryEntry(
                person_name="Alice",
                person_type="contact",
                employer_name="Acme Corp",
                employer_dealigence_id="acme-123",
                role_title="Engineer",
                start_date=date(2019, 1, 1),
                end_date=date(2022, 6, 1),
                source_person_id="contact-1",
            ),
        ],
    }
    lead_histories = {
        "lead-1": [
            WorkHistoryEntry(
                person_name="Bob",
                person_type="lead",
                employer_name="Acme Corp",
                employer_dealigence_id="acme-123",
                role_title="PM",
                start_date=date(2020, 6, 1),
                end_date=date(2023, 1, 1),
                source_person_id="lead-1",
            ),
        ],
    }

    index = CompanyTimeIndex.build(contact_histories, lead_histories)
    assert index.company_count == 1
    assert index.entry_count == 2

    # Look up contacts at Acme during Bob's tenure
    overlaps = index.find_overlaps(
        company_key="acme-123",
        start=date(2020, 6, 1),
        end=date(2023, 1, 1),
        target_type="contact",
    )
    assert len(overlaps) == 1
    entry, overlap_start, overlap_end = overlaps[0]
    assert entry.person_name == "Alice"
    assert overlap_start == date(2020, 6, 1)
    assert overlap_end == date(2022, 6, 1)


def test_index_no_overlap():
    """Verify no results when there's no temporal overlap."""
    contact_histories = {
        "contact-1": [
            WorkHistoryEntry(
                person_name="Alice",
                person_type="contact",
                employer_name="Acme Corp",
                employer_dealigence_id="acme-123",
                start_date=date(2015, 1, 1),
                end_date=date(2017, 1, 1),
                source_person_id="contact-1",
            ),
        ],
    }
    lead_histories = {
        "lead-1": [
            WorkHistoryEntry(
                person_name="Bob",
                person_type="lead",
                employer_name="Acme Corp",
                employer_dealigence_id="acme-123",
                start_date=date(2020, 1, 1),
                end_date=date(2023, 1, 1),
                source_person_id="lead-1",
            ),
        ],
    }

    index = CompanyTimeIndex.build(contact_histories, lead_histories)
    overlaps = index.find_overlaps(
        company_key="acme-123",
        start=date(2020, 1, 1),
        end=date(2023, 1, 1),
        target_type="contact",
    )
    assert len(overlaps) == 0


def test_index_different_companies():
    """Verify no match when at different companies."""
    contact_histories = {
        "contact-1": [
            WorkHistoryEntry(
                person_name="Alice",
                person_type="contact",
                employer_name="Acme Corp",
                employer_dealigence_id="acme-123",
                start_date=date(2020, 1, 1),
                end_date=date(2022, 1, 1),
                source_person_id="contact-1",
            ),
        ],
    }
    lead_histories = {
        "lead-1": [
            WorkHistoryEntry(
                person_name="Bob",
                person_type="lead",
                employer_name="Beta Inc",
                employer_dealigence_id="beta-456",
                start_date=date(2020, 1, 1),
                end_date=date(2022, 1, 1),
                source_person_id="lead-1",
            ),
        ],
    }

    index = CompanyTimeIndex.build(contact_histories, lead_histories)
    # Query for contacts at beta-456 — Alice is NOT there
    overlaps = index.find_overlaps(
        company_key="beta-456",
        start=date(2020, 1, 1),
        end=date(2022, 1, 1),
        target_type="contact",
    )
    assert len(overlaps) == 0


def test_index_name_fallback():
    """Verify normalized company name fallback when IDs are missing."""
    contact_histories = {
        "contact-1": [
            WorkHistoryEntry(
                person_name="Alice",
                person_type="contact",
                employer_name="Acme Corp Inc.",
                employer_dealigence_id="",  # No ID
                start_date=date(2020, 1, 1),
                end_date=date(2022, 1, 1),
                source_person_id="contact-1",
            ),
        ],
    }
    lead_histories = {
        "lead-1": [
            WorkHistoryEntry(
                person_name="Bob",
                person_type="lead",
                employer_name="Acme Corp Inc",
                employer_dealigence_id="",  # No ID
                start_date=date(2020, 6, 1),
                end_date=date(2023, 1, 1),
                source_person_id="lead-1",
            ),
        ],
    }

    index = CompanyTimeIndex.build(contact_histories, lead_histories)
    # Both indexed under "acme" after normalization (strips "Corp" and "Inc")
    overlaps = index.find_overlaps(
        company_key="acme",
        start=date(2020, 6, 1),
        end=date(2023, 1, 1),
        target_type="contact",
    )
    assert len(overlaps) == 1
