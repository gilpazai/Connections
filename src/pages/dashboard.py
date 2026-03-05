"""Dashboard page: overview stats, data readiness, recent matches."""

from __future__ import annotations

import logging
import streamlit as st

from src.data.notion_store import NotionStore

logger = logging.getLogger(__name__)


def _get_store() -> NotionStore:
    if "notion_store" not in st.session_state:
        st.session_state.notion_store = NotionStore()
    return st.session_state.notion_store


def _safe_load(loader, default=None):
    try:
        return loader()
    except Exception as e:
        logger.warning("Failed to load data: %s", e)
        return default


st.title("VC Connections Dashboard")

store = _get_store()

# Summary cards
col1, col2, col3, col4 = st.columns(4)

contacts = _safe_load(lambda: store.get_all_contacts(status="Active"), [])
leads = _safe_load(lambda: store.get_all_leads(), [])
matches = _safe_load(lambda: store.get_all_matches(), [])
new_matches = [m for m in (matches or []) if m.status == "New"]

with col1:
    st.metric("Active Contacts", len(contacts or []))
with col2:
    st.metric("Total Leads", len(leads or []))
with col3:
    st.metric("Total Matches", len(matches or []))
with col4:
    st.metric("New Matches", len(new_matches))

st.divider()

# Data readiness
st.subheader("Data Readiness")

contacts_list = contacts or []
leads_list = leads or []

enriched_contacts = [c for c in contacts_list if c.last_enriched is not None]
enriched_leads = [l for l in leads_list if l.last_enriched is not None]

col_r1, col_r2 = st.columns(2)
with col_r1:
    st.metric("Contacts with work history", f"{len(enriched_contacts)} / {len(contacts_list)}")
with col_r2:
    st.metric("Leads with work history", f"{len(enriched_leads)} / {len(leads_list)}")

unenriched_contacts = len(contacts_list) - len(enriched_contacts)
unenriched_leads = len(leads_list) - len(enriched_leads)

if unenriched_contacts or unenriched_leads:
    parts = []
    if unenriched_contacts:
        parts.append(f"**{unenriched_contacts}** contacts")
    if unenriched_leads:
        parts.append(f"**{unenriched_leads}** leads")
    st.info(
        f"{' and '.join(parts)} missing work history. "
        "Ask Claude Code: `enrich my contacts` or `enrich my leads` to fetch work history from LinkedIn."
    )

st.caption("Matching runs automatically when you import leads or enrich people.")

st.divider()

# Recent matches table
st.subheader("Recent Matches")

if matches:
    import pandas as pd

    df = pd.DataFrame([
        {
            "Contact": m.contact_name,
            "Lead": m.lead_name,
            "Company": m.shared_company,
            "Overlap (mo)": m.overlap_months,
            "Confidence": m.confidence,
            "Status": m.status,
            "Date Updated": m.date_updated.isoformat() if m.date_updated else "",
        }
        for m in (matches or [])[:20]
    ])
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No matches found yet. Add contacts and leads, then enrich them to discover connections.")
