#!/usr/bin/env python3
"""Scrape LinkedIn profiles and export all positions to CSV.

Usage:
    python scrape_to_csv.py URL1 [URL2 ...]  [--output leads.csv]
    python scrape_to_csv.py --file urls.txt   [--output leads.csv]

Each URL should be a LinkedIn profile URL (linkedin.com/in/username).
The script opens each profile in Chrome, copies all visible text via
Cmd+A / Cmd+C, passes the text to the configured LLM, and writes ALL
work experience positions to CSV.

Requires:
    - Google Chrome running and logged into LinkedIn
    - LLM_PROVIDER and matching API key set in .env
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Scrape LinkedIn profiles → CSV with all positions"
    )
    parser.add_argument(
        "urls",
        nargs="*",
        metavar="URL",
        help="One or more LinkedIn profile URLs",
    )
    parser.add_argument(
        "--file",
        metavar="FILE",
        help="Text file with one LinkedIn URL per line",
    )
    parser.add_argument(
        "--output",
        default="scraped_leads.csv",
        metavar="OUTPUT",
        help="Output CSV path (default: scraped_leads.csv)",
    )
    args = parser.parse_args()

    # Collect URLs
    urls: list[str] = list(args.urls)
    if args.file:
        file_path = Path(args.file)
        if not file_path.exists():
            print(f"ERROR: File not found: {args.file}", file=sys.stderr)
            sys.exit(1)
        for line in file_path.read_text().splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                urls.append(line)

    if not urls:
        parser.print_help()
        sys.exit(1)

    # Import here so .env is loaded via src.config before use
    from src.data.linkedin_profile_parser import parse_full_profile_with_llm
    from src.data.lead_csv_exporter import profiles_to_csv
    from src.config import settings

    if settings.scraper_method.lower() == "dom":
        from src.data.linkedin_scraper import scrape_linkedin_experience as scrape_fn
        scraper_label = "DOM (JavaScript)"
    else:
        from src.data.linkedin_clipboard_scraper import scrape_profile_via_clipboard as scrape_fn
        scraper_label = "Clipboard (Cmd+A/Cmd+C)"

    print(f"Provider : {settings.llm_provider} / {_active_model(settings)}")
    print(f"Scraper  : {scraper_label}")
    print(f"Profiles : {len(urls)}")
    print(f"Output   : {args.output}")
    print()

    profiles: list[dict] = []
    successful_urls: list[str] = []
    failures: list[tuple[str, str]] = []

    for i, url in enumerate(urls, 1):
        print(f"[{i}/{len(urls)}] {url}")
        try:
            print("  Scraping...", end="", flush=True)
            raw_text = scrape_fn(url)
            print(f" {len(raw_text):,} chars")

            print("  Parsing with LLM...", end="", flush=True)
            profile = parse_full_profile_with_llm(raw_text, linkedin_url=url)
            name = profile.get("name") or "(unknown)"
            positions = profile.get("positions", [])
            print(f" {name} ({len(positions)} positions)")
            for pos in positions:
                advisory = " [advisory]" if pos.get("is_advisory") else ""
                print(f"    - {pos.get('title', '?')} @ {pos.get('company', '?')}{advisory}")

            profiles.append(profile)
            successful_urls.append(url)

        except Exception as e:
            print(f" FAILED: {e}")
            failures.append((url, str(e)))

    if not profiles:
        print("\nNo profiles scraped successfully. No output file written.")
        sys.exit(1)

    total_rows = profiles_to_csv(profiles, args.output, linkedin_urls=successful_urls)

    total_positions = sum(len(p.get("positions", [])) for p in profiles)
    print(f"\n--- Wrote {total_rows} rows ({len(profiles)} people, {total_positions} positions) to {args.output}")
    if failures:
        print(f"--- {len(failures)} failure(s):")
        for url, err in failures:
            print(f"  {url}: {err}")


def _active_model(settings) -> str:
    provider = settings.llm_provider.lower()
    if provider == "gemini":
        return settings.gemini_model
    if provider == "anthropic":
        return settings.anthropic_model
    if provider == "openai":
        return settings.openai_model
    if provider == "ollama":
        return settings.ollama_model
    return "?"


if __name__ == "__main__":
    main()
