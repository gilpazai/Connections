"""Matches page: view, filter, and manage warm introduction matches."""

from __future__ import annotations

import logging
from datetime import date

import pandas as pd
import streamlit as st

from src.data.notion_store import NotionStore

logger = logging.getLogger(__name__)

STATUS_OPTIONS = ["New", "Request Intro", "Intro", "In CRM"]


def _get_store() -> NotionStore:
    if "notion_store" not in st.session_state:
        st.session_state.notion_store = NotionStore()
    return st.session_state.notion_store


st.title("Matches")
st.caption("Discovered warm introduction paths between your contacts and leads.")

store = _get_store()

# Filters
col_f1, col_f2 = st.columns(2)
with col_f1:
    status_filter = st.selectbox(
        "Filter by Status",
        ["All"] + STATUS_OPTIONS,
        index=0,
    )
with col_f2:
    confidence_filter = st.selectbox(
        "Filter by Confidence",
        ["All", "High", "Medium", "Low"],
        index=0,
    )

if st.button("Recheck Matches"):
    from src.engine.matcher import run_matching, store_new_matches, _group_histories_by_name
    with st.spinner("Running matching..."):
        contact_entries = store.get_all_work_history(person_type="Contact")
        lead_entries = store.get_all_work_history(person_type="Lead")
        if not contact_entries or not lead_entries:
            st.warning("Need enriched contacts and leads to run matching.")
        else:
            contact_histories = _group_histories_by_name(contact_entries)
            lead_histories = _group_histories_by_name(lead_entries)
            new_matches = run_matching(contact_histories, lead_histories)
            created, skipped = store_new_matches(new_matches, store)
            st.success(f"Done: {created} new match(es), {skipped} duplicate(s) skipped.")
            if created:
                st.rerun()

# Load matches
try:
    matches = store.get_all_matches(
        status=None if status_filter == "All" else status_filter,
        confidence=None if confidence_filter == "All" else confidence_filter,
    )
except Exception as e:
    st.error(f"Could not load matches: {e}")
    matches = []

if not matches:
    st.info("No matches found. Matches are created automatically when you import leads or enrich people.")
    st.stop()

st.caption(f"{len(matches)} matches shown.")

# Build editable dataframe
rows = []
page_ids = []
original_statuses = []
original_notes = []

for m in matches:
    status = m.status if m.status in STATUS_OPTIONS else "New"
    rows.append({
        "Contact": m.contact_name,
        "Contact LinkedIn": m.contact_linkedin,
        "Lead": m.lead_name,
        "Lead LinkedIn": m.lead_linkedin,
        "Lead Company": m.lead_company,
        "Shared Company": m.shared_company,
        "Overlap (mo)": m.overlap_months,
        "Confidence": m.confidence,
        "Status": status,
        "Notes": m.notes,
        "Date Updated": m.date_updated.isoformat() if m.date_updated else "",
    })
    page_ids.append(m.notion_page_id)
    original_statuses.append(status)
    original_notes.append(m.notes)

df = pd.DataFrame(rows)

edited_df = st.data_editor(
    df,
    use_container_width=True,
    hide_index=True,
    num_rows="fixed",
    column_config={
        "Contact": st.column_config.TextColumn("Contact", disabled=True),
        "Contact LinkedIn": st.column_config.LinkColumn("Contact LinkedIn"),
        "Lead": st.column_config.TextColumn("Lead", disabled=True),
        "Lead LinkedIn": st.column_config.LinkColumn("Lead LinkedIn"),
        "Lead Company": st.column_config.TextColumn("Lead Company", disabled=True),
        "Shared Company": st.column_config.TextColumn("Shared Company", disabled=True),
        "Overlap (mo)": st.column_config.NumberColumn("Overlap (mo)", disabled=True),
        "Confidence": st.column_config.TextColumn("Confidence", disabled=True),
        "Status": st.column_config.SelectboxColumn(
            "Status",
            options=STATUS_OPTIONS,
            required=True,
        ),
        "Notes": st.column_config.TextColumn("Notes", max_chars=500),
        "Date Updated": st.column_config.TextColumn("Date Updated", disabled=True),
    },
    key="matches_editor",
)

# Detect and save changes
if st.button("Save Changes", type="primary"):
    changes = 0
    for i in range(len(page_ids)):
        new_status = edited_df.iloc[i]["Status"]
        new_notes = edited_df.iloc[i]["Notes"]
        pid = page_ids[i]

        if not pid:
            continue

        status_changed = new_status != original_statuses[i]
        notes_changed = new_notes != original_notes[i]

        if status_changed or notes_changed:
            try:
                update_kwargs = {}
                if status_changed:
                    update_kwargs["status"] = new_status
                if notes_changed:
                    update_kwargs["notes"] = new_notes
                update_kwargs["date_updated"] = date.today()
                store.update_match(pid, **update_kwargs)
                changes += 1
            except Exception as e:
                st.error(f"Failed to update match: {e}")

    if changes:
        st.success(f"Updated {changes} match(es).")
        st.rerun()
    else:
        st.info("No changes detected.")
