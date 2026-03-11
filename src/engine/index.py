"""CompanyTimeIndex: inverted index for efficient overlap matching.

Maps company IDs to lists of people who worked there with date ranges.
Enables O(K) lookups per query where K = people at that company,
rather than O(N*M) brute-force comparison.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date

from src.models.contact import WorkHistoryEntry


@dataclass
class IndexedEntry:
    """A single work history entry in the index."""

    person_id: str  # Dealigence person ID or person name
    person_name: str
    person_type: str  # "contact" or "lead"
    role_title: str
    seniority: str
    start_date: date
    end_date: date  # date.today() if still employed
    is_advisory: bool = False


def _effective_end(end_date: date | None) -> date:
    """Resolve None end dates (current employment) to today."""
    return end_date or date.today()


def fill_end_dates(
    entries: list[WorkHistoryEntry],
) -> list[tuple[WorkHistoryEntry, date]]:
    """Return (entry, effective_end_date) pairs with missing end dates filled in.

    For past positions where end_date is None (data quality gap), estimate the
    end date as the start of the next chronological position for that person.
    Only the most recent non-advisory position keeps end_date=None (→ today),
    since that correctly represents current employment.

    Without this, a person who left a company years ago but whose record lacks
    an end date would be treated as still employed there, causing false overlaps.
    """
    advisory = [(e, _effective_end(e.end_date)) for e in entries if e.is_advisory]
    undated = [(e, _effective_end(e.end_date)) for e in entries if not e.start_date and not e.is_advisory]

    dated = sorted(
        [e for e in entries if e.start_date and not e.is_advisory],
        key=lambda e: e.start_date,
    )
    filled = []
    for i, entry in enumerate(dated):
        if entry.end_date is None and i < len(dated) - 1:
            # Not the most recent position — fill end with next entry's start
            effective_end = dated[i + 1].start_date
        else:
            effective_end = _effective_end(entry.end_date)
        filled.append((entry, effective_end))

    return filled + advisory + undated


def is_stealth_company(employer_name: str) -> bool:
    """Return True if the company name indicates a stealth/undisclosed employer.

    Stealth companies are placeholders, not real shared employers — matching on
    them would produce false positives connecting unrelated people.
    """
    return "stealth" in employer_name.lower()


def compute_overlap(
    start_a: date,
    end_a: date | None,
    start_b: date,
    end_b: date | None,
) -> tuple[date, date] | None:
    """Compute the overlapping date range between two intervals.

    Returns (overlap_start, overlap_end) or None if no overlap.
    Overlap exists when: start_a < end_b AND start_b < end_a.
    """
    eff_end_a = _effective_end(end_a)
    eff_end_b = _effective_end(end_b)

    if start_a >= eff_end_b or start_b >= eff_end_a:
        return None

    overlap_start = max(start_a, start_b)
    overlap_end = min(eff_end_a, eff_end_b)
    return (overlap_start, overlap_end)


def month_diff(start: date, end: date) -> int:
    """Calculate approximate months between two dates."""
    return max(0, (end.year - start.year) * 12 + (end.month - start.month))


@dataclass
class CompanyTimeIndex:
    """Inverted index: company_key -> list of IndexedEntry.

    The company_key is the Dealigence company ID when available,
    falling back to the normalized company name.
    """

    _index: dict[str, list[IndexedEntry]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def add(self, company_key: str, entry: IndexedEntry) -> None:
        """Add a work history entry to the index under a company key."""
        self._index[company_key].append(entry)

    def find_overlaps(
        self,
        company_key: str,
        start: date,
        end: date | None,
        target_type: str = "contact",
        query_is_advisory: bool = False,
    ) -> list[tuple[IndexedEntry, date, date]]:
        """Find entries of target_type at this company that overlap [start, end].

        If query_is_advisory or the indexed entry is advisory, the match is
        automatic (no date overlap required). Advisory roles represent ongoing
        connections where introductions are possible at any time.

        Returns list of (entry, overlap_start, overlap_end) tuples.
        """
        results = []
        eff_end = _effective_end(end)
        for entry in self._index.get(company_key, []):
            if entry.person_type != target_type:
                continue
            if query_is_advisory or entry.is_advisory:
                # Advisory match — use the non-advisory side's date range
                if entry.is_advisory and not query_is_advisory:
                    results.append((entry, start, eff_end))
                elif query_is_advisory and not entry.is_advisory:
                    results.append((entry, entry.start_date, entry.end_date))
                else:
                    # Both advisory — use today as nominal overlap
                    today = date.today()
                    results.append((entry, today, today))
                continue
            overlap = compute_overlap(start, eff_end, entry.start_date, entry.end_date)
            if overlap:
                results.append((entry, overlap[0], overlap[1]))
        return results

    @property
    def company_count(self) -> int:
        return len(self._index)

    @property
    def entry_count(self) -> int:
        return sum(len(entries) for entries in self._index.values())

    @classmethod
    def build(
        cls,
        contact_histories: dict[str, list[WorkHistoryEntry]],
        lead_histories: dict[str, list[WorkHistoryEntry]],
    ) -> CompanyTimeIndex:
        """Build the index from grouped work history data.

        Args:
            contact_histories: person_id -> list of WorkHistoryEntry for contacts
            lead_histories: person_id -> list of WorkHistoryEntry for leads
        """
        from src.data.dealigence import normalize_company_name

        index = cls()

        for person_id, entries in contact_histories.items():
            for entry, effective_end in fill_end_dates(entries):
                if not entry.start_date and not entry.is_advisory:
                    continue
                if is_stealth_company(entry.employer_name):
                    continue
                # Use Dealigence ID as primary key, fall back to normalized name
                company_key = (
                    entry.employer_dealigence_id
                    or normalize_company_name(entry.employer_name)
                )
                if not company_key:
                    continue
                index.add(company_key, IndexedEntry(
                    person_id=person_id,
                    person_name=entry.person_name,
                    person_type="contact",
                    role_title=entry.role_title,
                    seniority=entry.seniority,
                    start_date=entry.start_date or date(2000, 1, 1),
                    end_date=effective_end,
                    is_advisory=entry.is_advisory,
                ))

        for person_id, entries in lead_histories.items():
            for entry, effective_end in fill_end_dates(entries):
                if not entry.start_date and not entry.is_advisory:
                    continue
                if is_stealth_company(entry.employer_name):
                    continue
                company_key = (
                    entry.employer_dealigence_id
                    or normalize_company_name(entry.employer_name)
                )
                if not company_key:
                    continue
                index.add(company_key, IndexedEntry(
                    person_id=person_id,
                    person_name=entry.person_name,
                    person_type="lead",
                    role_title=entry.role_title,
                    seniority=entry.seniority,
                    start_date=entry.start_date or date(2000, 1, 1),
                    end_date=effective_end,
                    is_advisory=entry.is_advisory,
                ))

        return index
