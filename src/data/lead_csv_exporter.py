"""Export parsed LinkedIn profiles to CSV.

Outputs one row per work experience position, capturing the full career
history for each person.
"""

from __future__ import annotations

import csv
from pathlib import Path

_COLUMNS = [
    "Person Name",
    "Person Linkedin",
    "Company Name",
    "Employee Title",
    "Started At",
    "End Date",
    "Tenure (Years)",
    "Is Advisory",
]


def profiles_to_csv(
    profiles: list[dict],
    output_path: str,
    linkedin_urls: list[str] | None = None,
) -> int:
    """Write parsed profiles to CSV with one row per position.

    Args:
        profiles: List of dicts from parse_full_profile_with_llm(), each
                  containing "name" and "positions" list.
        output_path: Destination CSV file path.
        linkedin_urls: Optional list of source URLs (same order as profiles).

    Returns:
        Total number of rows written.
    """
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    row_count = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=_COLUMNS)
        writer.writeheader()

        for i, profile in enumerate(profiles):
            linkedin_url = ""
            if linkedin_urls and i < len(linkedin_urls):
                linkedin_url = linkedin_urls[i].strip().rstrip("/")
                if "/details/experience" in linkedin_url:
                    linkedin_url = linkedin_url.split("/details/experience")[0].rstrip("/")

            name = profile.get("name", "").strip()
            positions = profile.get("positions", [])

            for pos in positions:
                started_raw = pos.get("started_at") or ""
                started_fmt = ""
                if started_raw:
                    try:
                        parts = started_raw.split("-")
                        if len(parts) >= 2:
                            started_fmt = f"{parts[1]}/{parts[0]}"
                    except Exception:
                        started_fmt = started_raw

                ended_raw = pos.get("ended_at") or ""
                ended_fmt = ""
                if ended_raw:
                    try:
                        parts = ended_raw.split("-")
                        if len(parts) >= 2:
                            ended_fmt = f"{parts[1]}/{parts[0]}"
                    except Exception:
                        ended_fmt = ended_raw

                writer.writerow({
                    "Person Name": name,
                    "Person Linkedin": linkedin_url,
                    "Company Name": (pos.get("company") or "").strip(),
                    "Employee Title": (pos.get("title") or "").strip(),
                    "Started At": started_fmt,
                    "End Date": ended_fmt or "Present",
                    "Tenure (Years)": pos.get("tenure_years") or "",
                    "Is Advisory": "TRUE" if pos.get("is_advisory") else "FALSE",
                })
                row_count += 1

    return row_count
