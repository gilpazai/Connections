"""LinkedIn scraper that controls the user's running Chrome via AppleScript (macOS).

Opens a new tab in the existing Chrome session (already logged into LinkedIn),
waits for the page to load, scrolls to trigger lazy loading, extracts the
experience section text, and closes the tab.
No separate browser or login required.
"""

from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

_SCRAPE_DEBUG = os.environ.get("SCRAPE_DEBUG", "").lower() in ("1", "true", "yes")
_DEBUG_DIR = Path.home() / ".vc_connections" / "debug"


def _experience_url(linkedin_url: str) -> str:
    url = linkedin_url.strip().rstrip("/")
    if "/details/experience" not in url:
        url = url + "/details/experience/"
    return url


def _deduplicate_lines(text: str) -> str:
    """Remove consecutive duplicate lines from LinkedIn scraped text.

    LinkedIn renders each experience entry twice in the DOM (once visually,
    once for screen readers). This roughly halves the text size before it
    reaches the LLM, fitting more positions within the token limit.
    """
    lines = text.split("\n")
    deduped: list[str] = []
    prev: str | None = None
    for line in lines:
        if line != prev:
            deduped.append(line)
        prev = line
    return "\n".join(deduped)


def _validate_scraped_content(text: str) -> None:
    """Check that scraped text looks like a real LinkedIn experience page.

    Raises RuntimeError with a descriptive message for known failure modes.
    """
    stripped = text.strip()
    if len(stripped) < 200:
        raise RuntimeError(
            f"Scraped text too short ({len(stripped)} chars) — page likely failed to load. "
            "Make sure Google Chrome is running and you are logged into LinkedIn."
        )

    lower = stripped.lower()

    # Auth wall detection: LinkedIn shows "Sign in" + "Join now" when not logged in
    if "sign in" in lower and "join now" in lower:
        raise RuntimeError(
            "LinkedIn auth wall detected — you are not logged into LinkedIn in Chrome. "
            "Please log in to LinkedIn in your Chrome browser and try again."
        )

    # Error page detection
    if "page not found" in lower or "this page doesn't exist" in lower:
        raise RuntimeError(
            "LinkedIn returned a 'Page not found' error. "
            "Check that the LinkedIn URL is correct."
        )


def _save_debug_text(person_hint: str, text: str) -> None:
    """Save raw scraped text to a debug file when SCRAPE_DEBUG is enabled."""
    if not _SCRAPE_DEBUG:
        return
    try:
        _DEBUG_DIR.mkdir(parents=True, exist_ok=True)
        # Sanitize filename
        safe_name = "".join(c if c.isalnum() or c in "-_ " else "_" for c in person_hint)
        path = _DEBUG_DIR / f"{safe_name}_raw.txt"
        path.write_text(text, encoding="utf-8")
        logger.info("Debug: saved raw scraped text to %s", path)
    except Exception as e:
        logger.warning("Failed to save debug text: %s", e)


def scrape_linkedin_experience(linkedin_url: str, timeout_secs: int = 30) -> str:
    """Open the LinkedIn experience page in the running Chrome and return body text.

    Uses AppleScript to control the user's Chrome (already logged into LinkedIn).
    Opens a new tab, waits for full load, scrolls to trigger lazy loading,
    extracts the main content text, and closes the tab.
    The entire sequence runs in a single osascript call to avoid tab index races.

    Raises RuntimeError if Chrome is not running, not logged in, or page fails.
    """
    url = _experience_url(linkedin_url)
    logger.info("Scraping LinkedIn via Chrome: %s", url)

    # Run the entire workflow in one AppleScript:
    # open tab → poll readyState → poll for content → scroll to load lazy content
    # → extract main section text → close tab
    # Using a variable `t` to hold the tab reference avoids index-shift bugs.
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

    -- Stage 3: Scroll down to trigger lazy loading of all experience entries
    repeat 5 times
        execute t javascript "window.scrollBy(0, window.innerHeight)"
        delay 0.5
    end repeat
    delay 0.5

    -- Stage 4: Extract only the main content area (skip nav, sidebar, messaging)
    set pageText to execute t javascript "(function() {{ var main = document.querySelector('main'); return main ? main.innerText : document.body.innerText; }})()"
    close t
    return pageText
end tell'''

    r = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout_secs + 20,
    )

    if r.returncode != 0:
        raise RuntimeError(
            f"Could not scrape LinkedIn via Chrome: {r.stderr.strip()}\n"
            "Make sure Google Chrome is running and you are logged into LinkedIn."
        )

    raw_text = r.stdout

    # LinkedIn renders each experience entry twice: once visually, once for screen readers.
    # Deduplicate consecutive identical lines to roughly halve the text size before LLM.
    raw_text = _deduplicate_lines(raw_text)

    logger.info("Scraped %d chars from %s (after dedup)", len(raw_text), url)
    logger.debug("Scraped text preview (first 500 chars):\n%s", raw_text[:500])

    # Validate content before returning
    _validate_scraped_content(raw_text)

    # Save debug file if SCRAPE_DEBUG is enabled
    # Extract person hint from URL for filename
    person_hint = linkedin_url.strip().rstrip("/").split("/")[-1]
    if person_hint == "experience":
        parts = linkedin_url.strip().rstrip("/").split("/")
        person_hint = parts[-2] if len(parts) >= 2 else "unknown"
    _save_debug_text(person_hint, raw_text)

    return raw_text


def _activity_url(linkedin_url: str, activity_type: str) -> str:
    url = linkedin_url.strip().rstrip("/")
    if "/recent-activity" in url:
        url = url.split("/recent-activity")[0]
    return url + f"/recent-activity/{activity_type}/"

def scrape_linkedin_activity(linkedin_url: str, activity_type: str = "shares", timeout_secs: int = 30) -> str:
    """Open the LinkedIn activity page in Chrome and return body text."""
    url = _activity_url(linkedin_url, activity_type)
    logger.info("Scraping LinkedIn Activity (%s) via Chrome: %s", activity_type, url)

    script = f'''
tell application "Google Chrome"
    activate
    set t to make new tab at end of tabs of window 1 with properties {{URL:"{url}"}}
    set deadline to (current date) + {timeout_secs}
    repeat
        if (current date) > deadline then exit repeat
        delay 1
        try
            set s to execute t javascript "document.readyState"
            if s contains "complete" then exit repeat
        end try
    end repeat
    set contentDeadline to (current date) + 10
    repeat
        delay 0.5
        try
            set bodyLen to execute t javascript "document.body.innerText.length"
            if bodyLen > 1500 then exit repeat
        end try
        if (current date) > contentDeadline then exit repeat
    end repeat
    repeat 3 times
        execute t javascript "window.scrollBy(0, window.innerHeight)"
        delay 0.5
    end repeat
    delay 0.3
    set pageText to execute t javascript "var msg = document.querySelector('.msg-overlay-container'); if(msg) msg.remove(); var aside = document.querySelector('aside'); if(aside) aside.remove(); (function() {{ var main = document.querySelector('main'); return main ? main.innerText : document.body.innerText; }})()"
    close t
    return pageText
end tell'''

    r = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout_secs + 20,
    )

    if r.returncode != 0:
        raise RuntimeError(
            f"Could not scrape LinkedIn via Chrome: {r.stderr.strip()}\n"
            "Make sure Google Chrome is running and you are logged into LinkedIn."
        )

    return r.stdout
