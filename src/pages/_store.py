"""Shared NotionStore accessor — single definition used by all pages."""

from __future__ import annotations

import streamlit as st

from src.data.notion_store import NotionStore


def get_store() -> NotionStore:
    if "notion_store" not in st.session_state:
        st.session_state.notion_store = NotionStore()
    return st.session_state.notion_store
