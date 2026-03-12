"""Leads page: view, import, and manage target leads."""

from __future__ import annotations

import logging
from datetime import date

import streamlit as st

from src.models.lead import Lead
from src.pages._cached_data import cached, invalidate_all
from src.pages._store import get_store

logger = logging.getLogger(__name__)


# ── Dialogs ──────────────────────────────────────────────────────────────────

@st.dialog("Run AI Research on imported leads?")
def _batch_research_dialog(leads_info: list[dict]) -> None:
    st.write(
        f"**{len(leads_info)}** leads were just imported. "
        "Run AI research on each one to build their profiles and extract work history?"
    )
    st.caption("Each person takes ~30 seconds. Total: ~" + str(len(leads_info) * 30) + "s")
    col_yes, col_no = st.columns(2)
    with col_yes:
        if st.button("Research all", type="primary", use_container_width=True):
            store = get_store()
            st.session_state.pop("_batch_research_stop", None)
            st.button(
                "⏹ Stop after this person",
                key="btn_stop_batch_research",
                on_click=lambda: st.session_state.update({"_batch_research_stop": True}),
            )
            progress = st.progress(0, text="Starting research...")
            stopped_at = None
            for i, info in enumerate(leads_info):
                if st.session_state.get("_batch_research_stop"):
                    stopped_at = i
                    break
                progress.progress((i + 1) / len(leads_info), text=f"Researching {info['name']}...")
                try:
                    from src.data.investigator_runner import run_research
                    from src.pages._enrichment_ui import do_enrich
                    report_md = run_research(info["name"], company=info.get("company"))
                    do_enrich(store, info["name"], "Lead", report_md)
                except Exception as e:
                    st.warning(f"Research failed for {info['name']}: {e}")
            st.session_state.pop("_batch_research_stop", None)
            if stopped_at is not None:
                st.info(f"Stopped after {stopped_at}/{len(leads_info)} people.")
            else:
                progress.progress(1.0, text="All research complete!")
                st.success(f"Research complete for {len(leads_info)} leads.")
            invalidate_all()
            st.rerun()
    with col_no:
        if st.button("Skip for now", use_container_width=True):
            st.rerun()


@st.dialog("Archive Batch")
def _archive_batch_dialog() -> None:
    store = get_store()
    st.write("Archive all leads in a batch. Archived leads are hidden from the default view.")
    archive_batch = st.text_input("Batch to archive", placeholder="e.g. 2026-02")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Archive", type="primary", use_container_width=True, key="dlg_archive_confirm"):
            if archive_batch:
                try:
                    count = store.archive_batch(archive_batch)
                    if count:
                        st.success(f"Archived **{count}** leads from batch '{archive_batch}'.")
                        invalidate_all()
                        st.rerun()
                    else:
                        st.info("No leads found in that batch (or already archived).")
                except Exception as e:
                    st.error(f"Failed to archive batch: {e}")
    with col2:
        if st.button("Cancel", use_container_width=True, key="dlg_archive_cancel"):
            st.rerun()


@st.dialog("Delete lead")
def _confirm_delete_lead(page_id: str, person_name: str) -> None:
    store = get_store()
    st.write(f"Delete **{person_name}** and all associated data?")
    st.caption("Removes the lead, their work history, and any matches.")
    col1, col2 = st.columns(2)
    with col1:
        if st.button("Delete", type="primary", use_container_width=True, key="dlg_del_l_confirm"):
            store.delete_lead(page_id, person_name=person_name)
            invalidate_all()
            st.rerun()
    with col2:
        if st.button("Cancel", use_container_width=True, key="dlg_del_l_cancel"):
            st.rerun()


# ── Page header ──────────────────────────────────────────────────────────────

st.title("Leads")
st.caption("Manage monthly target leads for warm introductions.")

store = get_store()

# ── Import section (consolidated) ────────────────────────────────────────────

with st.expander("Import Leads", expanded=False, icon=":material/upload:"):
    import_tab_csv, import_tab_paste, import_tab_single = st.tabs([
        "Dealigence CSV", "Paste List", "Add Single"
    ])

    # --- Tab 1: CSV import ---
    with import_tab_csv:
        st.caption(
            "Upload a CSV exported from Dealigence (e.g. Stealth Co-Founders Report). "
            "Creates leads **and** stores their work history."
        )
        with st.form("import_csv"):
            uploaded_file = st.file_uploader(
                "Dealigence CSV file",
                type=["csv"],
                help="CSV with columns: Person Name, Person Linkedin, Company Name, Employee Title, etc.",
            )
            col_a, col_b = st.columns(2)
            with col_a:
                csv_batch = st.text_input("Batch Label", value=date.today().strftime("%Y-%m"))
            with col_b:
                csv_priority = st.selectbox("Default Priority", ["High", "Medium", "Low"], index=1, key="csv_priority")
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

                if work_entries:
                    # Clean up existing work history to prevent duplicates/orphans
                    cleaned_names = set()
                    for entry in work_entries:
                        if entry.person_name not in cleaned_names:
                            store.delete_work_history(person_name=entry.person_name)
                            cleaned_names.add(entry.person_name)
                    created_history = store.store_work_history(work_entries)

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
                invalidate_all()
                st.rerun()
            except Exception as e:
                st.error(f"CSV import failed: {e}")
                logger.exception("CSV import error")

    # --- Tab 2: Paste import ---
    with import_tab_paste:
        st.caption("Paste one lead per line: `Name, Company, LinkedIn URL` (company and URL optional)")
        with st.form("import_leads"):
            batch_label = st.text_input("Batch Label", value=date.today().strftime("%Y-%m"), help="Month identifier for this batch")
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
                    invalidate_all()
                    st.rerun()

    # --- Tab 3: Add single lead ---
    with import_tab_single:
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
                    used_url = linkedin_url.strip()
                    if not used_url:
                        with st.spinner(f"Searching LinkedIn for {name}..."):
                            from src.data.linkedin_finder import find_linkedin_url
                            used_url = find_linkedin_url(name, company or None) or ""

                    lead = Lead(
                        name=name,
                        linkedin_url=used_url,
                        company_current=company,
                        title_current=title,
                        priority=lead_priority,
                        batch=batch,
                    )
                    new_page_id = store.create_lead(lead)

                    if used_url:
                        with st.spinner(f"Enriching {name} from LinkedIn..."):
                            try:
                                from src.pages._enrichment_ui import enrich_from_linkedin_url
                                count, _, new_matches = enrich_from_linkedin_url(
                                    store, name, "Lead", used_url,
                                    notion_page_id=new_page_id,
                                )
                                msg = f"Added and enriched **{name}**: {count} positions stored."
                                if new_matches:
                                    msg += f" {new_matches} new match(es) found."
                                st.session_state["add_lead_result"] = ("success", msg)
                            except Exception as e:
                                st.session_state["add_lead_result"] = (
                                    "warning",
                                    f"Added **{name}** but enrichment failed: {e}",
                                )
                    else:
                        st.session_state["add_lead_result"] = (
                            "info",
                            f"Added **{name}** — no LinkedIn profile found. Add a URL to enrich.",
                        )

                    st.session_state["post_add_research_name"] = name
                    st.session_state["post_add_research_company"] = company
                    invalidate_all()
                    st.rerun()
                except ValueError as e:
                    st.warning(str(e))
                except Exception as e:
                    st.error(f"Failed to add lead: {e}")
            elif submitted:
                st.warning("Name is required.")

# Result from previous add
if "add_lead_result" in st.session_state:
    level, msg = st.session_state.pop("add_lead_result")
    getattr(st, level)(msg)

# Post-add research prompt
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

# ── Filters ──────────────────────────────────────────────────────────────────

col_f1, col_f2 = st.columns([1, 3])
with col_f1:
    batch_filter = st.text_input("Batch", placeholder="e.g. 2026-03")
with col_f2:
    status_options = ["All", "New", "Enriched", "Matched", "Contacted", "Converted", "Archived"]
    status_filter = st.pills("Status", status_options, default="All", key="leads_status_filter")

# Header actions (Archive Batch)
if st.button("Archive Batch", help="Archive all leads in a batch to hide them from the default view"):
    _archive_batch_dialog()

# ── Load leads ───────────────────────────────────────────────────────────────

try:
    cache_key = f"leads_{batch_filter}_{status_filter}"
    if status_filter == "Archived":
        leads = cached(cache_key, lambda: store.get_all_leads(batch=batch_filter or None, status="Archived"))
    elif status_filter and status_filter != "All":
        leads = cached(cache_key, lambda: [
            l for l in store.get_active_leads(batch=batch_filter or None)
            if l.status == status_filter
        ])
    else:
        leads = cached(cache_key, lambda: store.get_active_leads(batch=batch_filter or None))
except Exception as e:
    st.error(f"Could not load leads: {e}")
    leads = []

if not leads:
    st.info("No leads found. Import a batch or add leads above.")
    st.stop()

import pandas as pd
from src.pages._table_helpers import lookup_work_history, position_cells, work_history_columns
from src.pages._enrichment_ui import enrich_from_linkedin_url

grouped_wh = cached("wh_leads", lambda: store.get_work_histories_grouped(person_type="Lead"))

# ── Status metrics (above the list for context) ─────────────────────────────

status_counts = {}
for l in leads:
    status_counts[l.status] = status_counts.get(l.status, 0) + 1
metric_cols = st.columns(max(len(status_counts), 1))
for i, (s, count) in enumerate(sorted(status_counts.items())):
    with metric_cols[i]:
        st.metric(s, count)

# ── Leads table ──────────────────────────────────────────────────────────────

st.caption(f"{len(leads)} leads shown.")

tab_detail, tab_list = st.tabs(["Detail Table", "List View"])

with tab_list:
    # Header row
    hdr_name, hdr_company, hdr_priority, hdr_batch, hdr_status, hdr_actions = st.columns([3, 2, 1, 1, 1, 1])
    hdr_name.markdown("**Name**")
    hdr_company.markdown("**Company**")
    hdr_priority.markdown("**Priority**")
    hdr_batch.markdown("**Batch**")
    hdr_status.markdown("**Status**")
    hdr_actions.markdown("**...**")

    for l in leads:
        row_key = l.notion_page_id or l.name
        col_name, col_company, col_priority, col_batch, col_status, col_actions = st.columns([3, 2, 1, 1, 1, 1])
        col_name.write(l.name)
        col_company.write(l.company_current or "")
        col_priority.write(l.priority or "")
        col_batch.write(l.batch or "")
        col_status.write(l.status or "")
        with col_actions:
            with st.popover("...", use_container_width=True):
                has_history = len(lookup_work_history(l.dealigence_person_id, l.name, grouped_wh)) > 0
                enrich_label = "Re-enrich" if has_history else "Enrich"
                if st.button(enrich_label, key=f"enrich_l_{row_key}", use_container_width=True):
                    if not l.linkedin_url:
                        st.warning(f"No LinkedIn URL for {l.name}.")
                    else:
                        with st.spinner(f"Enriching {l.name}..."):
                            try:
                                count, _, new_matches = enrich_from_linkedin_url(
                                    store, l.name, "Lead", l.linkedin_url,
                                    notion_page_id=l.notion_page_id,
                                )
                                msg = f"Enriched **{l.name}**: {count} positions stored."
                                if new_matches:
                                    msg += f" {new_matches} new match(es) found."
                                st.success(msg)
                                invalidate_all()
                                st.rerun()
                            except Exception as e:
                                st.error(f"Enrichment failed: {e}")
                if st.button("Research", key=f"research_l_{row_key}", use_container_width=True):
                    st.session_state["research_person_name"] = l.name
                    st.session_state["research_person_company"] = l.company_current or ""
                    st.session_state["research_person_type"] = "Lead"
                    st.switch_page("src/pages/research.py")
                st.divider()
                if l.notion_page_id:
                    if st.button("Delete", key=f"del_l_{row_key}", use_container_width=True):
                        _confirm_delete_lead(l.notion_page_id, l.name)

with tab_detail:
    _COL_MAP = {
        "Company":  "company_current",
        "Title":    "title_current",
        "Priority": "priority",
        "Batch":    "batch",
        "Status":   "status",
        "LinkedIn": "linkedin_url",
        "Notes":    "notes",
    }
    rows, page_ids = [], []
    for l in leads:
        entries = lookup_work_history(l.dealigence_person_id, l.name, grouped_wh)
        row = {
            "Name":     l.name,
            "Company":  l.company_current,
            "Title":    l.title_current,
            "Priority": l.priority,
            "Batch":    l.batch,
            "Status":   l.status,
            "LinkedIn": l.linkedin_url,
            "Notes":    l.notes,
        }
        row.update(position_cells(entries, enriched=len(entries) > 0))
        rows.append(row)
        page_ids.append(l.notion_page_id)

    df = pd.DataFrame(rows)
    st.data_editor(
        df,
        use_container_width=True,
        hide_index=True,
        num_rows="fixed",
        disabled=["Name"] + work_history_columns(),
        column_config={
            "Priority": st.column_config.SelectboxColumn(
                "Priority", options=["High", "Medium", "Low"]
            ),
            "Status": st.column_config.SelectboxColumn(
                "Status", options=["New", "Enriched", "Matched", "Contacted", "Converted"]
            ),
        },
        key="leads_detail_editor",
    )
    if st.button("Save changes", key="save_leads_detail"):
        edited_rows = st.session_state.get("leads_detail_editor", {}).get("edited_rows", {})
        if not edited_rows:
            st.info("No changes to save.")
        else:
            errors = []
            for row_idx, changes in edited_rows.items():
                page_id = page_ids[row_idx]
                kwargs = {}
                for col, val in changes.items():
                    if col not in _COL_MAP:
                        continue
                    kwargs[_COL_MAP[col]] = val
                if kwargs:
                    try:
                        store.update_lead(page_id, **kwargs)
                    except Exception as e:
                        errors.append(f"{rows[row_idx]['Name']}: {e}")
            if errors:
                st.error("Errors: " + "; ".join(errors))
            else:
                st.success(f"Saved {len(edited_rows)} change(s).")
                invalidate_all()
                st.rerun()
