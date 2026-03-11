"""LLM-based LinkedIn full profile parser.

Extracts ALL work experience positions from a LinkedIn profile's experience
page text. Advisory role detection is delegated to the LLM using the configured
advisory titles from settings.
"""

from __future__ import annotations

import json
import logging

from src.config import settings
from src.data.advisory_titles import load_advisory_titles

logger = logging.getLogger(__name__)


def _build_profile_prompt(advisory_titles: list[str], linkedin_url: str) -> str:
    titles_str = ", ".join(advisory_titles) if advisory_titles else "Advisor, Board Member, Investor"
    slug = linkedin_url.strip().rstrip("/").split("/in/")[-1].split("/")[0]
    return (
        "You are a structured data extractor. Given raw text copied from a LinkedIn profile's "
        "experience page, extract the person's name and ALL work experience positions.\n\n"
        "IMPORTANT — Name disambiguation:\n"
        "The text includes navigation elements and messaging UI from the logged-in user's LinkedIn session. "
        f'The profile being viewed belongs to the URL slug "{slug}". '
        "The profile owner's name appears prominently in the profile header (before the headline/tagline), "
        "NOT in the navigation bar or messaging section. Extract the profile OWNER's name, not the logged-in user's.\n\n"
        "Return a JSON object with:\n"
        '- "name": the profile owner\'s full name (string)\n'
        '- "positions": array of ALL work positions, most recent first, each with:\n'
        '  - "company": company name (string)\n'
        '  - "title": job title (string)\n'
        '  - "started_at": start date as "YYYY-MM-DD" (use first of month if only month/year), or null\n'
        '  - "ended_at": end date as "YYYY-MM-DD" (use first of month), or null if current/present\n'
        '  - "tenure_years": duration as a decimal number (e.g. 2.5), or 0 if unknown\n'
        '  - "is_advisory": true if the role is an advisory, board, or investment role\n\n'
        f"Advisory role detection — use your judgment:\n"
        f'The following title keywords indicate advisory/board/investment roles: {titles_str}\n'
        f"Flag is_advisory=true for any role whose title matches or is semantically similar to these "
        f"(e.g. 'Venture Advisor' matches 'Advisor', 'Board Director' matches 'Board Member'). "
        f"Standard executive and employee roles are NOT advisory.\n\n"
        "Rules:\n"
        "- Extract EVERY position listed under Experience — do not skip any\n"
        "- Some companies have multiple roles listed as sub-positions — extract each as a separate entry\n"
        "- Ignore education, certifications, volunteer work, skills, and 'More profiles for you' sections\n"
        "- Return ONLY the JSON object, no markdown fences, no explanation"
    )


def _strip_fences(text: str) -> str:
    text = text.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        end = -1 if lines[-1].strip() == "```" else len(lines)
        text = "\n".join(lines[1:end])
    return text


def _parse_with_gemini(text: str, prompt: str) -> dict:
    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY not set in .env — required for Gemini parsing")
    from google import genai
    client = genai.Client(api_key=settings.google_api_key)
    response = client.models.generate_content(
        model=settings.gemini_model,
        contents=f"{prompt}\n\n{text}",
    )
    return json.loads(_strip_fences(response.text))


def _parse_with_anthropic(text: str, prompt: str) -> dict:
    if not settings.anthropic_api_key:
        raise RuntimeError("ANTHROPIC_API_KEY not set in .env — required for Anthropic parsing")
    import anthropic
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    response = client.messages.create(
        model=settings.anthropic_model,
        max_tokens=4096,
        system=prompt,
        messages=[{"role": "user", "content": text}],
    )
    return json.loads(_strip_fences(response.content[0].text))


def _parse_with_openai(text: str, prompt: str) -> dict:
    if not settings.openai_api_key:
        raise RuntimeError("OPENAI_API_KEY not set in .env — required for OpenAI parsing")
    import httpx
    payload = {
        "model": settings.openai_model,
        "messages": [
            {"role": "system", "content": prompt},
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


def _parse_with_ollama(text: str, prompt: str) -> dict:
    import httpx
    payload = {
        "model": settings.ollama_model,
        "messages": [
            {"role": "system", "content": prompt},
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


def parse_full_profile_with_llm(raw_text: str, linkedin_url: str = "") -> dict:
    """Extract all positions from raw LinkedIn experience page text.

    Returns:
        {
            "name": str,
            "positions": [
                {
                    "company": str,
                    "title": str,
                    "started_at": str | None,
                    "ended_at": str | None,
                    "tenure_years": float,
                    "is_advisory": bool,
                },
                ...
            ]
        }
    """
    advisory_titles = load_advisory_titles()
    prompt = _build_profile_prompt(advisory_titles, linkedin_url)
    provider = settings.llm_provider.lower()
    text = raw_text[:30000] if len(raw_text) > 30000 else raw_text

    logger.info("Parsing profile with LLM (%s), %d chars", provider, len(text))

    if provider == "gemini":
        result = _parse_with_gemini(text, prompt)
    elif provider == "anthropic":
        result = _parse_with_anthropic(text, prompt)
    elif provider == "openai":
        result = _parse_with_openai(text, prompt)
    elif provider == "ollama":
        result = _parse_with_ollama(text, prompt)
    else:
        raise RuntimeError(
            f"Unknown LLM_PROVIDER '{provider}' — use 'gemini', 'anthropic', 'openai', or 'ollama'"
        )

    positions = result.get("positions", [])
    logger.info(
        "Parsed profile: name=%r, %d positions",
        result.get("name"),
        len(positions),
    )
    return result
