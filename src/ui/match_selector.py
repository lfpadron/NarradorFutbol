"""One match selection per session, shared by every page and section."""

from __future__ import annotations

from collections.abc import Mapping

import streamlit as st

from src.ui.i18n import t

MATCH_SELECTION_KEY = "selected_match_id"


def get_selected_match_id() -> int | None:
    return st.session_state.get(MATCH_SELECTION_KEY)


def _remember_match(widget_key: str) -> None:
    st.session_state[MATCH_SELECTION_KEY] = st.session_state[widget_key]


def _clear_match() -> None:
    st.session_state[MATCH_SELECTION_KEY] = None


def render_match_selector(label: str, options: Mapping[str, int], *, key: str) -> int | None:
    labels = {int(match_id): text for text, match_id in options.items()}
    selected = get_selected_match_id()
    if selected not in labels:
        selected = None
        st.session_state[MATCH_SELECTION_KEY] = None

    # Keep the durable selection separate from widget state, which Streamlit
    # removes when its page is no longer rendered. Store IDs, not translated labels.
    st.session_state[key] = selected
    selector, clear = st.columns([5, 1], vertical_alignment="bottom")
    with selector:
        value = st.selectbox(
            label,
            list(labels),
            index=None,
            format_func=labels.__getitem__,
            placeholder=str(t("Selecciona un partido")),
            key=key,
            on_change=_remember_match,
            args=(key,),
        )
    with clear:
        st.button("Limpiar", key=f"{key}_clear", on_click=_clear_match, disabled=selected is None, width="stretch")
    return value
