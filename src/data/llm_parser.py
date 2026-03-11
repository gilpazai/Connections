"""LLM-based LinkedIn profile parser.

Sends raw LinkedIn profile text to an LLM for structured work history
extraction. Replaces the brittle regex parser with natural language
understanding — handles messy text, grouped roles, and edge cases without
custom heuristics.

Provider is controlled by settings.llm_provider: "gemini" (default), "anthropic", "openai", or "ollama".
"""

from __future__ import annotations

import json
import logging

from src.config import settings
from src.data.advisory_titles import load_advisory_titles
from src.data.linkedin import is_advisory_role

logger = logging.getLogger(__name__)


def _build_system_prompt() -> str:
    titles_str = ", ".join(load_advisory_titles())
    return (
        "You are a structured data extractor. Given raw text copied from a LinkedIn profile page, "
        "extract the person's complete work history as a JSON array.\n\n"
        "For EACH position, return an object with these exact fields:\n"
        '- "employer_name": company name (string)\n'
        '- "title": job title (string)\n'
        '- "seniority": MUST be exactly one of these four strings — no other values are valid:\n'
        '  "founder" → any founder or co-founder role\n'
        '  "vp-c-level" → C-suite (CEO/CTO/CFO/CMO/COO/etc.), VP, SVP, EVP, Director, Head of, President, Partner, Principal, Managing Director, General Manager\n'
        '  "managerial" → Manager, Lead, Team Lead, Supervisor, Coordinator\n'
        '  "hands-on" → Engineer, Analyst, Associate, Consultant, Intern, and all other roles\n'
        '- "started_at": start date as ISO format "YYYY-MM-DD" (use first of month if only month/year given), or null if unknown\n'
        '- "ended_at": end date as ISO format "YYYY-MM-DD", or null if current/present\n'
        '- "tenure_years": duration as a decimal number (e.g. 2.5), or 0 if unknown\n'
        f'- "is_advisory": true ONLY for explicit board/advisory/investment roles '
        f"({titles_str}; for President, only when not Vice President). "
        f"MUST be false for all founder, co-founder, executive, manager, and employee roles.\n\n"
        "Rules:\n"
        "- The FIRST position in your output MUST be the person's most recent/current role — never omit it\n"
        "- Order all positions from most recent to oldest\n"
        "- For grouped roles (multiple titles at the same company), create a separate entry for each title\n"
        '- "employer_name" must be the company name from the job entry header, never text from the role description\n'
        "- Skip education, certifications, volunteer work, skills, and endorsements\n"
        "- If a field is genuinely unavailable, use null for dates and 0 for tenure_years\n"
        "- Return ONLY the JSON array, no markdown fences, no explanation"
    )


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
        contents=f"{_build_system_prompt()}\n\n{text}",
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
        system=_build_system_prompt(),
        messages=[{"role": "user", "content": text}],
    )
    return json.loads(_strip_fences(response.content[0].text))


def _parse_with_openai(text: str) -> list[dict]:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set in .env — required for OpenAI parsing")
    import httpx
    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": _build_system_prompt()},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
    }
    response = httpx.post(
        "https://api.openai.com/v1/chat/completions",
        headers={"Authorization": f"Bearer {settings.openai_api_key}"},
        json=payload,
        timeout=60.0,
    )
    response.raise_for_status()
    content = response.json()["choices"][0]["message"]["content"]
    return json.loads(_strip_fences(content))


def _parse_with_ollama(text: str) -> list[dict]:
    import httpx
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": _build_system_prompt()},
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


def parse_linkedin_with_llm(raw_text: str, max_positions: int = 25) -> list[dict]:
    """Parse raw LinkedIn profile text into structured positions using an LLM.

    Args:
        raw_text: Full text from a LinkedIn profile page (via Cmd+A or get_page_text).
        max_positions: Maximum positions to return.

    Returns:
        List of position dicts matching the enrich.py --store format.
    """
    provider = settings.llm_provider.lower()
    text = raw_text[:30000] if len(raw_text) > 30000 else raw_text

    if provider == "gemini":
        positions = _parse_with_gemini(text)
    elif provider == "anthropic":
        positions = _parse_with_anthropic(text)
    elif provider == "openai":
        positions = _parse_with_openai(text)
    elif provider == "ollama":
        positions = _parse_with_ollama(text)
    else:
        raise RuntimeError(f"Unknown LLM_PROVIDER '{provider}' — use 'gemini', 'anthropic', 'openai', or 'ollama'")

    # Post-process: enforce is_advisory via our regex as a safety net
    for pos in positions:
        if not pos.get("is_advisory") and is_advisory_role(pos.get("title", "")):
            pos["is_advisory"] = True

    # Post-process: validate employer names exist in source text
    validated = _validate_employers(positions, text)

    # Post-process: enforce valid seniority values
    valid_seniorities = {"founder", "vp-c-level", "managerial", "hands-on"}
    for pos in validated:
        if pos.get("seniority", "").lower() not in valid_seniorities:
            pos["seniority"] = "hands-on"
        else:
            pos["seniority"] = pos["seniority"].lower()

    logger.info("LLM parser (%s) extracted %d positions (%d after validation)",
                provider, len(positions), len(validated))
    return validated[:max_positions]


def _validate_employers(positions: list[dict], source_text: str) -> list[dict]:
    """Remove positions whose employer_name doesn't appear in the source text.

    This catches LLM hallucinations where the model invents company names
    that aren't in the original LinkedIn profile, as well as cases where
    the LLM mistakes a country/location label for an employer name.
    """
    # Country/location names and other non-company strings that appear in LinkedIn text
    # but are never valid employer names
    _INVALID_EMPLOYERS = {
        "israel", "united states", "usa", "uk", "united kingdom", "canada",
        "australia", "germany", "france", "india", "china", "singapore",
        "tel aviv", "new york", "san francisco", "london", "berlin",
        "remote", "hybrid", "on-site", "contract", "freelance",
    }

    source_lower = source_text.lower()
    validated = []
    for pos in positions:
        employer = pos.get("employer_name", "").strip()
        if not employer:
            continue
        # Reject location/country strings masquerading as employer names
        if employer.lower() in _INVALID_EMPLOYERS:
            logger.warning(
                "Dropping invalid employer '%s' (title: '%s') — "
                "looks like a location/country, not a company name",
                employer, pos.get("title", ""),
            )
            continue
        # Check if employer name (or a substantial substring) appears in source
        if _employer_in_source(employer, source_lower):
            validated.append(pos)
        else:
            logger.warning(
                "Dropping hallucinated employer '%s' (title: '%s') — "
                "not found in LinkedIn source text",
                employer, pos.get("title", ""),
            )
    return validated


def _employer_in_source(employer: str, source_lower: str) -> bool:
    """Check if an employer name appears in the source text.

    Handles minor variations: full name match, or matching the longest word
    (>3 chars) in the employer name as a fallback for abbreviations.
    """
    emp_lower = employer.lower().strip()

    # Direct match
    if emp_lower in source_lower:
        return True

    # Try without common suffixes (Ltd., Inc., etc.)
    for suffix in ("ltd.", "ltd", "inc.", "inc", "llc", "corp.", "corp"):
        stripped = emp_lower.replace(suffix, "").strip().rstrip(".,")
        if stripped and len(stripped) > 2 and stripped in source_lower:
            return True

    # Try matching the longest significant word (>3 chars) as fallback
    # e.g. "Spinframe Technologies" -> check "spinframe"
    words = [w for w in emp_lower.split() if len(w) > 3]
    if words:
        longest = max(words, key=len)
        if longest in source_lower:
            return True

    return False
