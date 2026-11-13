"""Existing shot-chain panels grouped on the play analysis page."""

from __future__ import annotations

import streamlit as st

from src.analytics.db import AnalyticsDatabaseError
from src.security.streamlit_auth import require_login
from src.ui.advanced_page import load_matches, stop_with_footer
from src.ui.footer import render_footer
from src.ui.formatters import format_score
from src.ui.match_selector import render_match_selector
from src.ui.navigation import ensure_page_shell
from src.ui.shot_chain_panel import render_shot_chain_panel


def render_play_analysis_page(page_title: str = "Análisis de jugadas") -> None:
    ensure_page_shell(page_title)
    require_login("Gráficas avanzadas")
    st.title(page_title)

    try:
        matches = load_matches()
    except AnalyticsDatabaseError as exc:
        st.error(str(exc))
        stop_with_footer()

    if matches.empty:
        st.info("No hay partidos transformados para graficar.")
        stop_with_footer()

    match_options = {
        (
            f"{row.match_id} | {row.match_date} | "
            f"{format_score(row.home_team_name, row.home_score, row.away_score, row.away_team_name)}"
        ): int(row.match_id)
        for row in matches.itertuples(index=False)
    }
    match_id = render_match_selector("Partido", match_options, key="plays_match")
    if match_id is None:
        st.info("Selecciona un partido para continuar.")
        stop_with_footer()
    selected_match = matches.loc[matches["match_id"].eq(match_id)].iloc[0]
    home_team_name = str(selected_match.get("home_team_name") or "Local")
    away_team_name = str(selected_match.get("away_team_name") or "Visitante")
    play_tabs = st.tabs(
        ["Pases para tiro a gol", "Animación de tiros"],
        key="play_analysis_tabs",
        on_change="rerun",
    )
    for tab, animated in zip(play_tabs, (False, True)):
        if tab.open:
            with tab:
                try:
                    render_shot_chain_panel(match_id, home_team_name, away_team_name, animated=animated)
                except AnalyticsDatabaseError as exc:
                    st.error(str(exc))
    render_footer()
