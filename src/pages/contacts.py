"""Contacts page: view, add, and manage core network contacts."""

from __future__ import annotations

import logging
import streamlit as st

from src.data.notion_store import NotionStore
from src.models.contact import Contact

logger = logging.getLogger(__name__)


def _get_store() -> NotionStore:
    if "notion_store" not in st.session_state:
        st.session_state.notion_store = NotionStore()
    return st.session_state.notion_store


st.title("Contacts")
st.caption("Manage your core network of close contacts.")

store = _get_store()

# Add contact form
with st.expander("Add New Contact", expanded=False):
    with st.form("add_contact"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name*")
            linkedin_url = st.text_input("LinkedIn URL")
            company = st.text_input("Current Company*")
        with col2:
            title = st.text_input("Current Title")
            relationship = st.selectbox(
                "Relationship Strength",
                ["Close", "Medium", "Loose"],
                index=1,
            )
            tags_input = st.text_input("Tags (comma-separated)", placeholder="VC, Founder, Operator")

        submitted = st.form_submit_button("Add Contact", type="primary")
        if submitted and name:
            try:
                contact = Contact(
                    name=name,
                    linkedin_url=linkedin_url,
                    company_current=company,
                    title_current=title,
                    relationship_strength=relationship,
                    tags=[t.strip() for t in tags_input.split(",") if t.strip()],
                )
                store.create_contact(contact)
                st.success(f"Added contact: {name}.")
                st.session_state["post_add_research_name"] = name
                st.session_state["post_add_research_company"] = company
                st.rerun()
            except ValueError as e:
                st.warning(str(e))
            except Exception as e:
                st.error(f"Failed to add contact: {e}")
        elif submitted:
            st.warning("Name is required.")

# Post-add research prompt
if "post_add_research_name" in st.session_state:
    _name = st.session_state.pop("post_add_research_name")
    _company = st.session_state.pop("post_add_research_company", "")
    st.info(f"**{_name}** was added. Run AI research to build their profile?")
    col_yes, col_no, _ = st.columns([1, 1, 4])
    with col_yes:
        if st.button("Research now", key="post_add_research_yes", type="primary"):
            st.session_state["research_person_name"] = _name
            st.session_state["research_person_company"] = _company
            st.session_state["research_person_type"] = "Contact"
            st.switch_page("src/pages/research.py")
    with col_no:
        if st.button("Skip", key="post_add_research_no"):
            st.rerun()

st.divider()

# Filters
col_f1, col_f2 = st.columns(2)
with col_f1:
    status_filter = st.selectbox(
        "Filter by Status", ["All", "Active", "Inactive"], index=0
    )

# Contacts table
try:
    status = None if status_filter == "All" else status_filter
    contacts = store.get_all_contacts(status=status)
except Exception as e:
    st.error(f"Could not load contacts: {e}")
    contacts = []

if contacts:
    import pandas as pd
    from src.pages._table_helpers import lookup_work_history, position_cells
    from src.pages._enrichment_ui import enrich_from_linkedin_url

    # Load all work histories for contacts in one query
    try:
        grouped_wh = store.get_work_histories_grouped(person_type="Contact")
    except Exception:
        grouped_wh = {}

    # ── Per-row buttons ──────────────────────────────────────────────────────
    hdr0, hdr1, hdr2, hdr3, hdr4, hdr5 = st.columns([1, 1, 3, 3, 2, 2])
    hdr1.markdown("**Actions**")
    hdr2.markdown("**Name**")
    hdr3.markdown("**Company**")
    hdr4.markdown("**Strength**")
    hdr5.markdown("**Status**")

    for c in contacts:
        col_enrich, col_research, col_name, col_company, col_strength, col_status = st.columns([1, 1, 3, 3, 2, 2])
        with col_enrich:
            label = "Enrich" if c.last_enriched is None else "Re-enrich"
            if st.button(label, key=f"enrich_c_{c.notion_page_id or c.name}"):
                if not c.linkedin_url:
                    st.warning(f"No LinkedIn URL for {c.name} — add one first.")
                else:
                    with st.spinner(f"Enriching {c.name}..."):
                        try:
                            count, _, new_matches = enrich_from_linkedin_url(
                                store, c.name, "Contact", c.linkedin_url
                            )
                            msg = f"Enriched **{c.name}**: {count} positions stored."
                            if new_matches:
                                msg += f" {new_matches} new match(es) found."
                            st.success(msg)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Enrichment failed: {e}")
        with col_research:
            if st.button("Research", key=f"research_c_{c.notion_page_id or c.name}"):
                st.session_state["research_person_name"] = c.name
                st.session_state["research_person_company"] = c.company_current or ""
                st.session_state["research_person_type"] = "Contact"
                st.switch_page("src/pages/research.py")
        col_name.write(c.name)
        col_company.write(c.company_current or "")
        col_strength.write(c.relationship_strength or "")
        col_status.write(c.status or "")

    st.divider()

    # ── Full detail table ────────────────────────────────────────────────────
    with st.expander("Full detail table", expanded=False):
        rows = []
        for c in contacts:
            entries = lookup_work_history(c.dealigence_person_id, c.name, grouped_wh)
            row = {
                "Name": c.name,
                "Company": c.company_current,
                "Title": c.title_current,
                "Strength": c.relationship_strength,
                "Tags": ", ".join(c.tags),
                "Status": c.status,
                "LinkedIn": c.linkedin_url,
            }
            row.update(position_cells(entries, enriched=c.last_enriched is not None))
            rows.append(row)

        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={"LinkedIn": st.column_config.LinkColumn("LinkedIn")},
        )
    st.caption(f"{len(contacts)} contacts shown.")

else:
    st.info("No contacts found. Add your first contact above.")
