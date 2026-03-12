"""TTL-based session-state caching for Notion data."""

from __future__ import annotations

import time

import streamlit as st

_DEFAULT_TTL = 300  # seconds


def cached(key: str, loader, ttl: int = _DEFAULT_TTL):
    """Return cached data from session_state, re-fetching if expired."""
    ts_key = f"{key}__ts"
    now = time.time()
    if key in st.session_state and (now - st.session_state.get(ts_key, 0)) < ttl:
        return st.session_state[key]
    data = loader()
    st.session_state[key] = data
    st.session_state[ts_key] = now
    return data


def invalidate(*keys: str) -> None:
    """Clear specific cache entries."""
    for key in keys:
        st.session_state.pop(key, None)
        st.session_state.pop(f"{key}__ts", None)


def invalidate_all() -> None:
    """Clear every cached entry (any key ending with ``__ts``)."""
    for key in list(st.session_state):
        if key.endswith("__ts"):
            base = key[:-4]
            st.session_state.pop(base, None)
            st.session_state.pop(key, None)
