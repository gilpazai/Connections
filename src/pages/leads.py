"""Leads page: view, import, and manage target leads."""

from __future__ import annotations

import logging
from datetime import date

import streamlit as st

from src.data.notion_store import NotionStore
from src.models.lead import Lead

logger = logging.getLogger(__name__)


def _get_store() -> NotionStore:
    if "notion_store" not in st.session_state:
        st.session_state.notion_store = NotionStore()
    return st.session_state.notion_store


@st.dialog("Run AI Research on imported leads?")
def _batch_research_dialog(leads_info: list[dict]) -> None:
    """Confirmation dialog to research all newly imported leads."""
    st.write(
        f"**{len(leads_info)}** leads were just imported. "
        "Run AI research on each one to build their profiles and extract work history?"
    )
    st.caption("Each person takes ~30 seconds. Total: ~" + str(len(leads_info) * 30) + "s")
    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button("Research all", type="primary", use_container_width=True):
            store = _get_store()
            progress = st.progress(0, text="Starting research...")
            for i, info in enumerate(leads_info):
                progress.progress((i + 1) / len(leads_info), text=f"Researching {info['name']}...")
                try:
                    from src.data.investigator_runner import run_research
                    from src.pages._enrichment_ui import do_enrich
                    report_md = run_research(info["name"], company=info.get("company"))
                    do_enrich(store, info["name"], "Lead", report_md)
                except Exception as e:
                    st.warning(f"Research failed for {info['name']}: {e}")
            progress.progress(1.0, text="All research complete!")
            st.success(f"Research complete for {len(leads_info)} leads.")
            st.rerun()
    with col_no:
        if st.button("Skip for now", use_container_width=True):
            st.rerun()


st.title("Leads")
st.caption("Manage monthly target leads for warm introductions.")

store = _get_store()

# CSV file import (Dealigence export format)
with st.expander("Import from Dealigence CSV", expanded=False):
    st.markdown(
        "Upload a CSV exported from Dealigence (e.g. Stealth Co-Founders Report). "
        "This will create leads **and** store their work history from the CSV data."
    )
    with st.form("import_csv"):
        uploaded_file = st.file_uploader(
            "Dealigence CSV file",
            type=["csv"],
            help="CSV with columns: Person Name, Person Linkedin, Company Name, Employee Title, etc.",
        )
        col_a, col_b = st.columns(2)
        with col_a:
            csv_batch = st.text_input(
                "Batch Label",
                value=date.today().strftime("%Y-%m"),
            )
        with col_b:
            csv_priority = st.selectbox(
                "Default Priority",
                ["High", "Medium", "Low"],
                index=1,
                key="csv_priority",
            )
        csv_submitted = st.form_submit_button("Import CSV", type="primary")

    if csv_submitted and uploaded_file is not None:
        from src.data.csv_import import parse_dealigence_csv

        try:
            csv_content = uploaded_file.getvalue().decode("utf-8")
            leads_parsed, work_entries = parse_dealigence_csv(
                csv_content, batch=csv_batch, default_priority=csv_priority,
            )

            created_leads = 0
            skipped_dupes = 0
            created_history = 0
            progress = st.progress(0, text="Importing leads...")
            imported_names = []

            for i, lead in enumerate(leads_parsed):
                try:
                    store.create_lead(lead)
                    created_leads += 1
                    imported_names.append({"name": lead.name, "company": lead.company_current or ""})
                except ValueError:
                    skipped_dupes += 1
                except Exception as e:
                    st.warning(f"Failed to import '{lead.name}': {e}")
                progress.progress((i + 1) / (len(leads_parsed) + 1), text=f"Importing lead {i+1}/{len(leads_parsed)}...")

            # Store work history entries in batches
            if work_entries:
                created_history = store.store_work_history(work_entries)

            # Auto-match imported leads against existing contacts
            created_matches = 0
            if work_entries and created_leads > 0:
                from src.engine.matcher import run_matching, store_new_matches, _group_histories_by_name

                progress.progress(0.95, text="Running matching...")
                contact_entries = store.get_all_work_history(person_type="Contact")
                if contact_entries:
                    contact_histories = _group_histories_by_name(contact_entries)
                    lead_histories = _group_histories_by_name(work_entries)
                    matches = run_matching(contact_histories, lead_histories)
                    created_matches, _ = store_new_matches(matches, store)

            progress.progress(1.0, text="Import complete!")
            msg = f"Imported **{created_leads}** leads and **{created_history}** work history entries into batch '{csv_batch}'."
            if created_matches:
                msg += f" Discovered **{created_matches}** new matches."
            if skipped_dupes:
                msg += f" Skipped **{skipped_dupes}** duplicates."
            st.success(msg)

            if imported_names:
                st.session_state["pending_batch_research"] = imported_names
            st.rerun()
        except Exception as e:
            st.error(f"CSV import failed: {e}")
            logger.exception("CSV import error")

# Batch import (manual paste)
with st.expander("Import Lead Batch (paste)", expanded=False):
    st.markdown("Paste one lead per line: `Name, Company, LinkedIn URL` (company and URL optional)")
    with st.form("import_leads"):
        batch_label = st.text_input(
            "Batch Label",
            value=date.today().strftime("%Y-%m"),
            help="Month identifier for this batch",
        )
        priority = st.selectbox("Default Priority", ["High", "Medium", "Low"], index=1)
        raw_input = st.text_area(
            "Leads",
            height=200,
            placeholder="Jane Doe, Acme Corp, https://linkedin.com/in/janedoe\nJohn Smith, Beta Inc",
        )
        submitted = st.form_submit_button("Import Leads", type="primary")
        if submitted and raw_input.strip():
            lines = [l.strip() for l in raw_input.strip().split("\n") if l.strip()]
            created = 0
            skipped = 0
            imported_names = []
            for line in lines:
                parts = [p.strip() for p in line.split(",")]
                name = parts[0] if len(parts) > 0 else ""
                company = parts[1] if len(parts) > 1 else ""
                linkedin = parts[2] if len(parts) > 2 else ""
                if not name:
                    continue
                try:
                    lead = Lead(
                        name=name,
                        company_current=company,
                        linkedin_url=linkedin,
                        priority=priority,
                        batch=batch_label,
                    )
                    store.create_lead(lead)
                    created += 1
                    imported_names.append({"name": name, "company": company})
                except ValueError:
                    skipped += 1
                except Exception as e:
                    st.warning(f"Failed to import '{name}': {e}")
            if created or skipped:
                msg = f"Imported {created} leads into batch '{batch_label}'."
                if skipped:
                    msg += f" Skipped {skipped} duplicates."
                st.success(msg)
                if imported_names:
                    st.session_state["pending_batch_research"] = imported_names
                st.rerun()

# Add single lead
with st.expander("Add Single Lead", expanded=False):
    with st.form("add_lead"):
        col1, col2 = st.columns(2)
        with col1:
            name = st.text_input("Full Name*")
            linkedin_url = st.text_input("LinkedIn URL")
            company = st.text_input("Current Company")
        with col2:
            title = st.text_input("Current Title")
            lead_priority = st.selectbox("Priority", ["High", "Medium", "Low"], index=1)
            batch = st.text_input("Batch", value=date.today().strftime("%Y-%m"))

        submitted = st.form_submit_button("Add Lead", type="primary")
        if submitted and name:
            try:
                lead = Lead(
                    name=name,
                    linkedin_url=linkedin_url,
                    company_current=company,
                    title_current=title,
                    priority=lead_priority,
                    batch=batch,
                )
                store.create_lead(lead)
                st.success(f"Added lead: {name}.")
                st.session_state["post_add_research_name"] = name
                st.session_state["post_add_research_company"] = company
                st.rerun()
            except ValueError as e:
                st.warning(str(e))
            except Exception as e:
                st.error(f"Failed to add lead: {e}")
        elif submitted:
            st.warning("Name is required.")

# Post-add research prompt (single lead)
if "post_add_research_name" in st.session_state:
    _name = st.session_state.pop("post_add_research_name")
    _company = st.session_state.pop("post_add_research_company", "")
    st.info(f"**{_name}** was added. Run AI research to build their profile?")
    col_yes, col_no, _ = st.columns([1, 1, 4])
    with col_yes:
        if st.button("Research now", key="post_add_lead_research_yes", type="primary"):
            st.session_state["research_person_name"] = _name
            st.session_state["research_person_company"] = _company
            st.session_state["research_person_type"] = "Lead"
            st.switch_page("src/pages/research.py")
    with col_no:
        if st.button("Skip", key="post_add_lead_research_no"):
            st.rerun()

# Batch research dialog (after CSV/paste import)
if "pending_batch_research" in st.session_state:
    _batch_research_dialog(st.session_state.pop("pending_batch_research"))

st.divider()

# Batch archive
with st.expander("Close Batch", expanded=False):
    st.markdown("Archive all leads in a batch. Archived leads are hidden from the default view.")
    with st.form("close_batch"):
        archive_batch = st.text_input("Batch to archive", placeholder="e.g. 2026-02")
        if st.form_submit_button("Archive Batch", type="primary"):
            if archive_batch:
                try:
                    count = store.archive_batch(archive_batch)
                    if count:
                        st.success(f"Archived **{count}** leads from batch '{archive_batch}'.")
                        st.rerun()
                    else:
                        st.info("No leads found in that batch (or already archived).")
                except Exception as e:
                    st.error(f"Failed to archive batch: {e}")

st.divider()

# Filters
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    batch_filter = st.text_input("Filter by Batch", placeholder="e.g. 2026-03")
with col_f2:
    status_filter = st.selectbox(
        "Filter by Status",
        ["All", "New", "Enriched", "Matched", "Contacted", "Converted", "Archived"],
        index=0,
    )
with col_f3:
    show_archived = st.checkbox("Show Archived", value=False)

# Leads table
try:
    if show_archived or status_filter == "Archived":
        leads = store.get_all_leads(
            batch=batch_filter or None,
            status=None if status_filter == "All" else status_filter,
        )
    else:
        leads = store.get_active_leads(batch=batch_filter or None)
        if status_filter != "All":
            leads = [l for l in leads if l.status == status_filter]
except Exception as e:
    st.error(f"Could not load leads: {e}")
    leads = []

if leads:
    import pandas as pd
    from src.pages._table_helpers import lookup_work_history, position_cells
    from src.pages._enrichment_ui import enrich_from_linkedin_url

    # Load all work histories for leads in one query
    try:
        grouped_wh = store.get_work_histories_grouped(person_type="Lead")
    except Exception:
        grouped_wh = {}

    # ── Per-row buttons ──────────────────────────────────────────────────────
    hdr0, hdr1, hdr2, hdr3, hdr4, hdr5, hdr6 = st.columns([1, 1, 3, 3, 2, 2, 2])
    hdr1.markdown("**Actions**")
    hdr2.markdown("**Name**")
    hdr3.markdown("**Company**")
    hdr4.markdown("**Priority**")
    hdr5.markdown("**Batch**")
    hdr6.markdown("**Status**")

    for l in leads:
        col_enrich, col_research, col_name, col_company, col_priority, col_batch, col_status = st.columns([1, 1, 3, 3, 2, 2, 2])
        with col_enrich:
            has_history = len(lookup_work_history(l.dealigence_person_id, l.name, grouped_wh)) > 0
            label = "Re-enrich" if has_history else "Enrich"
            if st.button(label, key=f"enrich_l_{l.notion_page_id or l.name}"):
                if not l.linkedin_url:
                    st.warning(f"No LinkedIn URL for {l.name} — add one first.")
                else:
                    with st.spinner(f"Enriching {l.name}..."):
                        try:
                            count, _, new_matches = enrich_from_linkedin_url(
                                store, l.name, "Lead", l.linkedin_url
                            )
                            msg = f"Enriched **{l.name}**: {count} positions stored."
                            if new_matches:
                                msg += f" {new_matches} new match(es) found."
                            st.success(msg)
                            st.rerun()
                        except Exception as e:
                            st.error(f"Enrichment failed: {e}")
        with col_research:
            if st.button("Research", key=f"research_l_{l.notion_page_id or l.name}"):
                st.session_state["research_person_name"] = l.name
                st.session_state["research_person_company"] = l.company_current or ""
                st.session_state["research_person_type"] = "Lead"
                st.switch_page("src/pages/research.py")
        col_name.write(l.name)
        col_company.write(l.company_current or "")
        col_priority.write(l.priority or "")
        col_batch.write(l.batch or "")
        col_status.write(l.status or "")

    st.divider()

    # ── Full detail table ────────────────────────────────────────────────────
    with st.expander("Full detail table", expanded=False):
        rows = []
        for l in leads:
            entries = lookup_work_history(l.dealigence_person_id, l.name, grouped_wh)
            row = {
                "Name": l.name,
                "Company": l.company_current,
                "Title": l.title_current,
                "Priority": l.priority,
                "Batch": l.batch,
                "Status": l.status,
                "LinkedIn": l.linkedin_url,
            }
            row.update(position_cells(entries, enriched=len(entries) > 0))
            rows.append(row)

        df = pd.DataFrame(rows)
        st.dataframe(
            df,
            use_container_width=True,
            hide_index=True,
            column_config={"LinkedIn": st.column_config.LinkColumn("LinkedIn")},
        )

    # Status summary
    status_counts = {}
    for l in leads:
        status_counts[l.status] = status_counts.get(l.status, 0) + 1
    cols = st.columns(len(status_counts))
    for i, (s, count) in enumerate(sorted(status_counts.items())):
        with cols[i]:
            st.metric(s, count)
else:
    st.info("No leads found. Import a batch or add leads above.")
