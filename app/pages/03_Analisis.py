from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import streamlit as st

from src.analytics.ai_context import build_ai_match_context
from src.analytics.db import AnalyticsDatabaseError, query_df
from src.analytics.key_moments import get_key_moments
from src.analytics.match_summary import get_match_summary
from src.analytics.momentum import get_momentum_by_interval
from src.analytics.pass_analysis import get_pass_summary, get_progressive_passes
from src.analytics.possession_analysis import get_possession_summary
from src.analytics.shot_analysis import get_shot_summary, get_shots
from src.analytics.team_stats import get_team_stats
from src.config import ANALYTICS_EXPORTS_DIR
from src.ingestion.utils import to_jsonable
from src.ui.charts import momentum_line, shot_count_bar, xg_bar
from src.ui.formatters import format_float, format_score


st.set_page_config(page_title="Analisis", layout="wide")
st.title("Analisis")


@st.cache_data(show_spinner=False)
def load_match_options() -> pd.DataFrame:
    return query_df(
        """
        SELECT match_id, match_date, home_team_name, away_team_name, home_score, away_score
        FROM vw_match_summary
        WHERE total_events > 0
        ORDER BY match_date, match_id
        """
    )


@st.cache_data(show_spinner=False)
def load_context(match_id: int) -> dict[str, object]:
    return build_ai_match_context(match_id)


@st.cache_data(show_spinner=False)
def load_detail(match_id: int) -> dict[str, object]:
    return {
        "summary": get_match_summary(match_id),
        "team_stats": get_team_stats(match_id),
        "shots": get_shots(match_id),
        "shot_summary": get_shot_summary(match_id),
        "pass_summary": get_pass_summary(match_id),
        "progressive_passes": get_progressive_passes(match_id),
        "possession_summary": get_possession_summary(match_id),
        "momentum": get_momentum_by_interval(match_id),
        "key_moments": get_key_moments(match_id),
    }


try:
    matches = load_match_options()
except AnalyticsDatabaseError as exc:
    st.error(str(exc))
    st.stop()

if matches.empty:
    st.info("No hay partidos transformados para analizar.")
    st.stop()

options = {
    f"{row.match_id} | {row.match_date} | {row.home_team_name} {row.home_score}-{row.away_score} {row.away_team_name}": int(row.match_id)
    for row in matches.itertuples(index=False)
}
selected_label = st.selectbox("Partido", list(options.keys()))
match_id = options[selected_label]

try:
    detail = load_detail(match_id)
    context = load_context(match_id)
except (AnalyticsDatabaseError, ValueError) as exc:
    st.error(str(exc))
    st.stop()

summary = detail["summary"]
team_stats = detail["team_stats"]

st.subheader("Resumen del partido")
cols = st.columns(5)
cols[0].metric(
    "Marcador",
    format_score(
        summary.get("home_team_name"),
        summary.get("home_score"),
        summary.get("away_score"),
        summary.get("away_team_name"),
    ),
)
cols[1].metric("Tiros", summary.get("total_shots", 0))
cols[2].metric("Goles", summary.get("total_goals", 0))
cols[3].metric("xG total", format_float(summary.get("total_xg")))
cols[4].metric("Pases", summary.get("total_passes", 0))

st.subheader("Estadisticas por equipo")
st.dataframe(pd.DataFrame(team_stats), width="stretch")

st.subheader("Top jugadores")
st.dataframe(pd.DataFrame(context.get("top_players", [])), width="stretch")

st.subheader("Tiros")
shot_summary = detail["shot_summary"]
shot_cols = st.columns(3)
shot_cols[0].metric("Tiros", shot_summary.get("total_shots", 0))
shot_cols[1].metric("Goles", shot_summary.get("total_goals", 0))
shot_cols[2].metric("xG", format_float(shot_summary.get("total_xg")))
chart_cols = st.columns(2)
chart_cols[0].plotly_chart(shot_count_bar(team_stats), width="stretch")
chart_cols[1].plotly_chart(xg_bar(team_stats), width="stretch")
st.dataframe(pd.DataFrame(detail["shots"]), width="stretch")

st.subheader("Pases")
pass_summary = detail["pass_summary"]
pass_cols = st.columns(5)
pass_cols[0].metric("Pases", pass_summary.get("total_passes", 0))
pass_cols[1].metric("Completados", pass_summary.get("successful_passes", 0))
pass_cols[2].metric("% completados", f"{pass_summary.get('pass_completion_pct')}%")
pass_cols[3].metric("Asistencias", pass_summary.get("assists", 0))
pass_cols[4].metric("Pases clave", pass_summary.get("key_passes", 0))
st.write("Pases progresivos")
st.dataframe(pd.DataFrame(detail["progressive_passes"]), width="stretch")

st.subheader("Posesion")
possession = detail["possession_summary"]
pos_cols = st.columns(4)
pos_cols[0].metric("Posesiones", possession.get("possessions_total", 0))
pos_cols[1].metric("Prom. eventos", format_float(possession.get("avg_events_per_possession")))
pos_cols[2].metric("Terminan en tiro", possession.get("possessions_ending_in_shot", 0))
pos_cols[3].metric("Terminan en gol", possession.get("possessions_ending_in_goal", 0))
st.write(possession.get("possessions_by_team", {}))

st.subheader("Momentum")
momentum = detail["momentum"]
st.plotly_chart(momentum_line(momentum), width="stretch")
st.dataframe(pd.DataFrame(momentum), width="stretch")

st.subheader("Momentos clave")
key_moments = detail["key_moments"]
if not key_moments:
    st.info("No se detectaron momentos clave.")
else:
    for moment in key_moments:
        st.markdown(
            f"**{moment.get('minute')}:{int(moment.get('second') or 0):02d}** "
            f"`{moment.get('type')}` {moment.get('title')}  \n"
            f"{moment.get('description')}"
        )

st.subheader("Exportar JSON")
if st.button("Exportar contexto analitico"):
    ANALYTICS_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    output_path = ANALYTICS_EXPORTS_DIR / f"analysis.match-{match_id}.json"
    with output_path.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(context), file, ensure_ascii=False, indent=2)
        file.write("\n")
    st.success(f"JSON exportado: {output_path.as_posix()}")
