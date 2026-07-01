from __future__ import annotations

import inspect
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.analytics.advanced_charts import (
    build_advanced_chart_bundle,
    get_match_teams,
    get_players_for_heatmap,
    plot_event_heatmap,
    plot_broadcast_momentum,
    plot_momentum,
    plot_pass_map,
    plot_presence_zones,
    plot_recoveries_losses,
    plot_shots_advanced,
)
from src.analytics.db import AnalyticsDatabaseError, query_df
from src.reports.tab_pdf import save_analysis_tab_pdf
from src.security.streamlit_auth import require_login
from src.ui.downloads import render_download_button
from src.ui.footer import render_footer
from src.ui.formatters import format_score
from src.ui.pitch_charts import plot_pass_network

st.set_page_config(page_title="Gráficas avanzadas", layout="wide")
require_login()
st.title("Gráficas avanzadas")


def stop_with_footer() -> None:
    render_footer()
    st.stop()


def supports_chart_args(function: object, *arg_names: str) -> bool:
    try:
        parameters = inspect.signature(function).parameters
    except (TypeError, ValueError):
        return True
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters.values()):
        return True
    return all(name in parameters for name in arg_names)


def plot_shots_advanced_page(rows: list[dict[str, object]], home_team: str, away_team: str):
    if supports_chart_args(plot_shots_advanced, "home_team_name", "away_team_name"):
        return plot_shots_advanced(rows, home_team_name=home_team, away_team_name=away_team)
    return plot_shots_advanced(rows)


def plot_pass_map_page(rows: list[dict[str, object]], home_team: str, away_team: str):
    if supports_chart_args(plot_pass_map, "home_team_name", "away_team_name"):
        return plot_pass_map(rows, home_team_name=home_team, away_team_name=away_team)
    return plot_pass_map(rows)


def plot_recoveries_losses_page(rows: list[dict[str, object]], home_team: str, away_team: str):
    if supports_chart_args(plot_recoveries_losses, "home_team_name", "away_team_name"):
        return plot_recoveries_losses(rows, home_team_name=home_team, away_team_name=away_team)
    return plot_recoveries_losses(rows)


def plot_momentum_page(rows: list[dict[str, object]], home_team: str, away_team: str):
    if supports_chart_args(plot_momentum, "home_team_name", "away_team_name"):
        return plot_momentum(rows, home_team_name=home_team, away_team_name=away_team)
    return plot_momentum(rows)


def render_pdf_button(
    tab_name: str,
    title: str,
    sections: list[dict[str, object]],
    figures: list[object] | None = None,
    key: str | None = None,
) -> None:
    button_key = key or f"advanced_pdf_{tab_name}_{match_id}_{selected_team}_{selected_player_label}"
    result_key = f"{button_key}_result"
    if st.button("Exportar PDF de esta pestaña", key=button_key):
        st.session_state[result_key] = save_analysis_tab_pdf(tab_name, match_id, title, sections, figures or [])

    result = st.session_state.get(result_key)
    if not result:
        return

    if result.get("status") == "generated":
        st.success(f"PDF exportado: `{result.get('path')}`")
        render_download_button(result.get("path"), "PDF", f"{button_key}_download")
    else:
        st.error(f"No se pudo exportar PDF: {result.get('error_message')}")
    warnings = result.get("warnings") or []
    if warnings:
        st.info(" ".join(str(warning) for warning in warnings))


def table_rows(rows: object, limit: int = 24) -> list[dict[str, object]]:
    frame = rows if isinstance(rows, pd.DataFrame) else pd.DataFrame(rows)
    if frame.empty:
        return []
    return frame.head(limit).to_dict("records")


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
selected_match_label = st.selectbox("Partido", list(match_options.keys()))
match_id = match_options[selected_match_label]
selected_match = matches.loc[matches["match_id"].eq(match_id)].iloc[0]
home_team_name = str(selected_match.get("home_team_name") or "Local")
away_team_name = str(selected_match.get("away_team_name") or "Visitante")
match_score_label = format_score(
    selected_match.get("home_team_name"),
    selected_match.get("home_score"),
    selected_match.get("away_score"),
    selected_match.get("away_team_name"),
)

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
    stop_with_footer()

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
    heatmap_fig = plot_event_heatmap(
        bundle.get("events", []),
        home_team_name=home_team_name,
        away_team_name=away_team_name,
    )
    st.plotly_chart(
        heatmap_fig,
        width="stretch",
    )
    render_pdf_button(
        "graficas_avanzadas_calor",
        f"Mapa de calor | {match_score_label}",
        [{"heading": "Eventos", "rows": table_rows(bundle.get("events", []))}],
        [heatmap_fig],
        key=f"advanced_pdf_heatmap_{match_id}_{selected_team}_{selected_player_label}",
    )

with chart_tabs[1]:
    st.subheader("Mapa de tiros")
    shots_fig = plot_shots_advanced_page(bundle.get("shots", []), home_team_name, away_team_name)
    st.plotly_chart(shots_fig, width="stretch")
    render_pdf_button(
        "graficas_avanzadas_tiros",
        f"Mapa de tiros | {match_score_label}",
        [{"heading": "Tiros", "rows": table_rows(bundle.get("shots", []))}],
        [shots_fig],
        key=f"advanced_pdf_shots_{match_id}_{selected_team}",
    )

with chart_tabs[2]:
    st.subheader("Mapa de pases")
    st.caption("Muestra hasta 350 flechas para mantener la interacción fluida.")
    pass_map_fig = plot_pass_map_page(bundle.get("passes", []), home_team_name, away_team_name)
    st.plotly_chart(pass_map_fig, width="stretch")
    render_pdf_button(
        "graficas_avanzadas_pases",
        f"Mapa de pases | {match_score_label}",
        [{"heading": "Pases", "rows": table_rows(bundle.get("passes", []))}],
        [pass_map_fig],
        key=f"advanced_pdf_passes_{match_id}_{selected_team}",
    )

with chart_tabs[3]:
    st.subheader("Red de pases simple")
    pass_network_fig = None
    pass_network_sections: list[dict[str, object]] = []
    if team_filter is None:
        st.info("Selecciona un equipo específico para construir la red de pases.")
        pass_network_sections.append(
            {"heading": "Red de pases", "paragraphs": ["Selecciona un equipo específico para construir la red de pases."]}
        )
    elif bundle.get("pass_network"):
        pass_network_fig = plot_pass_network(bundle["pass_network"])
        st.plotly_chart(pass_network_fig, width="stretch")
        network = bundle.get("pass_network") or {}
        pass_network_sections.extend(
            [
                {
                    "heading": "Nodos",
                    "rows": table_rows(network.get("nodes", []) if isinstance(network, dict) else []),
                },
                {
                    "heading": "Conexiones",
                    "rows": table_rows(network.get("edges", []) if isinstance(network, dict) else []),
                },
            ]
        )
    else:
        st.info("No hay datos suficientes para red de pases.")
        pass_network_sections.append({"heading": "Red de pases", "paragraphs": ["No hay datos suficientes para red de pases."]})
    render_pdf_button(
        "graficas_avanzadas_red_pases",
        f"Red de pases | {match_score_label}",
        pass_network_sections,
        [pass_network_fig] if pass_network_fig is not None else [],
        key=f"advanced_pdf_pass_network_{match_id}_{selected_team}",
    )

with chart_tabs[4]:
    st.subheader("Mapa de recuperaciones y pérdidas")
    recoveries_losses_fig = plot_recoveries_losses_page(bundle.get("recovery_loss", []), home_team_name, away_team_name)
    st.plotly_chart(
        recoveries_losses_fig,
        width="stretch",
    )
    render_pdf_button(
        "graficas_avanzadas_recuperaciones_perdidas",
        f"Recuperaciones y pérdidas | {match_score_label}",
        [{"heading": "Recuperaciones y pérdidas", "rows": table_rows(bundle.get("recovery_loss", []))}],
        [recoveries_losses_fig],
        key=f"advanced_pdf_recoveries_losses_{match_id}_{selected_team}",
    )

with chart_tabs[5]:
    st.subheader("Momentum por intervalos")
    momentum_fig = plot_momentum_page(bundle.get("momentum", []), home_team_name, away_team_name)
    st.plotly_chart(momentum_fig, width="stretch")
    st.subheader("Momento del partido")
    broadcast_momentum_fig = plot_broadcast_momentum(
        bundle.get("momentum", []),
        home_team_name,
        away_team_name,
        shots=bundle.get("match_shots", bundle.get("shots", [])),
    )
    st.plotly_chart(
        broadcast_momentum_fig,
        width="stretch",
    )
    render_pdf_button(
        "graficas_avanzadas_momentum",
        f"Momentum | {match_score_label}",
        [{"heading": "Momentum por intervalos", "rows": table_rows(bundle.get("momentum", []))}],
        [momentum_fig, broadcast_momentum_fig],
        key=f"advanced_pdf_momentum_{match_id}_{selected_team}",
    )

with chart_tabs[6]:
    st.subheader("Zonas de dominio o presencia")
    zones_fig = plot_presence_zones(bundle.get("zones", []), selected_team=team_filter)
    st.plotly_chart(zones_fig, width="stretch")
    zones_frame = pd.DataFrame(bundle.get("zones", []))
    sorted_zones_frame = (
        zones_frame.sort_values(["share_pct", "events"], ascending=False)
        if {"share_pct", "events"}.issubset(zones_frame.columns)
        else zones_frame
    )
    if not sorted_zones_frame.empty:
        st.dataframe(sorted_zones_frame, width="stretch")
    render_pdf_button(
        "graficas_avanzadas_zonas",
        f"Zonas | {match_score_label}",
        [{"heading": "Zonas", "rows": table_rows(sorted_zones_frame)}],
        [zones_fig],
        key=f"advanced_pdf_zones_{match_id}_{selected_team}",
    )

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
    selected_frame = pd.DataFrame(data_frames[selected_table])
    st.dataframe(selected_frame, width="stretch")
    render_pdf_button(
        "graficas_avanzadas_datos",
        f"Datos base | {match_score_label}",
        [{"heading": selected_table, "rows": table_rows(selected_frame)}],
        [],
        key=f"advanced_pdf_data_{match_id}_{selected_table}",
    )

render_footer()
