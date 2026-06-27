from __future__ import annotations

import pandas as pd
import streamlit as st

from src.analytics.advanced_charts import (
    build_advanced_chart_bundle,
    get_match_teams,
    get_players_for_heatmap,
    plot_event_heatmap,
    plot_momentum,
    plot_pass_map,
    plot_presence_zones,
    plot_recoveries_losses,
    plot_shots_advanced,
)
from src.analytics.db import AnalyticsDatabaseError, query_df
from src.security.streamlit_auth import require_login
from src.ui.formatters import format_score
from src.ui.pitch_charts import plot_pass_network

st.set_page_config(page_title="Gráficas avanzadas", layout="wide")
require_login()
st.title("Gráficas avanzadas")


@st.cache_data(show_spinner=False)
def load_matches() -> pd.DataFrame:
    return query_df("""
        SELECT
            match_id,
            match_date,
            home_team_name,
            away_team_name,
            home_score,
            away_score,
            total_events
        FROM vw_match_summary
        WHERE total_events > 0
        ORDER BY match_date, match_id
        """)


@st.cache_data(show_spinner=False)
def load_bundle(match_id: int, team_name: str | None, player_id: int | None) -> dict[str, object]:
    return build_advanced_chart_bundle(match_id, team_name=team_name, player_id=player_id)


try:
    matches = load_matches()
except AnalyticsDatabaseError as exc:
    st.error(str(exc))
    st.stop()

if matches.empty:
    st.info("No hay partidos transformados para graficar.")
    st.stop()

match_options = {
    (
        f"{row.match_id} | {row.match_date} | "
        f"{format_score(row.home_team_name, row.home_score, row.away_score, row.away_team_name)}"
    ): int(row.match_id)
    for row in matches.itertuples(index=False)
}
selected_match_label = st.selectbox("Partido", list(match_options.keys()))
match_id = match_options[selected_match_label]

teams = get_match_teams(match_id)
selected_team = st.selectbox("Equipo", ["Todos", *teams])
team_filter = None if selected_team == "Todos" else selected_team

players = get_players_for_heatmap(match_id, team_filter)
player_options = {"Todos": None}
player_options.update(
    {
        f"{row.get('player_name')} | {row.get('team_name')} | eventos {row.get('events')} | id {row.get('player_id')}": int(
            row["player_id"]
        )
        for row in players
        if row.get("player_id") is not None
    }
)
selected_player_label = st.selectbox("Jugador para mapa de calor", list(player_options.keys()))
player_filter = player_options[selected_player_label]

try:
    bundle = load_bundle(match_id, team_filter, player_filter)
except AnalyticsDatabaseError as exc:
    st.error(str(exc))
    st.stop()

summary_cols = st.columns(5)
summary_cols[0].metric("Eventos", len(bundle.get("events", [])))
summary_cols[1].metric("Tiros", len(bundle.get("shots", [])))
summary_cols[2].metric("Pases", len(bundle.get("passes", [])))
summary_cols[3].metric("Rec/pérdidas", len(bundle.get("recovery_loss", [])))
summary_cols[4].metric("Zonas", len(bundle.get("zones", [])))

chart_tabs = st.tabs(
    [
        "Calor",
        "Tiros",
        "Pases",
        "Red de pases",
        "Recuperaciones/pérdidas",
        "Momentum",
        "Zonas",
        "Datos",
    ]
)

with chart_tabs[0]:
    st.subheader("Mapa de calor de eventos o jugador")
    st.plotly_chart(plot_event_heatmap(bundle.get("events", [])), width="stretch")

with chart_tabs[1]:
    st.subheader("Mapa de tiros")
    st.plotly_chart(plot_shots_advanced(bundle.get("shots", [])), width="stretch")

with chart_tabs[2]:
    st.subheader("Mapa de pases")
    st.caption("Muestra hasta 350 flechas para mantener la interacción fluida.")
    st.plotly_chart(plot_pass_map(bundle.get("passes", [])), width="stretch")

with chart_tabs[3]:
    st.subheader("Red de pases simple")
    if team_filter is None:
        st.info("Selecciona un equipo específico para construir la red de pases.")
    elif bundle.get("pass_network"):
        st.plotly_chart(plot_pass_network(bundle["pass_network"]), width="stretch")
    else:
        st.info("No hay datos suficientes para red de pases.")

with chart_tabs[4]:
    st.subheader("Mapa de recuperaciones y pérdidas")
    st.plotly_chart(plot_recoveries_losses(bundle.get("recovery_loss", [])), width="stretch")

with chart_tabs[5]:
    st.subheader("Momentum por intervalos")
    st.plotly_chart(plot_momentum(bundle.get("momentum", [])), width="stretch")

with chart_tabs[6]:
    st.subheader("Zonas de dominio o presencia")
    st.plotly_chart(plot_presence_zones(bundle.get("zones", []), selected_team=team_filter), width="stretch")
    zones_frame = pd.DataFrame(bundle.get("zones", []))
    if not zones_frame.empty:
        st.dataframe(zones_frame.sort_values(["share_pct", "events"], ascending=False), width="stretch")

with chart_tabs[7]:
    st.subheader("Datos base")
    data_frames = {
        "eventos": bundle.get("events", []),
        "tiros": bundle.get("shots", []),
        "pases": bundle.get("passes", []),
        "recuperaciones_perdidas": bundle.get("recovery_loss", []),
        "momentum": bundle.get("momentum", []),
        "zonas": bundle.get("zones", []),
    }
    selected_table = st.selectbox("Tabla", list(data_frames.keys()))
    st.dataframe(pd.DataFrame(data_frames[selected_table]), width="stretch")
