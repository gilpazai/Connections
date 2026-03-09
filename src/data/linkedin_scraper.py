"""LinkedIn scraper that controls the user's running Chrome via AppleScript (macOS).

Opens a new tab in the existing Chrome session (already logged into LinkedIn),
waits for the page to load, extracts the body text, and closes the tab.
No separate browser or login required.
"""

from __future__ import annotations

import logging
import subprocess

logger = logging.getLogger(__name__)


def _experience_url(linkedin_url: str) -> str:
    url = linkedin_url.strip().rstrip("/")
    if "/details/experience" not in url:
        url = url + "/details/experience/"
    return url


def scrape_linkedin_experience(linkedin_url: str, timeout_secs: int = 30) -> str:
    """Open the LinkedIn experience page in the running Chrome and return body text.

    Uses AppleScript to control the user's Chrome (already logged into LinkedIn).
    Opens a new tab, waits for full load, extracts text, and closes the tab.
    The entire sequence runs in a single osascript call to avoid tab index races.

    Raises RuntimeError if Chrome is not running or the page fails to load.
    """
    url = _experience_url(linkedin_url)
    logger.info("Scraping LinkedIn via Chrome: %s", url)

    # Run the entire workflow in one AppleScript:
    # open tab → poll readyState → extra wait → extract text → close tab
    # Using a variable `t` to hold the tab reference avoids index-shift bugs.
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
    delay 2
    set pageText to execute t javascript "document.body.innerText"
    close t
    return pageText
end tell'''

    r = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout_secs + 15,
    )

    if r.returncode != 0:
        raise RuntimeError(
            f"Could not scrape LinkedIn via Chrome: {r.stderr.strip()}\n"
            "Make sure Google Chrome is running and you are logged into LinkedIn."
        )

    return r.stdout

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
    delay 3
    set pageText to execute t javascript "var msg = document.querySelector('.msg-overlay-container'); if(msg) msg.remove(); var aside = document.querySelector('aside'); if(aside) aside.remove(); document.body.innerText;"
    close t
    return pageText
end tell'''

    r = subprocess.run(
        ["osascript", "-e", script],
        capture_output=True,
        text=True,
        timeout=timeout_secs + 15,
    )

    if r.returncode != 0:
        raise RuntimeError(
            f"Could not scrape LinkedIn via Chrome: {r.stderr.strip()}\\n"
            "Make sure Google Chrome is running and you are logged into LinkedIn."
        )

    return r.stdout
