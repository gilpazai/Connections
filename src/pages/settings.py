"""Settings page: configuration, connectivity status, data management."""

from __future__ import annotations

import os

import streamlit as st

from src.config import settings
from src.engine.rules.registry import create_default_registry

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")

_GEMINI_MODELS = [
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
]

_ANTHROPIC_MODELS = [
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-5-20251001",
    "claude-opus-4-5-20251001",
]

st.title("Settings")

# ── API Connectivity Status ──────────────────────────────────────────────────
st.subheader("API Connectivity")

col1, col2, col3, col4 = st.columns(4)
with col1:
    notion_ok = bool(settings.notion_token and settings.notion_contacts_db_id)
    st.metric("Notion", "Connected" if notion_ok else "Not configured")
    if not notion_ok:
        st.caption("Set NOTION_TOKEN and DB IDs in .env")
with col2:
    anthropic_ok = bool(settings.anthropic_api_key)
    st.metric("Anthropic", "Connected" if anthropic_ok else "Not configured")
    if not anthropic_ok:
        st.caption("Set ANTHROPIC_API_KEY in .env")
with col3:
    gemini_ok = bool(settings.google_api_key)
    st.metric("Gemini", "Connected" if gemini_ok else "Not configured")
    if not gemini_ok:
        st.caption("Set GOOGLE_API_KEY in .env")
with col4:
    try:
        import httpx
        r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
        ollama_ok = r.status_code == 200
    except Exception:
        ollama_ok = False
    st.metric("Ollama", "Running" if ollama_ok else "Not running")
    if not ollama_ok:
        st.caption(f"Start Ollama at {settings.ollama_base_url}")

st.divider()

# ── LLM Configuration ────────────────────────────────────────────────────────
st.subheader("LLM Configuration")
st.caption("Select which model to use for LinkedIn enrichment parsing. Changes are saved to .env and take effect on next app restart.")

_PROVIDERS = ["gemini", "anthropic", "ollama"]
current_provider = settings.llm_provider.lower()
provider_idx = _PROVIDERS.index(current_provider) if current_provider in _PROVIDERS else 0

col_p, col_m = st.columns(2)

with col_p:
    new_provider = st.selectbox(
        "Provider",
        _PROVIDERS,
        index=provider_idx,
        format_func=lambda p: {"gemini": "Gemini (Google)", "anthropic": "Anthropic (Claude)", "ollama": "Ollama (Local)"}[p],
    )

with col_m:
    if new_provider == "gemini":
        model_options = _GEMINI_MODELS
        current_model = settings.gemini_model
        model_key = "GEMINI_MODEL"
    elif new_provider == "anthropic":
        model_options = _ANTHROPIC_MODELS
        current_model = settings.anthropic_model
        model_key = "ANTHROPIC_MODEL"
    else:  # ollama
        if ollama_ok:
            try:
                import httpx, json
                r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
                model_options = [m["name"] for m in r.json().get("models", [])]
            except Exception:
                model_options = []
        else:
            model_options = []
        if not model_options:
            model_options = [settings.ollama_model]
        current_model = settings.ollama_model
        model_key = "OLLAMA_MODEL"

    model_idx = model_options.index(current_model) if current_model in model_options else 0
    new_model = st.selectbox("Model", model_options, index=model_idx)

active_label = f"**Active:** `{settings.llm_provider}` / `{current_model}`"
if new_provider != current_provider or new_model != current_model:
    active_label += f"  →  `{new_provider}` / `{new_model}` *(unsaved)*"
st.caption(active_label)

if st.button("Save LLM Settings", type="primary"):
    from dotenv import set_key
    env_path = os.path.abspath(_ENV_PATH)
    set_key(env_path, "LLM_PROVIDER", new_provider)
    set_key(env_path, model_key, new_model)
    st.success(f"Saved `LLM_PROVIDER={new_provider}` and `{model_key}={new_model}` to .env — restart the app to apply.")

st.divider()

# ── Active Matching Rules ────────────────────────────────────────────────────
st.subheader("Active Matching Rules")
registry = create_default_registry()
for rule in registry.get_all():
    st.markdown(f"- **{rule.name}**: {rule.description}")
st.caption(
    f"{len(registry)} rule(s) active. "
    "Add new rules in src/engine/rules/ and register them in registry.py."
)

st.divider()

# ── Configuration ────────────────────────────────────────────────────────────
st.subheader("Configuration")
st.json({"log_level": settings.log_level})
st.caption("Edit .env to change these values, then restart the app.")

st.divider()

# ── Notion Database IDs ───────────────────────────────────────────────────────
st.subheader("Notion Database IDs")
db_config = {
    "Contacts DB": settings.notion_contacts_db_id or "(not set)",
    "Leads DB": settings.notion_leads_db_id or "(not set)",
    "Work History DB": settings.notion_work_history_db_id or "(not set)",
    "Matches DB": settings.notion_matches_db_id or "(not set)",
}
for label, db_id in db_config.items():
    st.text_input(label, value=db_id, disabled=True)
