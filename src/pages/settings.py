"""Settings page: configuration, connectivity status, data management."""

from __future__ import annotations

import os

import streamlit as st

from src.config import settings
from src.engine.rules.registry import create_default_registry

_ENV_PATH = os.path.join(os.path.dirname(__file__), "..", "..", ".env")

_GEMINI_MODELS = [
    "gemini-2.5-pro",
    "gemini-2.5-flash",
    "gemini-2.0-flash",
    "gemini-2.0-flash-lite",
    "gemini-1.5-pro",
    "gemini-1.5-flash",
]

_ANTHROPIC_MODELS = [
    "claude-3-7-sonnet-20250219",
    "claude-3-5-sonnet-20241022",
    "claude-3-5-haiku-20241022",
    "claude-3-opus-20240229",
    "claude-haiku-4-5-20251001",
    "claude-sonnet-4-5-20251001",
    "claude-opus-4-5-20251001",
]

_OPENAI_MODELS = [
    "gpt-4o-mini",
    "gpt-4o",
    "o3-mini",
    "o1-mini",
    "o1",
    "gpt-4.5-preview",
    "gpt-4-turbo",
    "gpt-3.5-turbo",
]

# OpenAI pricing: (input_cost_per_1M, output_cost_per_1M)
_OPENAI_PRICING = {
    "gpt-4o-mini":     (0.15,   0.60),
    "gpt-4o":          (2.50,  10.00),
    "o3-mini":         (1.10,   4.40),
    "o1-mini":         (1.10,   4.40),
    "o1":              (15.00, 60.00),
    "gpt-4.5-preview": (75.00, 150.00),
    "gpt-4-turbo":     (10.00,  30.00),
    "gpt-3.5-turbo":   (0.50,   1.50),
}


def _fetch_openai_models(api_key: str) -> tuple[list[str], str]:
    try:
        import openai
        client = openai.OpenAI(api_key=api_key)
        skip = ("realtime", "audio", "instruct", "tts", "whisper", "dall-e",
                "embedding", "moderation", "babbage", "davinci", "search")
        prefixes = ("gpt-", "o1", "o3", "o4")
        models = sorted(
            m.id for m in client.models.list().data
            if any(m.id.startswith(p) for p in prefixes)
            and not any(t in m.id for t in skip)
        )
        return models, ""
    except Exception as e:
        return [], str(e)


def _fetch_gemini_models(api_key: str) -> tuple[list[str], str]:
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        models = sorted(
            m.name.replace("models/", "")
            for m in genai.list_models()
            if "generateContent" in (m.supported_generation_methods or [])
            and "gemini" in m.name.lower()
        )
        return models, ""
    except Exception as e:
        return [], str(e)


def _fetch_anthropic_models(api_key: str) -> tuple[list[str], str]:
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        models = sorted(m.id for m in client.models.list().data)
        return models, ""
    except Exception as e:
        return [], str(e)

# Estimated token usage per enrichment (average LinkedIn profile)
_TOKENS_PER_ENRICHMENT = {
    "input": 7000,      # LinkedIn text + system prompt
    "output": 1500,     # JSON positions + validation overhead
}

st.title("Settings")

# ── Tabs ─────────────────────────────────────────────────────────────────────

tab_connectivity, tab_llm, tab_rules, tab_data, tab_advanced = st.tabs([
    "Connectivity", "LLM & Enrichment", "Matching Rules", "Data Management", "Advanced",
])

# ── Tab 1: Connectivity ─────────────────────────────────────────────────────

with tab_connectivity:
    st.subheader("API Connectivity")

    col1, col2, col3, col4, col5 = st.columns(5)
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
        openai_ok = bool(settings.openai_api_key)
        st.metric("OpenAI", "Connected" if openai_ok else "Not configured")
        if not openai_ok:
            st.caption("Set OPENAI_API_KEY in .env")
    with col5:
        try:
            import httpx
            r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
            ollama_ok = r.status_code == 200
        except Exception:
            ollama_ok = False
        st.metric("Ollama", "Running" if ollama_ok else "Not running")
        if not ollama_ok:
            st.caption(f"Start Ollama at {settings.ollama_base_url}")

# ── Tab 2: LLM & Enrichment ─────────────────────────────────────────────────

with tab_llm:
    st.subheader("LLM Configuration")
    st.caption("Select which model to use for LinkedIn enrichment parsing. Changes are saved to .env and take effect on next app restart.")

    _PROVIDERS = ["gemini", "anthropic", "openai", "ollama"]
    current_provider = settings.llm_provider.lower()
    provider_idx = _PROVIDERS.index(current_provider) if current_provider in _PROVIDERS else 0

    col_p, col_m, col_r = st.columns([2, 2, 1])

    with col_p:
        new_provider = st.selectbox(
            "Provider",
            _PROVIDERS,
            index=provider_idx,
            format_func=lambda p: {"gemini": "Gemini (Google)", "anthropic": "Anthropic (Claude)", "openai": "OpenAI", "ollama": "Ollama (Local)"}[p],
        )

    with col_m:
        _session_key = f"fetched_models_{new_provider}"
        if new_provider == "gemini":
            _default_models = _GEMINI_MODELS
            current_model = settings.gemini_model
            model_key = "GEMINI_MODEL"
        elif new_provider == "anthropic":
            _default_models = _ANTHROPIC_MODELS
            current_model = settings.anthropic_model
            model_key = "ANTHROPIC_MODEL"
        elif new_provider == "openai":
            _default_models = _OPENAI_MODELS
            current_model = settings.openai_model
            model_key = "OPENAI_MODEL"
        else:  # ollama
            if ollama_ok:
                try:
                    import httpx, json
                    r = httpx.get(f"{settings.ollama_base_url}/api/tags", timeout=2.0)
                    _default_models = [m["name"] for m in r.json().get("models", [])]
                except Exception:
                    _default_models = []
            else:
                _default_models = []
            if not _default_models:
                _default_models = [settings.ollama_model]
            current_model = settings.ollama_model
            model_key = "OLLAMA_MODEL"

        model_options = st.session_state.get(_session_key) or _default_models
        model_idx = model_options.index(current_model) if current_model in model_options else 0
        new_model = st.selectbox("Model", model_options, index=model_idx)

    with col_r:
        st.write("")
        st.write("")
        if new_provider in ("openai", "gemini", "anthropic"):
            if st.button("Refresh", key="btn_refresh_models", help=f"Fetch available {new_provider} models from API", use_container_width=True):
                with st.spinner("Fetching..."):
                    if new_provider == "openai":
                        fetched, err = _fetch_openai_models(settings.openai_api_key or "")
                    elif new_provider == "gemini":
                        fetched, err = _fetch_gemini_models(settings.google_api_key or "")
                    else:
                        fetched, err = _fetch_anthropic_models(settings.anthropic_api_key or "")
                if fetched:
                    st.session_state[_session_key] = fetched
                    st.success(f"{len(fetched)} models")
                    st.rerun()
                else:
                    st.error(err or "No models returned")

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

    # Pricing and Token Usage (OpenAI only)
    if new_provider == "openai" and new_model in _OPENAI_PRICING:
        st.subheader("Pricing & Token Usage")

        input_cost, output_cost = _OPENAI_PRICING[new_model]
        input_tokens = _TOKENS_PER_ENRICHMENT["input"]
        output_tokens = _TOKENS_PER_ENRICHMENT["output"]

        input_cost_per_enrichment = (input_tokens / 1_000_000) * input_cost
        output_cost_per_enrichment = (output_tokens / 1_000_000) * output_cost
        total_cost_per_enrichment = input_cost_per_enrichment + output_cost_per_enrichment

        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("Tokens per enrichment", f"{input_tokens + output_tokens:,}",
                     delta=f"{input_tokens:,} input + {output_tokens:,} output",
                     delta_color="off")

        with col2:
            st.metric("Cost per enrichment", f"${total_cost_per_enrichment:.4f}",
                     delta=f"${input_cost_per_enrichment:.5f} input + ${output_cost_per_enrichment:.5f} output",
                     delta_color="off")

        with col3:
            batch_sizes = [10, 50, 100]
            batch_cost = total_cost_per_enrichment * 50
            st.metric("Cost per 50 people", f"${batch_cost:.2f}",
                     delta="Typical batch size",
                     delta_color="off")

        st.caption(f"Pricing based on {new_model}. Costs are estimates for average LinkedIn profiles.")

        # Model comparison table
        st.subheader("Model Comparison")
        comparison_data = []
        for model, (input_price, output_price) in _OPENAI_PRICING.items():
            cost_per_person = ((input_tokens / 1_000_000) * input_price +
                              (output_tokens / 1_000_000) * output_price)
            cost_per_100 = cost_per_person * 100
            comparison_data.append({
                "Model": model,
                "Cost per person": f"${cost_per_person:.4f}",
                "Cost per 100": f"${cost_per_100:.2f}",
                "Speed": "⚡ Fast" if "mini" in model else "⚡⚡⚡ Slower"
            })
        import pandas as pd
        df = pd.DataFrame(comparison_data)
        st.dataframe(df, use_container_width=True, hide_index=True)
        st.caption("💡 **Recommendation**: gpt-4o-mini offers the best price-quality balance for LinkedIn enrichment.")

    elif new_provider == "openai":
        st.info(f"Model '{new_model}' pricing not configured. Using default gpt-4o-mini estimates.")

    st.divider()

    # Scraper Method
    st.subheader("Scraper Method")
    st.caption("How LinkedIn profile text is extracted from Chrome.")

    _SCRAPER_METHODS = ["clipboard", "dom"]
    _SCRAPER_LABELS = {
        "clipboard": "Clipboard (Cmd+A / Cmd+C) — copies all visible text via keyboard shortcut",
        "dom": "DOM extraction (JavaScript) — extracts main content area via JS",
    }
    current_scraper = settings.scraper_method.lower()
    scraper_idx = _SCRAPER_METHODS.index(current_scraper) if current_scraper in _SCRAPER_METHODS else 0

    new_scraper = st.selectbox(
        "Method",
        _SCRAPER_METHODS,
        index=scraper_idx,
        format_func=lambda m: _SCRAPER_LABELS[m],
        key="scraper_method_select",
    )

    if new_scraper != current_scraper:
        st.caption(f"**Current:** `{current_scraper}` → `{new_scraper}` *(unsaved)*")

    if st.button("Save Scraper Setting", key="btn_save_scraper"):
        from dotenv import set_key
        env_path = os.path.abspath(_ENV_PATH)
        set_key(env_path, "SCRAPER_METHOD", new_scraper)
        st.success(f"Saved `SCRAPER_METHOD={new_scraper}` to .env — restart the app to apply.")

    st.divider()

    # Advisory Role Titles (enrichment-related)
    st.subheader("Advisory Role Titles")
    st.caption(
        "Titles matching these terms are treated as advisory roles — "
        "shown in a single 'Advisory Roles' cell and matched without date-overlap requirements."
    )

    from src.data.advisory_titles import DEFAULT_ADVISORY_TITLES, load_advisory_titles, save_advisory_titles

    current_titles = load_advisory_titles()

    if current_titles:
        cols_per_row = 4
        for row_start in range(0, len(current_titles), cols_per_row):
            row_titles = current_titles[row_start: row_start + cols_per_row]
            cols = st.columns(cols_per_row)
            for col, title in zip(cols, row_titles):
                with col:
                    if st.button(f"x  {title}", key=f"rm_advisory_{title}"):
                        updated = [t for t in current_titles if t != title]
                        save_advisory_titles(updated)
                        st.success(f"Removed '{title}'.")
                        st.rerun()

    with st.form("add_advisory_title", clear_on_submit=True):
        col_inp, col_btn = st.columns([3, 1])
        with col_inp:
            new_title = st.text_input("Add title", placeholder="e.g. Board Observer")
        with col_btn:
            st.write("")
            add_submitted = st.form_submit_button("Add", type="primary")
        if add_submitted and new_title.strip():
            t = new_title.strip()
            if t not in current_titles:
                save_advisory_titles(current_titles + [t])
                st.success(f"Added '{t}'.")
                st.rerun()
            else:
                st.warning(f"'{t}' is already in the list.")

    if st.button("Reset to defaults"):
        save_advisory_titles(list(DEFAULT_ADVISORY_TITLES))
        st.success("Reset to default advisory titles.")
        st.rerun()

# ── Tab 3: Matching Rules ───────────────────────────────────────────────────

with tab_rules:
    st.subheader("Active Matching Rules")
    registry = create_default_registry()
    for rule in registry.get_all():
        st.markdown(f"- **{rule.name}**: {rule.description}")
    st.caption(
        f"{len(registry)} rule(s) active. "
        "Add new rules in src/engine/rules/ and register them in registry.py."
    )

# ── Tab 4: Data Management ──────────────────────────────────────────────────

with tab_data:
    st.subheader("Data Management")
    st.warning("These operations affect all data in Notion. Pages are archived (recoverable from Notion trash), not permanently deleted.")

    from src.data.notion_store import NotionStore as _NS

    def _get_store_settings() -> _NS:
        if "notion_store" not in st.session_state:
            st.session_state.notion_store = _NS()
        return st.session_state.notion_store

    col_leads_del, col_matches_del = st.columns(2)

    with col_leads_del:
        with st.container(border=True):
            st.markdown("**Delete All Leads**")
            st.caption("Archives every lead in Notion.")
            confirm_leads = st.checkbox("I understand this deletes all leads", key="confirm_delete_all_leads")
            if st.button("Delete All Leads", disabled=not confirm_leads, key="btn_delete_all_leads"):
                try:
                    count = _get_store_settings().delete_all_leads()
                    st.success(f"Archived {count} leads.")
                    st.session_state.pop("confirm_delete_all_leads", None)
                except Exception as e:
                    st.error(f"Failed: {e}")

    with col_matches_del:
        with st.container(border=True):
            st.markdown("**Reset Matches**")
            st.caption("Archives every match record in Notion.")
            confirm_matches = st.checkbox("I understand this deletes all matches", key="confirm_reset_matches")
            if st.button("Reset All Matches", disabled=not confirm_matches, key="btn_reset_all_matches"):
                try:
                    count = _get_store_settings().delete_all_matches()
                    st.success(f"Archived {count} matches.")
                    st.session_state.pop("confirm_reset_matches", None)
                except Exception as e:
                    st.error(f"Failed: {e}")

# ── Tab 5: Advanced ─────────────────────────────────────────────────────────

with tab_advanced:
    st.subheader("Configuration")
    st.json({"log_level": settings.log_level})
    st.caption("Edit .env to change these values, then restart the app.")

    st.divider()

    st.subheader("Notion Database IDs")
    db_config = {
        "Contacts DB": settings.notion_contacts_db_id or "(not set)",
        "Leads DB": settings.notion_leads_db_id or "(not set)",
        "Work History DB": settings.notion_work_history_db_id or "(not set)",
        "Matches DB": settings.notion_matches_db_id or "(not set)",
    }
    for label, db_id in db_config.items():
        st.text_input(label, value=db_id, disabled=True)
