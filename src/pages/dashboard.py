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

# ── Summary metrics ──────────────────────────────────────────────────────────

contacts = _safe_load(lambda: store.get_all_contacts(status="Active"), [])
leads = _safe_load(lambda: store.get_all_leads(), [])
matches = _safe_load(lambda: store.get_all_matches(), [])
new_matches = [m for m in (matches or []) if m.status == "New"]

col1, col2, col3, col4 = st.columns(4)
with col1:
    st.metric("Active Contacts", len(contacts or []))
with col2:
    st.metric("Total Leads", len(leads or []))
with col3:
    st.metric("Total Matches", len(matches or []))
with col4:
    st.metric("New Matches", len(new_matches))

st.divider()

# ── Data readiness ───────────────────────────────────────────────────────────

contacts_list = contacts or []
leads_list = leads or []

enriched_contacts = [c for c in contacts_list if c.last_enriched is not None]
enriched_leads = [l for l in leads_list if l.last_enriched is not None]
unenriched_contacts = len(contacts_list) - len(enriched_contacts)
unenriched_leads = len(leads_list) - len(enriched_leads)

st.subheader("Data Readiness")

col_r1, col_r2 = st.columns(2)
with col_r1:
    st.metric("Contacts with work history", f"{len(enriched_contacts)} / {len(contacts_list)}")
with col_r2:
    st.metric("Leads with work history", f"{len(enriched_leads)} / {len(leads_list)}")

# Bulk enrich actions
if unenriched_contacts or unenriched_leads:
    st.caption("Bulk enrich missing people:")
    col_enrich, col_research, col_nav = st.columns([1, 1, 2])

    with col_enrich:
        if st.button("🔗 Enrich from LinkedIn", use_container_width=True, help="Scrape LinkedIn profiles for all unenriched people with URLs"):
            from src.pages._enrichment_ui import enrich_from_linkedin_url
            from src.engine.matcher import run_matching, store_new_matches, _group_histories_by_name

            to_enrich = []
            if unenriched_contacts:
                to_enrich.extend([(c, "Contact") for c in contacts_list if c.last_enriched is None and c.linkedin_url])
            if unenriched_leads:
                to_enrich.extend([(l, "Lead") for l in leads_list if l.last_enriched is None and l.linkedin_url])

            if to_enrich:
                progress = st.progress(0, text="Starting enrichment...")
                total_count = 0
                total_matches = 0
                for i, (person, ptype) in enumerate(to_enrich):
                    progress.progress((i + 1) / len(to_enrich), text=f"Enriching {person.name}...")
                    try:
                        count, _, new_matches = enrich_from_linkedin_url(store, person.name, ptype, person.linkedin_url, notion_page_id=person.notion_page_id)
                        total_count += count
                        total_matches += new_matches
                    except Exception as e:
                        logger.warning("Enrichment failed for %s: %s", person.name, e)
                progress.progress(1.0, text="Enrichment complete!")
                st.success(f"Enriched {len(to_enrich)} people: {total_count} positions, {total_matches} new matches.")
            else:
                st.info("No unenriched people with LinkedIn URLs found.")

    with col_research:
        if st.button("🔍 Research & Enrich", use_container_width=True, help="Run AI research on all unenriched people"):
            from src.data.investigator_runner import run_research
            from src.pages._enrichment_ui import do_enrich
            from src.engine.matcher import run_matching, store_new_matches, _group_histories_by_name

            to_research = []
            if unenriched_contacts:
                to_research.extend([(c, "Contact") for c in contacts_list if c.last_enriched is None])
            if unenriched_leads:
                to_research.extend([(l, "Lead") for l in leads_list if l.last_enriched is None])

            if to_research:
                progress = st.progress(0, text="Starting research...")
                total_count = 0
                total_matches = 0
                for i, (person, ptype) in enumerate(to_research):
                    progress.progress((i + 1) / len(to_research), text=f"Researching {person.name}... (~30s)")
                    try:
                        report_md = run_research(person.name, company=person.company_current, force_refresh=False)
                        count, _, new_matches = do_enrich(store, person.name, ptype, report_md)
                        total_count += count
                        total_matches += new_matches
                    except Exception as e:
                        logger.warning("Research failed for %s: %s", person.name, e)
                progress.progress(1.0, text="Research complete!")
                st.success(f"Researched {len(to_research)} people: {total_count} positions, {total_matches} new matches.")
            else:
                st.info("No unenriched people found.")

    with col_nav:
        if st.button("View Details →", use_container_width=True):
            if unenriched_contacts:
                st.switch_page("src/pages/contacts.py")
            else:
                st.switch_page("src/pages/leads.py")

st.caption("Matching runs automatically when you import leads or enrich people.")

st.divider()

# ── Next Steps ───────────────────────────────────────────────────────────────

st.subheader("Next Steps")

if not contacts_list:
    st.info("Start by adding contacts from your network.")
    if st.button("Add Contacts", type="primary", key="ns_contacts"):
        st.switch_page("src/pages/contacts.py")
elif not leads_list:
    st.info("Add leads to find warm introduction paths.")
    if st.button("Import Leads", type="primary", key="ns_leads"):
        st.switch_page("src/pages/leads.py")
elif new_matches:
    st.info(f"You have **{len(new_matches)}** new matches to review.")
    if st.button("Review Matches", type="primary", key="ns_matches"):
        st.switch_page("src/pages/matches.py")
elif unenriched_contacts or unenriched_leads:
    parts = []
    if unenriched_contacts:
        parts.append(f"**{unenriched_contacts}** contacts")
    if unenriched_leads:
        parts.append(f"**{unenriched_leads}** leads")
    st.info(f"Enrich {' and '.join(parts)} to discover more connections.")
else:
    st.success("All caught up. Your network is fully mapped.")

st.divider()

# ── Recent matches ───────────────────────────────────────────────────────────

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
    if len(matches) > 20:
        if st.button("View all matches"):
            st.switch_page("src/pages/matches.py")
else:
    st.info("No matches found yet. Add contacts and leads, then enrich them to discover connections.")
