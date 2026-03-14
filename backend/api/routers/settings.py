"""Settings API router — connectivity checks and configuration."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from src.config import settings

router = APIRouter(prefix="/api/settings", tags=["settings"])


class ConnectivityStatus(BaseModel):
    notion: bool
    anthropic: bool
    gemini: bool
    openai: bool
    ollama: bool


class LLMConfig(BaseModel):
    provider: str
    model: str


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
    """Return current LLM provider and model."""
    provider = settings.llm_provider.lower()
    model_map = {
        "gemini": settings.gemini_model,
        "anthropic": settings.anthropic_model,
        "openai": settings.openai_model,
        "ollama": settings.ollama_model,
    }
    return LLMConfig(provider=provider, model=model_map.get(provider, ""))
