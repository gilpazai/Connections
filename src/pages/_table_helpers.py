"""Shared table-building helpers for contacts and leads pages."""

from __future__ import annotations

from datetime import date

from src.models.contact import WorkHistoryEntry

N_POSITIONS = 5


def _format_period(start: date | None, end: date | None) -> str:
    s = str(start.year) if start else "?"
    e = "now" if end is None else str(end.year)
    return f"{s}–{e}"


def work_history_columns() -> list[str]:
    """Return the ordered list of position column names."""
    cols = []
    for i in range(1, N_POSITIONS + 1):
        cols += [f"Employer {i}", f"Title {i}", f"Period {i}"]
    return cols


def position_cells(
    entries: list[WorkHistoryEntry],
    enriched: bool,
) -> dict[str, str]:
    """Return a flat dict with up to N_POSITIONS positions for one table row.

    - Not enriched: all cells are empty string.
    - Enriched but fewer than N_POSITIONS entries: remaining cells are "N/A".
    - Entries are sorted most-recent first (current before previous, then by start date desc).
    """
    row: dict[str, str] = {}

    if not enriched:
        for col in work_history_columns():
            row[col] = ""
        return row

    # Sort: current (end=None) first, then most recent start date descending
    sorted_entries = sorted(
        entries,
        key=lambda e: (e.end_date is None, e.start_date or date.min),
        reverse=True,
    )

    for i in range(N_POSITIONS):
        idx = i + 1
        if i < len(sorted_entries):
            e = sorted_entries[i]
            row[f"Employer {idx}"] = e.employer_name
            row[f"Title {idx}"] = e.role_title
            row[f"Period {idx}"] = _format_period(e.start_date, e.end_date)
        else:
            row[f"Employer {idx}"] = "N/A"
            row[f"Title {idx}"] = "N/A"
            row[f"Period {idx}"] = "N/A"

    return row


def lookup_work_history(
    dealigence_id: str,
    name: str,
    grouped: dict[str, list[WorkHistoryEntry]],
) -> list[WorkHistoryEntry]:
    """Find work history entries for a person.

    Tries by Dealigence person ID first, then falls back to name.
    """
    if dealigence_id and dealigence_id in grouped:
        return grouped[dealigence_id]
    return grouped.get(name, [])
