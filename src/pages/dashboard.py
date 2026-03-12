"""Dashboard page: overview stats, data readiness, recent matches."""

from __future__ import annotations

import logging
import streamlit as st

from src.pages._cached_data import cached, invalidate_all
from src.pages._store import get_store

logger = logging.getLogger(__name__)

_ENRICH_BATCH_SIZE = 5


def _safe_load(key, loader, default=None):
    try:
        return cached(key, loader)
    except Exception as e:
        logger.warning("Failed to load data: %s", e)
        return default


st.title("VC Connections Dashboard")

store = get_store()

# ── Summary metrics ──────────────────────────────────────────────────────────

contacts = _safe_load("dash_contacts", lambda: store.get_all_contacts(status="Active"), [])
leads = _safe_load("dash_leads", lambda: store.get_all_leads(), [])
matches = _safe_load("dash_matches", lambda: store.get_all_matches(), [])
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

# ── Active enrichment processor ──────────────────────────────────────────────

if st.session_state.get("_enrich_queue") is not None:
    if st.session_state.get("_enrich_stop"):
        done = st.session_state["_enrich_total"] - len(st.session_state["_enrich_queue"])
        c = st.session_state.get("_enrich_counters", {})
        st.info(
            f"Stopped after {done}/{st.session_state['_enrich_total']} people — "
            f"{c.get('positions', 0)} positions, {c.get('matches', 0)} new matches."
        )
        for k in ("_enrich_queue", "_enrich_total", "_enrich_counters", "_enrich_mode", "_enrich_stop"):
            st.session_state.pop(k, None)
        invalidate_all()
        st.rerun()

    queue = st.session_state["_enrich_queue"]
    total = st.session_state["_enrich_total"]
    done  = total - len(queue)
    mode  = st.session_state.get("_enrich_mode", "linkedin")
    label = "Enriching" if mode == "linkedin" else "Researching"

    batch = [queue.pop(0) for _ in range(min(_ENRICH_BATCH_SIZE, len(queue)))]
    st.session_state["_enrich_queue"] = queue

    batch_start = done + 1
    batch_end   = done + len(batch)
    st.progress(
        done / total,
        text=f"{label} {batch[0][0].name}… ({batch_start}–{batch_end} of {total})",
    )
    st.button(
        "⏹ Stop after this batch",
        key="btn_stop_enrich",
        on_click=lambda: st.session_state.update({"_enrich_stop": True}),
    )

    counters = st.session_state.setdefault("_enrich_counters", {"positions": 0, "matches": 0})
    for person, ptype in batch:
        try:
            if mode == "linkedin":
                from src.pages._enrichment_ui import enrich_from_linkedin_url
                count, _, nm = enrich_from_linkedin_url(
                    store, person.name, ptype, person.linkedin_url,
                    notion_page_id=person.notion_page_id,
                )
            else:
                from src.data.investigator_runner import run_research
                from src.pages._enrichment_ui import do_enrich
                report_md = run_research(person.name, company=person.company_current, force_refresh=False)
                count, _, nm = do_enrich(store, person.name, ptype, report_md)
            counters["positions"] += count
            counters["matches"]   += nm
        except Exception as e:
            logger.warning("Enrichment failed for %s: %s", person.name, e)

    if queue:
        st.rerun()
    else:
        c = counters
        st.success(
            f"Done — {total} people: {c['positions']} positions, {c['matches']} new matches."
        )
        for k in ("_enrich_queue", "_enrich_total", "_enrich_counters", "_enrich_mode", "_enrich_stop"):
            st.session_state.pop(k, None)
        invalidate_all()
        st.rerun()

# ── Bulk enrich actions ───────────────────────────────────────────────────────

if unenriched_contacts or unenriched_leads:
    st.caption("Bulk enrich missing people:")
    col_enrich, col_research, col_nav = st.columns([1, 1, 2])

    with col_enrich:
        if st.button("🔗 Enrich from LinkedIn", use_container_width=True, help="Scrape LinkedIn profiles for all unenriched people with URLs"):
            to_enrich = []
            if unenriched_contacts:
                to_enrich.extend([(c, "Contact") for c in contacts_list if c.last_enriched is None and c.linkedin_url])
            if unenriched_leads:
                to_enrich.extend([(l, "Lead") for l in leads_list if l.last_enriched is None and l.linkedin_url])

            if to_enrich:
                st.session_state.update({
                    "_enrich_queue":    list(to_enrich),
                    "_enrich_total":    len(to_enrich),
                    "_enrich_counters": {"positions": 0, "matches": 0},
                    "_enrich_mode":     "linkedin",
                })
                st.session_state.pop("_enrich_stop", None)
                st.rerun()
            else:
                st.info("No unenriched people with LinkedIn URLs found.")

    with col_research:
        if st.button("🔍 Research & Enrich", use_container_width=True, help="Run AI research on all unenriched people"):
            to_research = []
            if unenriched_contacts:
                to_research.extend([(c, "Contact") for c in contacts_list if c.last_enriched is None])
            if unenriched_leads:
                to_research.extend([(l, "Lead") for l in leads_list if l.last_enriched is None])

            if to_research:
                st.session_state.update({
                    "_enrich_queue":    list(to_research),
                    "_enrich_total":    len(to_research),
                    "_enrich_counters": {"positions": 0, "matches": 0},
                    "_enrich_mode":     "research",
                })
                st.session_state.pop("_enrich_stop", None)
                st.rerun()
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
