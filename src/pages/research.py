"""Research page: AI-powered background reports for contacts and leads."""

from __future__ import annotations

import logging

import streamlit as st

from src.data.investigator_runner import (
    delete_cached_report,
    extract_work_history_from_report,
    get_cached_report,
    run_research,
)
from src.pages._store import get_store

logger = logging.getLogger(__name__)


st.title("Research")
st.caption("AI-powered background reports using public web sources (DuckDuckGo + LLM synthesis).")

# ── Person selection ───────────────────────────────────────────────────────────

person_name = st.session_state.get("research_person_name", "")
person_company = st.session_state.get("research_person_company", "")
person_type = st.session_state.get("research_person_type", "")

col1, col2, col3 = st.columns([3, 3, 2])
with col1:
    name_input = st.text_input("Person name", value=person_name)
with col2:
    company_input = st.text_input("Company (optional)", value=person_company)
with col3:
    st.write("")
    st.write("")
    run_btn = st.button("Run Research", type="primary", use_container_width=True)

name = name_input.strip()
company = company_input.strip() or None

if not name and not run_btn:
    st.info("Enter a name above and click **Run Research**, or navigate here from a Contacts or Leads row.")
    st.stop()

# ── Check for cached report ────────────────────────────────────────────────────

cached = get_cached_report(name) if name else None

if cached and not run_btn:
    st.success(f"Showing cached report for **{name}**. Click **Refresh** to fetch updated data.")
    col_r1, col_r2 = st.columns([1, 5])
    with col_r1:
        if st.button("Refresh Report"):
            delete_cached_report(name)
            st.rerun()
    report_md = cached
elif run_btn and name:
    force = run_btn and bool(cached)
    with st.status(f"Researching **{name}**...", expanded=True) as status_bar:
        try:
            status_bar.write("Searching public web sources...")
            report_md = run_research(name, company=company, force_refresh=force)
            status_bar.update(label=f"Research complete for **{name}**.", state="complete")
        except TimeoutError:
            status_bar.update(label="Research timed out.", state="error")
            st.error("Research timed out after 120 seconds. Try again.")
            st.stop()
        except Exception as e:
            status_bar.update(label="Research failed.", state="error")
            st.error(f"Research failed: {e}")
            logger.exception("Research error for %s", name)
            st.stop()
else:
    st.stop()

# ── Enrich work history from report ───────────────────────────────────────────

if person_type and name:
    store = get_store()
    auto_expand = bool(person_type and name)
    with st.expander("Extract & Store Work History", expanded=auto_expand):
        st.markdown(
            "Parse the Professional Profile section of this report and store "
            "the work history in Notion (same as LinkedIn enrichment)."
        )
        if st.button("Extract Work History from Report", key="extract_wh"):
            with st.spinner("Extracting work history..."):
                try:
                    from src.pages._enrichment_ui import do_enrich
                    count, positions, new_matches = do_enrich(
                        store, name, person_type, report_md
                    )
                    msg = f"Stored **{count}** positions for {name}."
                    if new_matches:
                        msg += f" Found **{new_matches}** new match(es)."
                    st.success(msg)
                    for p in positions:
                        advisory = " *(advisory)*" if p.get("is_advisory") else ""
                        st.write(f"- {p.get('title', '?')} @ {p.get('employer_name', '?')}{advisory}")
                except Exception as e:
                    st.error(f"Failed to extract work history: {e}")

st.divider()

# ── Report display ─────────────────────────────────────────────────────────────

st.markdown(report_md)
