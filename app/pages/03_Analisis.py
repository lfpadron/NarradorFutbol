from __future__ import annotations

import json

import pandas as pd
import streamlit as st

from src.analytics.ai_context import build_ai_match_context
from src.analytics.db import AnalyticsDatabaseError, query_df
from src.analytics.key_moments import get_key_moments
from src.analytics.match_summary import get_match_summary
from src.analytics.momentum import get_momentum_by_interval
from src.analytics.pass_analysis import get_pass_network, get_pass_summary, get_progressive_passes
from src.analytics.possession_analysis import get_possession_summary
from src.analytics.pressure_analysis import get_pressures
from src.analytics.shot_analysis import get_shot_summary, get_shots
from src.analytics.team_stats import get_team_stats
from src.config import ANALYTICS_EXPORTS_DIR
from src.ingestion.utils import to_jsonable
from src.narrative.config import SUPPORTED_TONES, has_openai_api_key
from src.narrative.narrative_store import save_narrative
from src.narrative.narrator import generate_match_narrative
from src.narrative.quality_checker import evaluate_narrative_quality
from src.narrative.review_report import build_review_report, save_review_report
from src.narrative.tone_comparison import compare_tones
from src.ui.charts import momentum_line, shot_count_bar, xg_bar
from src.ui.formatters import format_float, format_pct, format_score
from src.ui.pitch_charts import (
    plot_cumulative_xg,
    plot_pass_network,
    plot_pressure_map,
    plot_progressive_passes,
    plot_shot_map,
)


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
        "pressures": get_pressures(match_id),
    }


@st.cache_data(show_spinner=False)
def load_pass_network(match_id: int, team_name: str) -> dict[str, object]:
    return get_pass_network(match_id, team_name)


def team_options(team_stats: list[dict[str, object]]) -> list[str]:
    return [str(row["team_name"]) for row in team_stats if row.get("team_name")]


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
teams = team_options(team_stats)

st.caption(
    f"{summary.get('match_date')} | "
    f"{format_score(summary.get('home_team_name'), summary.get('home_score'), summary.get('away_score'), summary.get('away_team_name'))}"
)

tabs = st.tabs(
    [
        "Resumen",
        "Tiros y xG",
        "Pases",
        "Presión",
        "Momentum",
        "Análisis avanzado",
        "Narrador AI",
        "Momentos clave",
        "Datos",
    ]
)

with tabs[0]:
    st.subheader("Resumen del partido")
    st.write("Vista general del partido y métricas agregadas por equipo y jugador.")
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

    st.subheader("Estadísticas por equipo")
    st.dataframe(pd.DataFrame(team_stats), width="stretch")

    st.subheader("Top jugadores")
    st.dataframe(pd.DataFrame(context.get("top_players", [])), width="stretch")

with tabs[1]:
    st.subheader("Tiros y xG")
    st.write("Mapa de tiros sobre cancha StatsBomb 120x80 y evolución de xG acumulado.")
    shot_summary = detail["shot_summary"]
    shot_cols = st.columns(4)
    shot_cols[0].metric("Tiros", shot_summary.get("total_shots", 0))
    shot_cols[1].metric("Goles", shot_summary.get("total_goals", 0))
    shot_cols[2].metric("xG", format_float(shot_summary.get("total_xg")))
    best_chance = shot_summary.get("best_chance")
    shot_cols[3].metric(
        "Mejor ocasión",
        format_float(best_chance.get("shot_statsbomb_xg") if best_chance else None),
    )

    st.plotly_chart(
        plot_shot_map(
            detail["shots"],
            str(summary.get("home_team_name") or ""),
            str(summary.get("away_team_name") or ""),
        ),
        width="stretch",
    )
    st.plotly_chart(plot_cumulative_xg(detail["shots"]), width="stretch")

    chart_cols = st.columns(2)
    chart_cols[0].plotly_chart(shot_count_bar(team_stats), width="stretch")
    chart_cols[1].plotly_chart(xg_bar(team_stats), width="stretch")
    st.dataframe(pd.DataFrame(detail["shots"]), width="stretch")

with tabs[2]:
    st.subheader("Pases")
    st.write("Resumen de pases, mapa de pases progresivos y red simple de pases completados por equipo.")
    pass_summary = detail["pass_summary"]
    pass_cols = st.columns(5)
    pass_cols[0].metric("Pases", pass_summary.get("total_passes", 0))
    pass_cols[1].metric("Completados", pass_summary.get("successful_passes", 0))
    pass_cols[2].metric("% completados", format_pct(pass_summary.get("pass_completion_pct")))
    pass_cols[3].metric("Asistencias", pass_summary.get("assists", 0))
    pass_cols[4].metric("Pases clave", pass_summary.get("key_passes", 0))

    pass_team_filter = st.selectbox("Equipo para mapa de pases progresivos", ["Todos", *teams])
    st.plotly_chart(
        plot_progressive_passes(
            detail["progressive_passes"],
            None if pass_team_filter == "Todos" else pass_team_filter,
        ),
        width="stretch",
    )
    st.dataframe(pd.DataFrame(detail["progressive_passes"]), width="stretch")

    if teams:
        network_team = st.selectbox("Equipo para red de pases", teams)
        st.plotly_chart(plot_pass_network(load_pass_network(match_id, network_team)), width="stretch")
    else:
        st.info("No hay equipos disponibles para construir red de pases.")

with tabs[3]:
    st.subheader("Presión")
    st.write("Mapa de eventos de presión y counterpress. Maneja partidos sin presiones registradas.")
    pressure_team_filter = st.selectbox("Equipo para presiones", ["Todos", *teams])
    st.plotly_chart(
        plot_pressure_map(
            detail["pressures"],
            None if pressure_team_filter == "Todos" else pressure_team_filter,
        ),
        width="stretch",
    )
    st.dataframe(pd.DataFrame(detail["pressures"]), width="stretch")

with tabs[4]:
    st.subheader("Momentum")
    st.write(
        "Fórmula MVP: tiros * 3 + xG * 10 + entradas al tercio final * 1 "
        "+ eventos ofensivos * 0.5."
    )
    momentum = detail["momentum"]
    st.plotly_chart(momentum_line(momentum), width="stretch")
    st.dataframe(pd.DataFrame(momentum), width="stretch")

with tabs[5]:
    st.subheader("Análisis avanzado")

    dominance = context.get("dominance", [])
    dominance_frame = pd.DataFrame(dominance)
    if not dominance_frame.empty:
        leader = dominance[0]
        dominance_cols = st.columns(4)
        dominance_cols[0].metric("Dominio estimado", leader.get("team_name"))
        dominance_cols[1].metric("Score dominio", format_float(leader.get("dominance_score")))
        dominance_cols[2].metric("Tiros", leader.get("shots", 0))
        dominance_cols[3].metric("xG", format_float(leader.get("xg")))
        st.dataframe(dominance_frame, width="stretch")
    else:
        st.info("No hay métricas de dominio para este partido.")

    xg_breakdown = context.get("xg_breakdown", [])
    st.subheader("Desglose xG")
    st.dataframe(pd.DataFrame(xg_breakdown), width="stretch")

    impact_players = context.get("impact_players", [])
    st.subheader("Jugadores de impacto")
    st.dataframe(pd.DataFrame(impact_players), width="stretch")

    dangerous_attacks = context.get("dangerous_attacks", [])
    st.subheader("Ataques peligrosos")
    attack_cols = st.columns(3)
    attack_cols[0].metric("Total", len(dangerous_attacks))
    attack_cols[1].metric(
        "Con tiro",
        sum(1 for attack in dangerous_attacks if attack.get("has_shot")),
    )
    attack_cols[2].metric(
        "Con gol",
        sum(1 for attack in dangerous_attacks if attack.get("has_goal")),
    )
    st.dataframe(pd.DataFrame(dangerous_attacks), width="stretch")

    st.subheader("Intervalos de dominio")
    st.dataframe(pd.DataFrame(context.get("dominance_intervals", [])), width="stretch")

    validation = context.get("validation", {})
    status = validation.get("status", "UNKNOWN")
    st.subheader("Validación")
    if status == "PASS":
        st.success("PASS: no se detectaron anomalías.")
    elif status == "WARNING":
        st.warning("WARNING: hay hallazgos para revisar.")
    else:
        st.error(f"{status}: hay anomalías críticas o el estado no es reconocido.")
    findings = validation.get("findings", [])
    if findings:
        st.dataframe(pd.DataFrame(findings), width="stretch")

    st.subheader("Comparación contra referencia")
    st.json(to_jsonable(context.get("reference_comparison", {})), expanded=False)

with tabs[6]:
    st.subheader("Narrador AI")
    tone_label_to_value = {label: value for value, label in SUPPORTED_TONES.items()}
    selected_tone_label = st.selectbox("Tono", list(tone_label_to_value.keys()))
    selected_tone = tone_label_to_value[selected_tone_label]
    api_key_available = has_openai_api_key()
    use_api = st.checkbox("usar OpenAI API", value=api_key_available)

    if not api_key_available:
        st.warning("OPENAI_API_KEY no está configurada. Se generará narrativa local de respaldo.")

    result_key = f"narrative_result_{match_id}_{selected_tone}"
    quality_key = f"narrative_quality_{match_id}_{selected_tone}"
    comparison_key = f"tone_comparison_{match_id}"
    review_key = f"review_report_{match_id}"
    action_cols = st.columns(2)
    if action_cols[0].button("Generar narración"):
        with st.spinner("Generando narración..."):
            st.session_state[result_key] = generate_match_narrative(
                match_id,
                selected_tone,
                use_api=use_api,
            )

    current_result = st.session_state.get(result_key)
    if action_cols[1].button("Guardar narración", disabled=current_result is None):
        if current_result:
            md_path, json_path = save_narrative(current_result)
            st.success(f"Narración guardada: {md_path} | {json_path}")

    review_cols = st.columns(3)
    if review_cols[0].button("Evaluar calidad"):
        with st.spinner("Evaluando calidad narrativa..."):
            if current_result is None:
                current_result = generate_match_narrative(match_id, selected_tone, use_api=use_api)
                st.session_state[result_key] = current_result
            st.session_state[quality_key] = evaluate_narrative_quality(
                str(current_result.get("narrative_markdown") or ""),
                context,
            )

    if review_cols[1].button("Comparar tonos"):
        with st.spinner("Comparando tonos..."):
            st.session_state[comparison_key] = compare_tones(match_id, tones=None, use_api=use_api)

    if review_cols[2].button("Guardar revisión"):
        with st.spinner("Construyendo revisión..."):
            report = build_review_report(match_id, use_api=use_api)
            md_path, json_path = save_review_report(report)
            st.session_state[review_key] = report
            st.success(f"Revisión guardada: {md_path} | {json_path}")

    if current_result:
        status_cols = st.columns(3)
        status_cols[0].metric("Status", current_result.get("status"))
        status_cols[1].metric("Modelo", current_result.get("model"))
        status_cols[2].metric("Tono", SUPPORTED_TONES.get(str(current_result.get("tone")), "N/D"))

        warnings = current_result.get("warnings", [])
        if warnings:
            st.warning("Fact guard generó advertencias.")
            for warning in warnings:
                st.write(f"- {warning}")
        else:
            st.success("Fact guard sin advertencias.")

        st.markdown(str(current_result.get("narrative_markdown") or ""))
    else:
        st.info("Genera una narración para el partido seleccionado.")

    quality = st.session_state.get(quality_key)
    if quality:
        st.subheader("Evaluación de calidad")
        quality_cols = st.columns(6)
        quality_cols[0].metric("Overall", quality.get("overall_score"))
        quality_cols[1].metric("Factualidad", quality.get("factuality_score"))
        quality_cols[2].metric("Cobertura", quality.get("coverage_score"))
        quality_cols[3].metric("Claridad", quality.get("clarity_score"))
        quality_cols[4].metric("Emoción", quality.get("excitement_score"))
        quality_cols[5].metric("Táctica", quality.get("tactical_depth_score"))

        element_cols = st.columns(2)
        with element_cols[0]:
            st.write("Detectado")
            st.write(quality.get("detected_elements", []))
        with element_cols[1]:
            st.write("Faltante")
            st.write(quality.get("missing_elements", []))

        quality_warnings = quality.get("warnings", [])
        if quality_warnings:
            st.warning("Advertencias de calidad")
            for warning in quality_warnings:
                st.write(f"- {warning}")

    comparison = st.session_state.get(comparison_key)
    if comparison:
        st.subheader("Comparación de tonos")
        comparison_rows = []
        for row in comparison.get("tones", []):
            comparison_rows.append(
                {
                    "tono": row.get("tone_label") or row.get("tone"),
                    "status": row.get("status"),
                    "overall": row.get("overall_score"),
                    "factualidad": row.get("factuality_score"),
                    "cobertura": row.get("coverage_score"),
                    "claridad": row.get("clarity_score"),
                    "emoción": row.get("excitement_score"),
                    "táctica": row.get("tactical_depth_score"),
                    "warnings": len(row.get("warnings", [])),
                }
            )
        st.dataframe(pd.DataFrame(comparison_rows), width="stretch")
        st.success(f"Mejor tono sugerido: {comparison.get('best_tone_label') or comparison.get('best_tone')}")

    review_report = st.session_state.get(review_key)
    if review_report:
        st.subheader("Revisión guardada")
        st.write("Recomendaciones")
        for recommendation in review_report.get("recommendations", []):
            st.write(f"- {recommendation}")

with tabs[7]:
    st.subheader("Momentos clave")
    st.write("Timeline simple con goles, ocasiones claras, tarjetas, penaltis, asistencias y cambios.")
    key_moments = detail["key_moments"]
    if not key_moments:
        st.info("No se detectaron momentos clave.")
    else:
        for moment in key_moments:
            label = (
                f"{moment.get('minute')}:{int(moment.get('second') or 0):02d} "
                f"| {moment.get('type')} | importancia {moment.get('importance_score')}"
            )
            with st.expander(label, expanded=int(moment.get("importance_score") or 0) >= 85):
                st.markdown(f"**{moment.get('title')}**")
                st.write(moment.get("description"))
                st.write(
                    {
                        "equipo": moment.get("team_name"),
                        "jugador": moment.get("player_name"),
                        "eventos": moment.get("evidence_event_ids"),
                    }
                )

with tabs[8]:
    st.subheader("Datos")
    st.write("Tablas de respaldo y export del contexto analítico para futuras fases.")
    data_tabs = st.tabs(
        ["Contexto AI", "Equipo", "Jugadores top", "Tiros", "Pases progresivos", "Presiones", "Avanzado"]
    )
    with data_tabs[0]:
        st.json(to_jsonable(context), expanded=False)
    with data_tabs[1]:
        st.dataframe(pd.DataFrame(team_stats), width="stretch")
    with data_tabs[2]:
        st.dataframe(pd.DataFrame(context.get("top_players", [])), width="stretch")
    with data_tabs[3]:
        st.dataframe(pd.DataFrame(detail["shots"]), width="stretch")
    with data_tabs[4]:
        st.dataframe(pd.DataFrame(detail["progressive_passes"]), width="stretch")
    with data_tabs[5]:
        st.dataframe(pd.DataFrame(detail["pressures"]), width="stretch")
    with data_tabs[6]:
        advanced_tables = {
            "dominance": context.get("dominance", []),
            "dominance_intervals": context.get("dominance_intervals", []),
            "dangerous_attacks": context.get("dangerous_attacks", []),
            "impact_players": context.get("impact_players", []),
            "xg_breakdown": context.get("xg_breakdown", []),
            "validation": context.get("validation", {}),
        }
        st.json(to_jsonable(advanced_tables), expanded=False)

    st.subheader("Exportar JSON")
    if st.button("Exportar contexto analítico"):
        ANALYTICS_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
        output_path = ANALYTICS_EXPORTS_DIR / f"analysis.match-{match_id}.json"
        with output_path.open("w", encoding="utf-8") as file:
            json.dump(to_jsonable(context), file, ensure_ascii=False, indent=2)
            file.write("\n")
        st.success(f"JSON exportado: {output_path.as_posix()}")
