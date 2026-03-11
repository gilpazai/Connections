"""LinkedIn scraper using Select All → Copy (Cmd+A / Cmd+C) via AppleScript.

Unlike the DOM-based scraper in linkedin_scraper.py, this one copies all
visible page text to the clipboard using keyboard shortcuts and reads it
back via `pbpaste`. Captures exactly what the user would see if they
manually selected all and copied.

Accepts the main profile URL and rewrites it to the /details/experience/
subpage to ensure full work history is captured.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from src.data.linkedin_scraper import _deduplicate_lines, _validate_scraped_content

logger = logging.getLogger(__name__)

_SCRAPE_DEBUG = os.environ.get("SCRAPE_DEBUG", "").lower() in ("1", "true", "yes")
_DEBUG_DIR = Path.home() / ".vc_connections" / "debug"


def _experience_url(linkedin_url: str) -> str:
    url = linkedin_url.strip().rstrip("/")
    if "/details/experience" not in url:
        url = url + "/details/experience/"
    return url


def _save_debug_text(person_hint: str, text: str) -> None:
    if not _SCRAPE_DEBUG:
        return
    try:
        _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in person_hint)
        path = _DEBUG_DIR / f"{safe_name}_clipboard_raw.txt"
        path.write_text(text, encoding="utf-8")
        logger.info("Debug: saved clipboard scraped text to %s", path)
    except Exception as e:
        logger.warning("Failed to save debug text: %s", e)


def scrape_profile_via_clipboard(linkedin_url: str, timeout_secs: int = 30) -> str:
    """Scrape a LinkedIn experience page by selecting all text and copying to clipboard.

    Accepts the main profile URL (e.g. linkedin.com/in/username) and rewrites
    it to the /details/experience/ subpage. Uses Cmd+A and Cmd+C via AppleScript
    then reads the clipboard with `pbpaste`.

    Requires Google Chrome to be running with an active LinkedIn session.
    Raises RuntimeError if Chrome is not available or scraping fails.
    """
    url = _experience_url(linkedin_url)
    logger.info("Scraping LinkedIn via clipboard: %s", url)

    # Escape single quotes in URL for AppleScript
    url_escaped = url.replace("'", "\\'")

    script = f'''
tell application "Google Chrome"
    activate
    set t to make new tab at end of tabs of window 1 with properties {{URL:"{url}"}}

    -- Stage 1: Wait for DOM ready (up to {timeout_secs}s)
    set deadline to (current date) + {timeout_secs}
    repeat
        if (current date) > deadline then exit repeat
        delay 1
        try
            set s to execute t javascript "document.readyState"
            if s contains "complete" then exit repeat
        end try
    end repeat

    -- Stage 2: Wait for meaningful content (up to 10s, threshold 1500 chars)
    set contentDeadline to (current date) + 10
    repeat
        delay 0.5
        try
            set bodyLen to execute t javascript "document.body.innerText.length"
            if bodyLen > 1500 then exit repeat
        end try
        if (current date) > contentDeadline then exit repeat
    end repeat

    -- Stage 3: Select all and copy to clipboard
    execute t javascript "window.focus()"
    delay 0.2
    tell application "System Events"
        keystroke "a" using command down
        delay 0.3
        keystroke "c" using command down
    end tell
    delay 0.3

    close t
end tell'''

    r = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout_secs + 30,
    )

    if r.returncode != 0:
        raise RuntimeError(
            f"AppleScript failed: {r.stderr.strip()}\n"
            "Make sure Google Chrome is running and you are logged into LinkedIn."
        )

    # Read clipboard via pbpaste
    pb = subprocess.run(["pbpaste"], capture_output=True, text=True)
    if pb.returncode != 0:
        raise RuntimeError(f"pbpaste failed: {pb.stderr.strip()}")

    raw_text = pb.stdout

    raw_text = _deduplicate_lines(raw_text)
    logger.info("Clipboard scraped %d chars from %s (after dedup)", len(raw_text), url)

    _validate_scraped_content(raw_text)

    person_hint = linkedin_url.strip().rstrip("/").split("/in/")[-1].split("/")[0]
    _save_debug_text(person_hint, raw_text)

    return raw_text
