"""Tests for matching rules."""

from __future__ import annotations

from datetime import date

from src.engine.index import CompanyTimeIndex
from src.engine.rules.shared_workplace import SharedWorkplaceRule
from src.models.contact import WorkHistoryEntry


def _make_entry(
    person_name: str,
    person_type: str,
    employer: str,
    employer_id: str,
    start: date,
    end: date | None = None,
    role: str = "",
    seniority: str = "",
    person_id: str = "",
) -> WorkHistoryEntry:
    return WorkHistoryEntry(
        person_name=person_name,
        person_type=person_type,
        employer_name=employer,
        employer_dealigence_id=employer_id,
        role_title=role,
        seniority=seniority,
        start_date=start,
        end_date=end,
        source_person_id=person_id or person_name.lower(),
    )


def test_shared_workplace_basic_match():
    """Two people overlapping at the same company."""
    contacts = {
        "alice": [
            _make_entry(
                "Alice", "contact", "Acme", "acme-1",
                date(2019, 1, 1), date(2022, 1, 1),
                role="Engineer", seniority="hands-on", person_id="alice",
            ),
        ],
    }
    leads = {
        "bob": [
            _make_entry(
                "Bob", "lead", "Acme", "acme-1",
                date(2020, 6, 1), date(2023, 1, 1),
                role="PM", seniority="managerial", person_id="bob",
            ),
        ],
    }

    index = CompanyTimeIndex.build(contacts, leads)
    rule = SharedWorkplaceRule()
    matches = rule.find_matches(contacts, leads, index)

    assert len(matches) == 1
    m = matches[0]
    assert m.contact_name == "Alice"
    assert m.lead_name == "Bob"
    assert m.shared_company == "Acme"
    assert m.overlap_start == date(2020, 6, 1)
    assert m.overlap_end == date(2022, 1, 1)
    assert m.overlap_months == 19
    assert m.rule_name == "SharedWorkplace"


def test_shared_workplace_no_overlap():
    """Same company but no temporal overlap."""
    contacts = {
        "alice": [
            _make_entry(
                "Alice", "contact", "Acme", "acme-1",
                date(2015, 1, 1), date(2018, 1, 1),
                person_id="alice",
            ),
        ],
    }
    leads = {
        "bob": [
            _make_entry(
                "Bob", "lead", "Acme", "acme-1",
                date(2020, 1, 1), date(2022, 1, 1),
                person_id="bob",
            ),
        ],
    }

    index = CompanyTimeIndex.build(contacts, leads)
    rule = SharedWorkplaceRule()
    matches = rule.find_matches(contacts, leads, index)
    assert len(matches) == 0


def test_shared_workplace_multiple_matches():
    """One lead overlaps with multiple contacts at the same company."""
    contacts = {
        "alice": [
            _make_entry(
                "Alice", "contact", "Acme", "acme-1",
                date(2019, 1, 1), date(2022, 1, 1),
                person_id="alice",
            ),
        ],
        "charlie": [
            _make_entry(
                "Charlie", "contact", "Acme", "acme-1",
                date(2020, 1, 1), date(2023, 6, 1),
                person_id="charlie",
            ),
        ],
    }
    leads = {
        "bob": [
            _make_entry(
                "Bob", "lead", "Acme", "acme-1",
                date(2020, 6, 1), date(2021, 6, 1),
                person_id="bob",
            ),
        ],
    }

    index = CompanyTimeIndex.build(contacts, leads)
    rule = SharedWorkplaceRule()
    matches = rule.find_matches(contacts, leads, index)

    assert len(matches) == 2
    names = {m.contact_name for m in matches}
    assert names == {"Alice", "Charlie"}


def test_shared_workplace_confidence_high():
    """High confidence for long overlap with similar seniority."""
    contacts = {
        "alice": [
            _make_entry(
                "Alice", "contact", "Acme", "acme-1",
                date(2018, 1, 1), date(2023, 1, 1),
                seniority="vp-c-level", person_id="alice",
            ),
        ],
    }
    leads = {
        "bob": [
            _make_entry(
                "Bob", "lead", "Acme", "acme-1",
                date(2019, 1, 1), date(2022, 1, 1),
                seniority="founder", person_id="bob",
            ),
        ],
    }

    index = CompanyTimeIndex.build(contacts, leads)
    rule = SharedWorkplaceRule()
    matches = rule.find_matches(contacts, leads, index)

    assert len(matches) == 1
    assert matches[0].confidence == "High"
    assert matches[0].overlap_months == 36


def test_shared_workplace_confidence_low():
    """Low confidence for short overlap."""
    contacts = {
        "alice": [
            _make_entry(
                "Alice", "contact", "Acme", "acme-1",
                date(2020, 1, 1), date(2020, 4, 1),
                person_id="alice",
            ),
        ],
    }
    leads = {
        "bob": [
            _make_entry(
                "Bob", "lead", "Acme", "acme-1",
                date(2020, 2, 1), date(2020, 5, 1),
                person_id="bob",
            ),
        ],
    }

    index = CompanyTimeIndex.build(contacts, leads)
    rule = SharedWorkplaceRule()
    matches = rule.find_matches(contacts, leads, index)

    assert len(matches) == 1
    assert matches[0].confidence == "Low"


def test_shared_workplace_skips_no_start_date():
    """Entries without start dates are skipped."""
    contacts = {
        "alice": [
            _make_entry(
                "Alice", "contact", "Acme", "acme-1",
                date(2020, 1, 1), date(2022, 1, 1),
                person_id="alice",
            ),
        ],
    }
    leads = {
        "bob": [
            WorkHistoryEntry(
                person_name="Bob",
                person_type="lead",
                employer_name="Acme",
                employer_dealigence_id="acme-1",
                start_date=None,  # Missing start date
                end_date=date(2022, 1, 1),
                source_person_id="bob",
            ),
        ],
    }

    index = CompanyTimeIndex.build(contacts, leads)
    rule = SharedWorkplaceRule()
    matches = rule.find_matches(contacts, leads, index)
    assert len(matches) == 0
