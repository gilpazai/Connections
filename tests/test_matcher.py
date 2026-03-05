"""Tests for the matcher orchestrator."""

from __future__ import annotations

from datetime import date

from src.engine.matcher import deduplicate_matches, run_matching
from src.models.contact import WorkHistoryEntry
from src.models.match import Match


def test_deduplicate_keeps_longest_overlap():
    """When duplicate keys exist, keep the match with the longest overlap."""
    matches = [
        Match(
            contact_name="Alice", contact_id="a",
            lead_name="Bob", lead_id="b",
            shared_company="Acme",
            overlap_months=6,
            rule_name="Rule1",
        ),
        Match(
            contact_name="Alice", contact_id="a",
            lead_name="Bob", lead_id="b",
            shared_company="Acme",
            overlap_months=18,
            rule_name="Rule2",
        ),
    ]
    result = deduplicate_matches(matches)
    assert len(result) == 1
    assert result[0].overlap_months == 18


def test_deduplicate_different_companies():
    """Different companies should produce separate matches."""
    matches = [
        Match(
            contact_name="Alice", contact_id="a",
            lead_name="Bob", lead_id="b",
            shared_company="Acme",
            overlap_months=12,
        ),
        Match(
            contact_name="Alice", contact_id="a",
            lead_name="Bob", lead_id="b",
            shared_company="Beta",
            overlap_months=6,
        ),
    ]
    result = deduplicate_matches(matches)
    assert len(result) == 2


def test_run_matching_end_to_end():
    """Full matching pipeline with synthetic data."""
    contacts = {
        "alice": [
            WorkHistoryEntry(
                person_name="Alice",
                person_type="contact",
                employer_name="Acme Corp",
                employer_dealigence_id="acme-1",
                role_title="VP Engineering",
                seniority="vp-c-level",
                start_date=date(2018, 1, 1),
                end_date=date(2022, 1, 1),
                source_person_id="alice",
            ),
            WorkHistoryEntry(
                person_name="Alice",
                person_type="contact",
                employer_name="StartupX",
                employer_dealigence_id="sx-1",
                role_title="CTO",
                seniority="founder",
                start_date=date(2022, 3, 1),
                end_date=None,  # current
                source_person_id="alice",
            ),
        ],
        "charlie": [
            WorkHistoryEntry(
                person_name="Charlie",
                person_type="contact",
                employer_name="Acme Corp",
                employer_dealigence_id="acme-1",
                role_title="Product Manager",
                seniority="managerial",
                start_date=date(2020, 1, 1),
                end_date=date(2023, 6, 1),
                source_person_id="charlie",
            ),
        ],
    }
    leads = {
        "bob": [
            WorkHistoryEntry(
                person_name="Bob",
                person_type="lead",
                employer_name="Acme Corp",
                employer_dealigence_id="acme-1",
                role_title="Data Scientist",
                seniority="hands-on",
                start_date=date(2019, 6, 1),
                end_date=date(2021, 6, 1),
                source_person_id="bob",
            ),
        ],
        "diana": [
            WorkHistoryEntry(
                person_name="Diana",
                person_type="lead",
                employer_name="StartupX",
                employer_dealigence_id="sx-1",
                role_title="Engineer",
                seniority="hands-on",
                start_date=date(2023, 1, 1),
                end_date=date(2024, 1, 1),
                source_person_id="diana",
            ),
        ],
    }

    matches = run_matching(contacts, leads)

    # Expected matches:
    # 1. Alice <-> Bob at Acme (overlap: 2019-06 to 2021-06, 24 months)
    # 2. Charlie <-> Bob at Acme (overlap: 2020-01 to 2021-06, 17 months)
    # 3. Alice <-> Diana at StartupX (overlap: 2023-01 to 2024-01, 12 months)
    assert len(matches) == 3

    match_tuples = {(m.contact_name, m.lead_name, m.shared_company) for m in matches}
    assert ("Alice", "Bob", "Acme Corp") in match_tuples
    assert ("Charlie", "Bob", "Acme Corp") in match_tuples
    assert ("Alice", "Diana", "StartupX") in match_tuples


def test_run_matching_no_matches():
    """No matches when no overlap exists."""
    contacts = {
        "alice": [
            WorkHistoryEntry(
                person_name="Alice",
                person_type="contact",
                employer_name="Acme",
                employer_dealigence_id="acme-1",
                start_date=date(2015, 1, 1),
                end_date=date(2017, 1, 1),
                source_person_id="alice",
            ),
        ],
    }
    leads = {
        "bob": [
            WorkHistoryEntry(
                person_name="Bob",
                person_type="lead",
                employer_name="Beta",
                employer_dealigence_id="beta-1",
                start_date=date(2020, 1, 1),
                end_date=date(2022, 1, 1),
                source_person_id="bob",
            ),
        ],
    }

    matches = run_matching(contacts, leads)
    assert len(matches) == 0
