"""LinkedIn scraper that controls the user's running Chrome via AppleScript (macOS).

Opens a new tab in the existing Chrome session (already logged into LinkedIn),
waits for the page to load, extracts the body text, and closes the tab.
No separate browser or login required.
"""

from __future__ import annotations

import logging
import subprocess
import time

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

    Raises RuntimeError if Chrome is not running or the tab cannot be opened.
    """
    url = _experience_url(linkedin_url)
    logger.info("Scraping LinkedIn via Chrome: %s", url)

    # Open a new tab and capture its index in the frontmost window
    open_script = f'''
tell application "Google Chrome"
    activate
    tell window 1
        set t to make new tab with properties {{URL:"{url}"}}
        return index of t
    end tell
end tell'''

    r = subprocess.run(["osascript", "-e", open_script], capture_output=True, text=True)
    if r.returncode != 0:
        raise RuntimeError(
            f"Could not open a Chrome tab: {r.stderr.strip()}\n"
            "Make sure Google Chrome is running and you are logged into LinkedIn."
        )
    tab_idx = r.stdout.strip()

    # Poll until document.readyState == "complete"
    check_script = f'''
tell application "Google Chrome"
    tell window 1
        tell tab {tab_idx}
            execute javascript "document.readyState"
        end tell
    end tell
end tell'''

    deadline = time.time() + timeout_secs
    while time.time() < deadline:
        time.sleep(1)
        r = subprocess.run(["osascript", "-e", check_script], capture_output=True, text=True)
        if "complete" in r.stdout:
            break

    # Brief extra wait for LinkedIn's dynamic content to render
    time.sleep(2)

    # Extract full body text
    get_script = f'''
tell application "Google Chrome"
    tell window 1
        tell tab {tab_idx}
            execute javascript "document.body.innerText"
        end tell
    end tell
end tell'''

    r = subprocess.run(["osascript", "-e", get_script], capture_output=True, text=True, check=True)
    text = r.stdout

    # Close the tab
    close_script = f'''
tell application "Google Chrome"
    tell window 1
        close tab {tab_idx}
    end tell
end tell'''
    subprocess.run(["osascript", "-e", close_script])

    return text
