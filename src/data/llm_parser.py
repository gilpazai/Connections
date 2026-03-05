"""LLM-based LinkedIn profile parser.

Sends raw LinkedIn profile text to an LLM for structured work history
extraction. Replaces the brittle regex parser with natural language
understanding — handles messy text, grouped roles, and edge cases without
custom heuristics.

Provider is controlled by settings.llm_provider: "gemini" (default), "anthropic", or "ollama".
"""

from __future__ import annotations

import json
import logging

from src.config import settings
from src.data.linkedin import is_advisory_role

logger = logging.getLogger(__name__)

_SYSTEM_PROMPT = """\
You are a structured data extractor. Given raw text copied from a LinkedIn profile page, \
extract the person's complete work history as a JSON array.

For EACH position, return an object with these exact fields:
- "employer_name": company name (string)
- "title": job title (string)
- "seniority": one of "founder", "vp-c-level", "managerial", "hands-on"
  - founder: founder, co-founder, founding team
  - vp-c-level: chief/CxO, VP, SVP, EVP, director, head of, president, partner, principal, managing director, general manager
  - managerial: manager, lead, team lead, supervisor, coordinator
  - hands-on: everything else (engineer, analyst, associate, consultant, etc.)
- "started_at": start date as ISO format "YYYY-MM-DD" (use first of month if only month/year given), or null if unknown
- "ended_at": end date as ISO format "YYYY-MM-DD", or null if current/present
- "tenure_years": duration as a decimal number (e.g. 2.5), or 0 if unknown
- "is_advisory": true if the title indicates a board/advisory/investment role \
(investor, board member, board observer, chairman, president (not vice president), advisor, adviser), false otherwise

Rules:
- Order positions from most recent to oldest
- For grouped roles (multiple titles at the same company), create a separate entry for each title
- Skip education, certifications, volunteer work, skills, and endorsements
- If a field is genuinely unavailable, use null for dates and 0 for tenure_years
- Return ONLY the JSON array, no markdown fences, no explanation"""


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = -1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])
    return text


def _parse_with_gemini(text: str) -> list[dict]:
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY not set in .env — required for Gemini parsing")
    from google import genai
    client = genai.Client(api_key=settings.google_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=f"{_SYSTEM_PROMPT}\n\n{text}",
    )
    return json.loads(_strip_fences(response.text))


def _parse_with_anthropic(text: str) -> list[dict]:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env — required for Anthropic parsing")
    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": text}],
    )
    return json.loads(_strip_fences(response.content[0].text))


def _parse_with_ollama(text: str) -> list[dict]:
    import httpx
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "stream": False,
    }
    response = httpx.post(
        f"{settings.ollama_base_url}/api/chat",
        json=payload,
        timeout=120.0,
    )
    response.raise_for_status()
    content = response.json()["message"]["content"]
    return json.loads(_strip_fences(content))


def parse_linkedin_with_llm(raw_text: str, max_positions: int = 20) -> list[dict]:
    """Parse raw LinkedIn profile text into structured positions using an LLM.

    Args:
        raw_text: Full text from a LinkedIn profile page (via Cmd+A or get_page_text).
        max_positions: Maximum positions to return.

    Returns:
        List of position dicts matching the enrich.py --store format.
    """
    provider = settings.llm_provider.lower()
    text = raw_text[:15000] if len(raw_text) > 15000 else raw_text

    if provider == "gemini":
        positions = _parse_with_gemini(text)
    elif provider == "anthropic":
        positions = _parse_with_anthropic(text)
    elif provider == "ollama":
        positions = _parse_with_ollama(text)
    else:
        raise RuntimeError(f"Unknown LLM_PROVIDER '{provider}' — use 'gemini', 'anthropic', or 'ollama'")

    # Post-process: enforce is_advisory via our regex as a safety net
    for pos in positions:
        if not pos.get("is_advisory") and is_advisory_role(pos.get("title", "")):
            pos["is_advisory"] = True

    logger.info("LLM parser (%s) extracted %d positions", provider, len(positions))
    return positions[:max_positions]
