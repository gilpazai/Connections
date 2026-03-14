"""Settings API router — connectivity checks and LLM configuration."""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import APIRouter
from pydantic import BaseModel

from src.config import settings

router = APIRouter(prefix="/api/settings", tags=["settings"])

# Known model lists per provider (curated, no live API calls needed)
_MODELS: dict[str, list[str]] = {
    "gemini": [
        "gemini-2.5-flash",
        "gemini-2.5-pro",
        "gemini-2.0-flash",
        "gemini-1.5-flash",
        "gemini-1.5-pro",
    ],
    "anthropic": [
        "claude-haiku-4-5-20251001",
        "claude-sonnet-4-5-20251022",
        "claude-3-7-sonnet-20250219",
        "claude-3-5-sonnet-20241022",
        "claude-3-5-haiku-20241022",
        "claude-3-opus-20240229",
    ],
    "openai": [
        "gpt-4o-mini",
        "gpt-4o",
        "o1-mini",
        "o3-mini",
        "o4-mini",
        "gpt-4.5-preview",
    ],
    "ollama": [
        "llama3.2:3b",
        "llama3.2:1b",
        "llama3.1:8b",
        "mistral:7b",
        "qwen2.5:7b",
    ],
}


class ConnectivityStatus(BaseModel):
    notion: bool
    anthropic: bool
    gemini: bool
    openai: bool
    ollama: bool


class LLMConfig(BaseModel):
    provider: str
    model: str
    available_providers: list[str]
    available_models: dict[str, list[str]]


class UpdateLLMRequest(BaseModel):
    provider: str
    model: str


def _write_env(key: str, value: str) -> None:
    """Persist a key=value to the project .env file."""
    env_path = Path(__file__).parents[3] / ".env"
    try:
        from dotenv import set_key
        set_key(str(env_path), key, value)
    except Exception:
        pass  # best-effort; in-memory update already applied


@router.get("/connectivity")
def check_connectivity() -> ConnectivityStatus:
    """Check which API keys are configured."""
    ollama_ok = False
    try:
        import httpx
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
        ollama_ok = r.status_code == 200
    except Exception:
        pass

    return ConnectivityStatus(
        notion=bool(settings.notion_token and settings.notion_contacts_db_id),
        anthropic=bool(settings.anthropic_api_key),
        gemini=bool(settings.google_api_key),
        openai=bool(settings.openai_api_key),
        ollama=ollama_ok,
    )


@router.get("/llm")
def get_llm_config() -> LLMConfig:
    """Return current LLM provider, model, and available options."""
    provider = settings.llm_provider.lower()
    model_map = {
        "gemini": settings.gemini_model,
        "anthropic": settings.anthropic_model,
        "openai": settings.openai_model,
        "ollama": settings.ollama_model,
    }
    current_model = model_map.get(provider, "")

    # Ensure current model appears in the list even if not in curated list
    models_for_provider = list(_MODELS.get(provider, []))
    if current_model and current_model not in models_for_provider:
        models_for_provider.insert(0, current_model)

    return LLMConfig(
        provider=provider,
        model=current_model,
        available_providers=list(_MODELS.keys()),
        available_models={p: list(m) for p, m in _MODELS.items()},
    )


@router.patch("/llm")
def update_llm_config(body: UpdateLLMRequest) -> LLMConfig:
    """Update LLM provider and model — persists to .env and updates runtime state."""
    provider = body.provider.lower()
    model = body.model

    # Update in-memory settings so running processes pick up changes immediately
    settings.llm_provider = provider
    if provider == "gemini":
        settings.gemini_model = model
        _write_env("GEMINI_MODEL", model)
    elif provider == "anthropic":
        settings.anthropic_model = model
        _write_env("ANTHROPIC_MODEL", model)
    elif provider == "openai":
        settings.openai_model = model
        _write_env("OPENAI_MODEL", model)
    elif provider == "ollama":
        settings.ollama_model = model
        _write_env("OLLAMA_MODEL", model)

    _write_env("LLM_PROVIDER", provider)

    # Also update process env so any fresh imports pick it up
    os.environ["LLM_PROVIDER"] = provider

    return get_llm_config()
