from __future__ import annotations

import pandas as pd
import streamlit as st

from src.analytics.db import AnalyticsDatabaseError, query_df
from src.security.streamlit_auth import require_login
from src.ui.formatters import format_float, format_score

st.set_page_config(page_title="Partidos", layout="wide")
require_login()
st.title("Partidos")


@st.cache_data(show_spinner=False)
def load_matches() -> pd.DataFrame:
    return query_df("""
        SELECT
            m.match_id,
            m.competition_id,
            c.competition_name,
            m.season_id,
            s.season_name,
            m.match_date,
            m.home_team_name,
            m.away_team_name,
            m.home_score,
            m.away_score,
            v.total_events,
            v.total_shots,
            v.total_goals,
            v.total_xg,
            v.total_passes
        FROM vw_match_summary v
        INNER JOIN "match" m ON m.match_id = v.match_id
        LEFT JOIN competition c ON c.competition_id = m.competition_id
        LEFT JOIN season s ON s.season_id = m.season_id AND s.competition_id = m.competition_id
        WHERE v.total_events > 0
        ORDER BY m.match_date, m.match_id
        """)


try:
    matches = load_matches()
except AnalyticsDatabaseError as exc:
    st.error(str(exc))
    st.stop()

if matches.empty:
    st.info("No hay partidos transformados.")
    st.stop()

col1, col2, col3, col4 = st.columns(4)
competitions = ["Todas", *sorted(matches["competition_name"].dropna().unique().tolist())]
seasons = ["Todas", *sorted(matches["season_name"].dropna().unique().tolist())]
teams = sorted(set(matches["home_team_name"].dropna()) | set(matches["away_team_name"].dropna()))
selected_competition = col1.selectbox("Competencia", competitions)
selected_season = col2.selectbox("Temporada", seasons)
selected_team = col3.selectbox("Equipo", ["Todos", *teams])
selected_date = col4.text_input("Fecha contiene", "")

filtered = matches.copy()
if selected_competition != "Todas":
    filtered = filtered[filtered["competition_name"] == selected_competition]
if selected_season != "Todas":
    filtered = filtered[filtered["season_name"] == selected_season]
if selected_team != "Todos":
    filtered = filtered[(filtered["home_team_name"] == selected_team) | (filtered["away_team_name"] == selected_team)]
if selected_date:
    filtered = filtered[filtered["match_date"].astype(str).str.contains(selected_date, case=False, na=False)]

st.dataframe(filtered, width="stretch")

if filtered.empty:
    st.info("No hay partidos con esos filtros.")
    st.stop()

options = {
    f"{row.match_id} | {row.match_date} | {row.home_team_name} {row.home_score}-{row.away_score} {row.away_team_name}": int(
        row.match_id
    )
    for row in filtered.itertuples(index=False)
}
selected_label = st.selectbox("Seleccionar partido", list(options.keys()))
selected_match_id = options[selected_label]
row = filtered[filtered["match_id"] == selected_match_id].iloc[0]

st.subheader("Resumen")
metric_cols = st.columns(5)
metric_cols[0].metric("match_id", int(row["match_id"]))
metric_cols[1].metric("Fecha", row["match_date"])
metric_cols[2].metric(
    "Marcador", format_score(row["home_team_name"], row["home_score"], row["away_score"], row["away_team_name"])
)
metric_cols[3].metric("Eventos", int(row["total_events"]))
metric_cols[4].metric("xG total", format_float(row["total_xg"]))

st.write(
    {
        "competencia": row.get("competition_name"),
        "temporada": row.get("season_name"),
        "tiros": int(row["total_shots"]),
        "goles": int(row["total_goals"]),
        "pases": int(row["total_passes"]),
    }
)
