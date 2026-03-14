"""Investigator integration: run web research on contacts and leads.

Wraps the bundled `investigator` package to:
- Gather multi-source public web data about a person (DuckDuckGo + page fetch + LLM synthesis)
- Cache reports to ~/.vc_connections/reports/
- Extract structured work history from the prose report for storage in Notion
"""

from __future__ import annotations

import asyncio
import logging
import re
import threading
from pathlib import Path

from src.config import settings

logger = logging.getLogger(__name__)

# ── Cache ──────────────────────────────────────────────────────────────────────

_CACHE_DIR = Path.home() / ".vc_connections" / "reports"


def _cache_path(name: str) -> Path:
    safe = re.sub(r"[^\w\s-]", "", name).strip().replace(" ", "_").lower()
    return _CACHE_DIR / f"{safe}.md"


def get_cached_report(name: str) -> str | None:
    """Return cached report markdown for person, or None if not cached."""
    p = _cache_path(name)
    if p.exists():
        return p.read_text(encoding="utf-8")
    return None


def save_cached_report(name: str, report_md: str) -> None:
    """Save report markdown to the cache."""
    _CACHE_DIR.mkdir(parents=True, exist_ok=True)
    _cache_path(name).write_text(report_md, encoding="utf-8")


def delete_cached_report(name: str) -> None:
    """Delete cached report so next run fetches fresh data."""
    p = _cache_path(name)
    if p.exists():
        p.unlink()


# ── Runner ─────────────────────────────────────────────────────────────────────


def run_research(name: str, company: str | None = None, force_refresh: bool = False) -> str:
    """Run Investigator on a person and return the full markdown report.

    Uses cached report if available (unless force_refresh=True).
    Runs in a background thread to avoid conflicts with Streamlit's event loop.
    """
    if not force_refresh:
        cached = get_cached_report(name)
        if cached:
            logger.info("Returning cached report for %s", name)
            return cached

    from investigator.orchestrator import Orchestrator
    from investigator.config import InvestigatorConfig

    google_api_key = settings.google_api_key or None
    ollama_model = settings.ollama_model
    openai_api_key = settings.openai_api_key or None
    openai_model = settings.openai_model or "gpt-4o-mini"
    anthropic_api_key = settings.anthropic_api_key or None
    anthropic_model = settings.anthropic_model
    gemini_model = settings.gemini_model

    config = InvestigatorConfig(
        name=name,
        company=company or None,
        model=ollama_model,
        gemini_api_key=google_api_key,
        gemini_model=gemini_model,
        openai_api_key=openai_api_key,
        openai_model=openai_model,
        anthropic_api_key=anthropic_api_key,
        anthropic_model=anthropic_model,
        llm_provider=settings.llm_provider,
        output_path="",  # suppress file output
        use_cache=not force_refresh,
    )

    # Run asyncio in a dedicated thread to avoid event loop conflicts with Streamlit
    result: dict = {}

    def _run():
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            orchestrator = Orchestrator()
            result["report"] = loop.run_until_complete(orchestrator.run_and_return(config))
        except Exception as e:
            result["error"] = str(e)
        finally:
            loop.close()

    thread = threading.Thread(target=_run)
    thread.start()
    thread.join(timeout=120)

    if thread.is_alive():
        raise TimeoutError(f"Investigator timed out after 120s for {name}")

    if "error" in result:
        raise RuntimeError(f"Investigator failed: {result['error']}")

    report_md = result["report"]
    save_cached_report(name, report_md)
    logger.info("Research complete for %s (%d chars)", name, len(report_md))
    return report_md


# ── Work history extraction ────────────────────────────────────────────────────


def extract_work_history_from_report(report_md: str) -> list[dict]:
    """Extract structured work history positions from an Investigator report.

    Finds the Professional Profile section and passes it to the LLM parser
    to produce the same position format as LinkedIn enrichment.
    """
    from src.data.llm_parser import parse_linkedin_with_llm

    # Extract the Professional Profile section if present
    section_match = re.search(
        r"##\s+\d+\.\s+Professional Profile\n(.*?)(?=\n##\s|\Z)",
        report_md,
        re.DOTALL,
    )
    if section_match:
        text = section_match.group(1).strip()
    else:
        # Fallback: use the full report (LLM will find what it can)
        text = report_md

    if not text.strip():
        return []

    try:
        return parse_linkedin_with_llm(text)
    except Exception as e:
        logger.warning("Failed to extract work history from report: %s", e)
        return []
