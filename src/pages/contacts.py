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


store = _get_store()

# ── Page header ──────────────────────────────────────────────────────────────

st.title("Contacts")
st.caption("Manage your core network of close contacts.")

# ── Add contact form ─────────────────────────────────────────────────────────

with st.expander("Add New Contact", expanded=False, icon=":material/person_add:"):
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
                used_url = linkedin_url.strip()
                if not used_url:
                    with st.spinner(f"Searching LinkedIn for {name}..."):
                        from src.data.linkedin_finder import find_linkedin_url
                        used_url = find_linkedin_url(name, company or None) or ""

                contact = Contact(
                    name=name,
                    linkedin_url=used_url,
                    company_current=company,
                    title_current=title,
                    relationship_strength=relationship,
                    tags=[t.strip() for t in tags_input.split(",") if t.strip()],
                )
                new_page_id = store.create_contact(contact)

                if used_url:
                    with st.spinner(f"Enriching {name} from LinkedIn..."):
                        try:
                            from src.pages._enrichment_ui import enrich_from_linkedin_url
                            count, _, new_matches = enrich_from_linkedin_url(
                                store, name, "Contact", used_url,
                                notion_page_id=new_page_id,
                            )
                            msg = f"Added and enriched **{name}**: {count} positions stored."
                            if new_matches:
                                msg += f" {new_matches} new match(es) found."
                            st.session_state["add_contact_result"] = ("success", msg)
                        except Exception as e:
                            st.session_state["add_contact_result"] = (
                                "warning",
                                f"Added **{name}** but enrichment failed: {e}",
                            )
                else:
                    st.session_state["add_contact_result"] = (
                        "info",
                        f"Added **{name}** — no LinkedIn profile found. Add a URL to enrich.",
                    )

                st.session_state["post_add_research_name"] = name
                st.session_state["post_add_research_company"] = company
                st.rerun()
            except ValueError as e:
                st.warning(str(e))
            except Exception as e:
                st.error(f"Failed to add contact: {e}")
        elif submitted:
            st.warning("Name is required.")

# Result from previous add
if "add_contact_result" in st.session_state:
    level, msg = st.session_state.pop("add_contact_result")
    getattr(st, level)(msg)

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

# ── Filters ──────────────────────────────────────────────────────────────────

status_filter = st.pills(
    "Status",
    ["All", "Active", "Inactive"],
    default="All",
    key="contacts_status_filter",
)

# ── Load contacts ────────────────────────────────────────────────────────────

try:
    status = None if status_filter == "All" else status_filter
    contacts = store.get_all_contacts(status=status)
except Exception as e:
    st.error(f"Could not load contacts: {e}")
    contacts = []

if not contacts:
    st.info("No contacts found. Add your first contact above.")
    st.stop()

import pandas as pd
from src.pages._table_helpers import lookup_work_history, position_cells
from src.pages._enrichment_ui import enrich_from_linkedin_url

try:
    grouped_wh = store.get_work_histories_grouped(person_type="Contact")
except Exception:
    grouped_wh = {}

# ── Delete confirmation dialog ───────────────────────────────────────────────

@st.dialog("Delete contact")
def _confirm_delete(page_id: str, person_name: str):
    st.write(f"Delete **{person_name}** and all associated data?")
    st.caption("Removes the contact, their work history, and any matches.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Delete", type="primary", use_container_width=True, key="dlg_del_confirm"):
            store.delete_contact(page_id, person_name=person_name)
            st.rerun()
    with col2:
        if st.button("Cancel", use_container_width=True, key="dlg_del_cancel"):
            st.rerun()

# ── Contacts table ───────────────────────────────────────────────────────────

st.caption(f"{len(contacts)} contacts shown.")

tab_detail, tab_list = st.tabs(["Detail Table", "List View"])

with tab_list:
    # Header row
    hdr_name, hdr_company, hdr_strength, hdr_status, hdr_actions = st.columns([3, 3, 2, 2, 1])
    hdr_name.markdown("**Name**")
    hdr_company.markdown("**Company**")
    hdr_strength.markdown("**Strength**")
    hdr_status.markdown("**Status**")
    hdr_actions.markdown("**...**")

    for c in contacts:
        row_key = c.notion_page_id or c.name
        col_name, col_company, col_strength, col_status, col_actions = st.columns([3, 3, 2, 2, 1])
        col_name.write(c.name)
        col_company.write(c.company_current or "")
        col_strength.write(c.relationship_strength or "")
        col_status.write(c.status or "")
        with col_actions:
            with st.popover("...", use_container_width=True):
                enrich_label = "Re-enrich" if c.last_enriched else "Enrich"
                if st.button(enrich_label, key=f"enrich_c_{row_key}", use_container_width=True):
                    if not c.linkedin_url:
                        st.warning(f"No LinkedIn URL for {c.name}.")
                    else:
                        with st.spinner(f"Enriching {c.name}..."):
                            try:
                                count, _, new_matches = enrich_from_linkedin_url(
                                    store, c.name, "Contact", c.linkedin_url,
                                    notion_page_id=c.notion_page_id,
                                )
                                msg = f"Enriched **{c.name}**: {count} positions stored."
                                if new_matches:
                                    msg += f" {new_matches} new match(es) found."
                                st.success(msg)
                                st.rerun()
                            except Exception as e:
                                st.error(f"Enrichment failed: {e}")
                if st.button("Research", key=f"research_c_{row_key}", use_container_width=True):
                    st.session_state["research_person_name"] = c.name
                    st.session_state["research_person_company"] = c.company_current or ""
                    st.session_state["research_person_type"] = "Contact"
                    st.switch_page("src/pages/research.py")
                st.divider()
                if c.notion_page_id:
                    if st.button("Delete", key=f"del_c_{row_key}", use_container_width=True):
                        _confirm_delete(c.notion_page_id, c.name)

with tab_detail:
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
