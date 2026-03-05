"""Streamlit entry point for the VC Connections app."""

import streamlit as st

st.set_page_config(
    page_title="VC Connections",
    page_icon="🔗",
    layout="wide",
    initial_sidebar_state="expanded",
)


def main():
    pages = {
        "Dashboard": st.Page("src/pages/dashboard.py", title="Dashboard", icon=":material/dashboard:"),
        "Contacts": st.Page("src/pages/contacts.py", title="Contacts", icon=":material/people:"),
        "Leads": st.Page("src/pages/leads.py", title="Leads", icon=":material/target:"),
        "Matches": st.Page("src/pages/matches.py", title="Matches", icon=":material/link:"),
        "Settings": st.Page("src/pages/settings.py", title="Settings", icon=":material/settings:"),
    }
    pg = st.navigation(list(pages.values()))
    pg.run()


if __name__ == "__main__":
    main()
