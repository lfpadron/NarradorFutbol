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
from src.benchmark.benchmark_cases import BENCHMARK_CASES
from src.benchmark.benchmark_report import save_benchmark_result
from src.benchmark.benchmark_runner import run_all_benchmarks
from src.benchmark.generic_report import save_generic_validation_result
from src.benchmark.generic_validation import validate_any_match
from src.comparison.comparison_narrative import generate_match_comparison_narrative
from src.comparison.comparison_report import save_match_comparison
from src.comparison.match_comparison import compare_matches
from src.comparison.player_comparison import build_player_radar_metrics, compare_players, list_players_for_match
from src.comparison.player_comparison_narrative import generate_player_comparison_narrative
from src.comparison.player_comparison_report import save_player_comparison
from src.comparison.player_visuals import (
    plot_player_metric_bars,
    plot_player_profile_groups,
    plot_player_radar,
    plot_player_strengths_weaknesses,
)
from src.config import ANALYTICS_EXPORTS_DIR
from src.ingestion.utils import to_jsonable
from src.narrative.config import SUPPORTED_TONES, has_openai_api_key
from src.narrative.narrative_store import save_narrative
from src.narrative.narrator import generate_match_narrative
from src.narrative.quality_checker import evaluate_narrative_quality
from src.narrative.review_report import build_review_report, save_review_report
from src.narrative.tone_comparison import compare_tones
from src.narrative_v2.narrator_v2 import (
    compare_specialized_styles,
    generate_specialized_narrative,
    save_specialized_narrative,
)
from src.narrative_v2.style_profiles import STYLE_PROFILES
from src.reports.html_report import render_html_report
from src.reports.markdown_report import render_markdown_report
from src.reports.report_builder import build_match_report
from src.reports.report_history import build_history_record, list_report_history, record_report_generation
from src.reports.report_store import save_report
from src.scouting.scouting_history import list_scouting_history
from src.scouting.scouting_narrator import generate_scouting_narrative
from src.scouting.scouting_report import save_scouting_report
from src.scouting.scouting_v2 import generate_scouting_v2
from src.scouting.scouting_v2_report import save_scouting_v2_report
from src.security.streamlit_auth import require_login
from src.ui.charts import momentum_line, shot_count_bar, xg_bar
from src.ui.formatters import format_float, format_pct, format_score
from src.ui.pitch_charts import (
    plot_cumulative_xg,
    plot_pass_network,
    plot_pressure_map,
    plot_progressive_passes,
    plot_shot_map,
)

st.set_page_config(page_title="Análisis", layout="wide")
require_login()
st.title("Análisis")


@st.cache_data(show_spinner=False)
def load_match_options() -> pd.DataFrame:
    return query_df("""
        SELECT match_id, match_date, home_team_name, away_team_name, home_score, away_score
        FROM vw_match_summary
        WHERE total_events > 0
        ORDER BY match_date, match_id
        """)


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


@st.cache_data(show_spinner=False)
def load_players_for_match(match_id: int) -> list[dict[str, object]]:
    return list_players_for_match(match_id)


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
    f"{row.match_id} | {row.match_date} | {row.home_team_name} {row.home_score}-{row.away_score} {row.away_team_name}": int(
        row.match_id
    )
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
        "Narrador AI v2",
        "Benchmark",
        "Comparador de partidos",
        "Comparador de jugadores",
        "Scouting AI v2",
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
    st.write("Fórmula MVP: tiros * 3 + xG * 10 + entradas al tercio final * 1 " "+ eventos ofensivos * 0.5.")
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
    final_report_key = f"final_report_{match_id}_{selected_tone}"
    final_report_paths_key = f"final_report_paths_{match_id}_{selected_tone}"
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

    st.subheader("Reporte final")
    st.caption("Markdown, HTML y JSON se generan siempre al guardar el reporte.")
    base_format_cols = st.columns(3)
    base_format_cols[0].checkbox(
        "Generar Markdown",
        value=True,
        disabled=True,
        key=f"final_report_md_{match_id}_{selected_tone}",
    )
    base_format_cols[1].checkbox(
        "Generar HTML",
        value=True,
        disabled=True,
        key=f"final_report_html_{match_id}_{selected_tone}",
    )
    base_format_cols[2].checkbox(
        "Generar JSON",
        value=True,
        disabled=True,
        key=f"final_report_json_{match_id}_{selected_tone}",
    )

    st.caption("Formatos adicionales")
    export_option_cols = st.columns(2)
    include_pdf = export_option_cols[0].checkbox(
        "Generar PDF",
        value=False,
        key=f"final_report_pdf_{match_id}_{selected_tone}",
    )
    include_docx = export_option_cols[1].checkbox(
        "Generar DOCX",
        value=True,
        key=f"final_report_docx_{match_id}_{selected_tone}",
    )

    report_cols = st.columns(2)
    if report_cols[0].button("Generar reporte"):
        with st.spinner("Generando reporte final..."):
            final_report = build_match_report(match_id, tone=selected_tone, use_api=use_api)
            st.session_state[final_report_key] = {
                "report": final_report,
                "markdown": render_markdown_report(final_report),
                "html": render_html_report(final_report),
            }
            st.session_state.pop(final_report_paths_key, None)

    report_bundle = st.session_state.get(final_report_key)
    if report_cols[1].button("Guardar reporte", disabled=report_bundle is None):
        if report_bundle:
            paths = save_report(
                report_bundle["report"],
                report_bundle["markdown"],
                report_bundle["html"],
                include_pdf=include_pdf,
                include_docx=include_docx,
            )
            history_record = build_history_record(report_bundle["report"], paths, use_api=use_api)
            record_report_generation(history_record)
            paths["generated_by"] = history_record.get("generated_by")
            paths["generated_at"] = paths.get("exported_at") or history_record.get("generated_at")
            paths["history_status"] = history_record.get("status")
            st.session_state[final_report_paths_key] = paths
            st.success("Reporte guardado.")

    report_paths = st.session_state.get(final_report_paths_key)
    if report_paths:
        st.write("Formatos base generados")
        format_labels = {
            "markdown": "Markdown",
            "html": "HTML",
            "json": "JSON",
            "pdf": "PDF",
            "docx": "DOCX",
        }
        for label in ("markdown", "html", "json"):
            path = report_paths.get(label)
            if path:
                st.write(f"- {format_labels[label]}: {path}")

        st.write("Formatos adicionales")
        optional_paths = False
        for label in ("pdf", "docx"):
            path = report_paths.get(label)
            if path:
                optional_paths = True
                st.write(f"- {format_labels[label]}: {path}")
        if not optional_paths:
            st.caption("No se generó ningún formato adicional en esta corrida.")

        audit_cols = st.columns(3)
        audit_cols[0].metric("Generado por", report_paths.get("generated_by", "local_user"))
        audit_cols[1].metric("Estado", report_paths.get("history_status", "generated"))
        audit_cols[2].metric("Fecha", report_paths.get("generated_at", "N/D"))

        status_cols = st.columns(2)
        status_cols[0].metric("PDF", report_paths.get("pdf_status", "not_requested"))
        status_cols[1].metric("DOCX", report_paths.get("docx_status", "not_requested"))
        if report_paths.get("pdf_warning_message"):
            st.info(f"PDF: {report_paths.get('pdf_warning_message')}")
        if report_paths.get("pdf_error_message"):
            st.warning(f"PDF: {report_paths.get('pdf_error_message')}")
        if report_paths.get("docx_error_message"):
            st.warning(f"DOCX: {report_paths.get('docx_error_message')}")

    if report_bundle:
        st.markdown("### Vista previa Markdown")
        st.markdown(report_bundle["markdown"])

    st.subheader("Historial de reportes")
    history_rows = list_report_history(limit=25)
    if history_rows:
        st.dataframe(pd.DataFrame(history_rows), width="stretch")
    else:
        st.info("Todavía no hay reportes registrados en historial.")

with tabs[7]:
    st.subheader("Narrador AI v2")
    st.write("Narrativas especializadas por audiencia.")

    style_labels = {
        "Táctico": "tactico",
        "Televisión": "television",
        "Periodístico": "periodistico",
        "Scouting": "scouting",
        "Ejecutivo": "ejecutivo",
    }
    selected_v2_label = st.selectbox("Estilo v2", list(style_labels.keys()))
    selected_style_id = style_labels[selected_v2_label]
    selected_profile = STYLE_PROFILES[selected_style_id]
    api_key_available_v2 = has_openai_api_key()
    use_api_v2 = st.checkbox(
        "Usar OpenAI API",
        value=api_key_available_v2,
        key=f"narrative_v2_use_api_{match_id}_{selected_style_id}",
    )

    if not api_key_available_v2:
        st.warning("OPENAI_API_KEY no está configurada. Narrador AI v2 usará fallback local.")

    st.caption(f"Audiencia: {selected_profile['audience']} | Objetivo: {selected_profile['objective']}")

    v2_result_key = f"narrative_v2_result_{match_id}_{selected_style_id}"
    v2_comparison_key = f"narrative_v2_comparison_{match_id}"
    v2_cols = st.columns(3)
    if v2_cols[0].button("Generar narrativa v2"):
        with st.spinner("Generando narrativa especializada..."):
            st.session_state[v2_result_key] = generate_specialized_narrative(
                match_id,
                selected_style_id,
                use_api=use_api_v2,
            )

    if v2_cols[1].button("Comparar estilos"):
        with st.spinner("Comparando estilos v2..."):
            st.session_state[v2_comparison_key] = compare_specialized_styles(
                match_id,
                use_api=use_api_v2,
            )

    v2_result = st.session_state.get(v2_result_key)
    if v2_cols[2].button("Guardar narrativa v2", disabled=v2_result is None):
        if v2_result:
            md_path, json_path = save_specialized_narrative(v2_result)
            st.success(f"Narrativa v2 guardada: {md_path} | {json_path}")

    if v2_result:
        st.markdown("### Resultado v2")
        v2_quality = v2_result.get("style_quality", {})
        metric_cols = st.columns(5)
        metric_cols[0].metric("Status", v2_result.get("status"))
        metric_cols[1].metric("Estilo", v2_result.get("style_name"))
        metric_cols[2].metric("Score", v2_quality.get("style_score"))
        metric_cols[3].metric("Estructura", v2_quality.get("structure_score"))
        metric_cols[4].metric("Factualidad", v2_quality.get("factuality_score"))

        fact_warnings = v2_result.get("fact_warnings", [])
        if fact_warnings:
            st.warning("Fact warnings")
            for warning in fact_warnings:
                st.write(f"- {warning}")
        else:
            st.success("Sin fact warnings.")

        style_warnings = v2_quality.get("warnings", [])
        if style_warnings:
            st.warning("Style quality warnings")
            for warning in style_warnings:
                st.write(f"- {warning}")

        st.json(v2_quality, expanded=False)
        st.markdown(v2_result.get("narrative_markdown") or "")

    v2_comparison = st.session_state.get(v2_comparison_key)
    if v2_comparison:
        st.markdown("### Comparación de estilos v2")
        comparison_rows = [
            {
                "estilo": row.get("style_name"),
                "status": row.get("status"),
                "score": row.get("style_score"),
                "fact_warnings": row.get("fact_warnings_count"),
            }
            for row in v2_comparison.get("styles", [])
        ]
        st.dataframe(pd.DataFrame(comparison_rows), width="stretch")
        st.success(f"Mejor estilo sugerido: {v2_comparison.get('best_style')}")

with tabs[8]:
    st.subheader("Benchmark")
    st.write(
        "Validación futbolística y regresión narrativa, con rutas separadas para casos curados y partidos genéricos."
    )

    st.markdown("### Benchmark curado")
    st.caption("Usa expectativas humanas conocidas; sirve para regresión narrativa y demos históricas controladas.")

    st.dataframe(
        pd.DataFrame(
            [
                {
                    "case_id": case.get("case_id"),
                    "match_id": case.get("match_id"),
                    "label": case.get("label"),
                    "winner": case.get("expected", {}).get("winner"),
                    "dominant_team": case.get("expected", {}).get("dominant_team"),
                }
                for case in BENCHMARK_CASES
            ]
        ),
        width="stretch",
    )

    benchmark_key = "benchmark_result_all_no_api"
    benchmark_cols = st.columns(2)
    if benchmark_cols[0].button("Ejecutar benchmark sin API"):
        with st.spinner("Ejecutando benchmark y regresión narrativa..."):
            try:
                st.session_state[benchmark_key] = run_all_benchmarks(use_api=False)
            except Exception as exc:
                st.error(f"No se pudo ejecutar benchmark: {exc}")

    benchmark_result = st.session_state.get(benchmark_key)
    if benchmark_cols[1].button("Guardar resultado", disabled=benchmark_result is None):
        if benchmark_result:
            try:
                paths = save_benchmark_result(benchmark_result)
                st.success(f"Benchmark guardado: {paths['markdown']} | {paths['json']}")
            except Exception as exc:
                st.error(f"No se pudo guardar benchmark: {exc}")

    if benchmark_result:
        summary_result = benchmark_result.get("summary", {})
        status_cols = st.columns(4)
        status_cols[0].metric("Status", benchmark_result.get("status"))
        status_cols[1].metric("PASS", summary_result.get("pass", 0))
        status_cols[2].metric("WARNING", summary_result.get("warning", 0))
        status_cols[3].metric("FAIL", summary_result.get("fail", 0))

        case_rows = []
        for case_result in benchmark_result.get("cases", []):
            case_rows.append(
                {
                    "case_id": case_result.get("case_id"),
                    "status": case_result.get("status"),
                    "basic_quality": case_result.get("basic_narrative", {}).get("quality_overall_score"),
                    "basic_fact_warnings": case_result.get("basic_narrative", {}).get("fact_warnings_count"),
                    "v2_best_style": case_result.get("v2_narrative", {}).get("best_style"),
                    "v2_fact_warnings": case_result.get("v2_narrative", {}).get("fact_warnings_count"),
                }
            )
        st.dataframe(pd.DataFrame(case_rows), width="stretch")

        for case_result in benchmark_result.get("cases", []):
            with st.expander(f"{case_result.get('case_id')} | {case_result.get('status')}"):
                checks_frame = pd.DataFrame(
                    [
                        {
                            "check": check.get("check_name"),
                            "status": check.get("status"),
                            "message": check.get("message"),
                        }
                        for check in case_result.get("checks", [])
                    ]
                )
                st.dataframe(checks_frame, width="stretch")
                warnings = [check for check in case_result.get("checks", []) if check.get("status") != "PASS"]
                if warnings:
                    st.warning("Advertencias o fallos detectados")
                    for warning in warnings:
                        st.write(f"- {warning.get('check_name')}: {warning.get('message')}")
                else:
                    st.success("Todos los checks pasaron.")

    st.divider()
    st.markdown("### Validación genérica")
    st.caption(
        "Funciona con cualquier partido transformado. Revisa consistencia interna, datos analíticos, reportes y narrativas sin exigir expectativas históricas."
    )

    generic_match_id = st.number_input(
        "Match ID para validación genérica",
        min_value=1,
        value=int(match_id),
        step=1,
    )
    generic_key = f"generic_validation_{int(generic_match_id)}"
    generic_cols = st.columns(2)
    if generic_cols[0].button("Validar partido"):
        with st.spinner("Ejecutando validación genérica..."):
            try:
                st.session_state[generic_key] = validate_any_match(int(generic_match_id), use_api=False)
            except Exception as exc:
                st.error(f"No se pudo ejecutar la validación genérica: {exc}")

    generic_result = st.session_state.get(generic_key)
    if generic_cols[1].button("Guardar validación", disabled=generic_result is None):
        if generic_result:
            try:
                paths = save_generic_validation_result(generic_result)
                st.success(f"Validación guardada: {paths['markdown']} | {paths['json']}")
            except Exception as exc:
                st.error(f"No se pudo guardar la validación genérica: {exc}")

    if generic_result:
        generic_summary = generic_result.get("summary", {})
        generic_checks = generic_result.get("checks", [])
        generic_status_cols = st.columns(5)
        generic_status_cols[0].metric("Status", generic_result.get("status"))
        generic_status_cols[1].metric("PASS", sum(1 for row in generic_checks if row.get("status") == "PASS"))
        generic_status_cols[2].metric("WARNING", sum(1 for row in generic_checks if row.get("status") == "WARNING"))
        generic_status_cols[3].metric("FAIL", sum(1 for row in generic_checks if row.get("status") == "FAIL"))
        generic_status_cols[4].metric("Eventos", generic_summary.get("events", 0))

        st.write(
            f"{generic_summary.get('home_team')} {generic_summary.get('home_score')}-"
            f"{generic_summary.get('away_score')} {generic_summary.get('away_team')}"
        )
        generic_rows = [
            {
                "check": check.get("check_name"),
                "status": check.get("status"),
                "message": check.get("message"),
            }
            for check in generic_checks
        ]
        st.dataframe(pd.DataFrame(generic_rows), width="stretch")

        generic_warnings = generic_result.get("warnings", [])
        if generic_warnings:
            st.warning("Advertencias o fallos detectados")
            for warning in generic_warnings:
                st.write(f"- {warning}")
        else:
            st.success("La validación genérica no generó advertencias.")

        basic_generic = generic_result.get("narrative_basic", {})
        v2_generic = generic_result.get("narrative_v2", {})
        narrative_cols = st.columns(4)
        narrative_cols[0].metric("Narrativa básica", basic_generic.get("status", "N/D"))
        narrative_cols[1].metric(
            "Calidad básica",
            basic_generic.get("quality", {}).get("overall_score", "N/D"),
        )
        narrative_cols[2].metric("Estilos v2", v2_generic.get("styles_checked", 0))
        narrative_cols[3].metric("Warnings v2", v2_generic.get("fact_warnings_total", 0))

with tabs[9]:
    st.subheader("Comparador de partidos")
    st.write("Compara dos partidos transformados para revisar diferencias de volumen, eficacia, dominio e impacto.")

    match_labels = list(options.keys())
    default_a_index = next((idx for idx, label in enumerate(match_labels) if options[label] == 7534), 0)
    default_b_index = next(
        (idx for idx, label in enumerate(match_labels) if options[label] != options[match_labels[default_a_index]]),
        0,
    )
    selector_cols = st.columns(2)
    comparison_label_a = selector_cols[0].selectbox(
        "Partido A",
        match_labels,
        index=default_a_index,
        key="comparison_match_a",
    )
    comparison_label_b = selector_cols[1].selectbox(
        "Partido B",
        match_labels,
        index=default_b_index,
        key="comparison_match_b",
    )
    comparison_match_a = options[comparison_label_a]
    comparison_match_b = options[comparison_label_b]
    comparison_key = f"comparison_{comparison_match_a}_{comparison_match_b}"
    comparison_narrative_key = f"comparison_narrative_{comparison_match_a}_{comparison_match_b}"

    comparison_actions = st.columns(3)
    if comparison_actions[0].button("Comparar partidos"):
        with st.spinner("Comparando partidos..."):
            try:
                st.session_state[comparison_key] = compare_matches(comparison_match_a, comparison_match_b)
                st.session_state.pop(comparison_narrative_key, None)
            except Exception as exc:
                st.error(f"No se pudo comparar partidos: {exc}")

    current_comparison = st.session_state.get(comparison_key)
    if comparison_actions[1].button(
        "Generar narrativa comparativa",
        disabled=current_comparison is None,
        key="match_comparison_generate_narrative",
    ):
        with st.spinner("Generando narrativa comparativa..."):
            try:
                st.session_state[comparison_narrative_key] = generate_match_comparison_narrative(
                    comparison_match_a,
                    comparison_match_b,
                    use_api=False,
                )
            except Exception as exc:
                st.error(f"No se pudo generar narrativa comparativa: {exc}")

    current_narrative = st.session_state.get(comparison_narrative_key)
    if comparison_actions[2].button(
        "Guardar comparación",
        disabled=current_comparison is None,
        key="match_comparison_save",
    ):
        if current_comparison:
            try:
                paths = save_match_comparison(current_comparison, current_narrative)
                st.success(f"Comparación guardada: {paths['markdown']} | {paths['json']}")
            except Exception as exc:
                st.error(f"No se pudo guardar la comparación: {exc}")

    if current_comparison:
        match_a = current_comparison.get("match_a", {})
        match_b = current_comparison.get("match_b", {})
        summary_comparison = current_comparison.get("summary_comparison", {})
        summary_cols = st.columns(2)
        with summary_cols[0]:
            st.markdown("### Partido A")
            a_metric_cols = st.columns(4)
            st.write(match_a.get("scoreline"))
            a_metric_cols[0].metric("Tiros", match_a.get("total_shots"))
            a_metric_cols[1].metric("xG", format_float(match_a.get("total_xg")))
            a_metric_cols[2].metric("Pases", match_a.get("total_passes"))
            a_metric_cols[3].metric("Ataques peligrosos", match_a.get("dangerous_attacks"))
        with summary_cols[1]:
            st.markdown("### Partido B")
            b_metric_cols = st.columns(4)
            st.write(match_b.get("scoreline"))
            b_metric_cols[0].metric("Tiros", match_b.get("total_shots"))
            b_metric_cols[1].metric("xG", format_float(match_b.get("total_xg")))
            b_metric_cols[2].metric("Pases", match_b.get("total_passes"))
            b_metric_cols[3].metric("Ataques peligrosos", match_b.get("dangerous_attacks"))

        difference_rows = []
        for label, key in (
            ("Goles", "goal_difference"),
            ("Tiros", "shot_difference"),
            ("xG", "xg_difference"),
            ("Pases", "pass_difference"),
            ("Ataques peligrosos", "dangerous_attack_difference"),
        ):
            values = summary_comparison.get(key, {})
            difference_rows.append(
                {
                    "métrica": label,
                    "partido_a": values.get("match_a"),
                    "partido_b": values.get("match_b"),
                    "diferencia_b_menos_a": values.get("difference_b_minus_a"),
                    "mayor": values.get("higher_match"),
                }
            )
        st.markdown("### Diferencias")
        st.dataframe(pd.DataFrame(difference_rows), width="stretch")

        pass_success = current_comparison.get("pass_comparison", {}).get("successful_passes", {})
        possessions_total = current_comparison.get("possession_comparison", {}).get("total_possessions", {})
        key_moments_total = current_comparison.get("key_moments_comparison", {}).get("total_key_moments", {})
        side_by_side_rows = [
            {
                "métrica": "Intensidad",
                "partido_a": summary_comparison.get("intensity_a", {}).get("score"),
                "partido_b": summary_comparison.get("intensity_b", {}).get("score"),
                "diferencia_b_menos_a": None,
                "mayor": summary_comparison.get("more_intense_match"),
            },
            {
                "métrica": "Pases completados",
                "partido_a": pass_success.get("match_a"),
                "partido_b": pass_success.get("match_b"),
                "diferencia_b_menos_a": pass_success.get("difference_b_minus_a"),
                "mayor": pass_success.get("higher_match"),
            },
            {
                "métrica": "Posesiones",
                "partido_a": possessions_total.get("match_a"),
                "partido_b": possessions_total.get("match_b"),
                "diferencia_b_menos_a": possessions_total.get("difference_b_minus_a"),
                "mayor": possessions_total.get("higher_match"),
            },
            {
                "métrica": "Momentos clave",
                "partido_a": key_moments_total.get("match_a"),
                "partido_b": key_moments_total.get("match_b"),
                "diferencia_b_menos_a": key_moments_total.get("difference_b_minus_a"),
                "mayor": key_moments_total.get("higher_match"),
            },
        ]
        st.markdown("### xG, tiros, pases y posesión")
        st.dataframe(pd.DataFrame(side_by_side_rows), width="stretch")

        dominance_comparison = current_comparison.get("dominance_comparison", {})
        dominance_rows = [
            {"partido": "A", **dominance_comparison.get("leader_a", {})},
            {"partido": "B", **dominance_comparison.get("leader_b", {})},
        ]
        st.markdown("### Dominio comparado")
        st.dataframe(pd.DataFrame(dominance_rows), width="stretch")

        impact_comparison = current_comparison.get("impact_players_comparison", {})
        impact_cols = st.columns(2)
        with impact_cols[0]:
            st.markdown("### Impacto Partido A")
            st.dataframe(pd.DataFrame(impact_comparison.get("rows_a", [])), width="stretch")
        with impact_cols[1]:
            st.markdown("### Impacto Partido B")
            st.dataframe(pd.DataFrame(impact_comparison.get("rows_b", [])), width="stretch")

        key_moments_comparison = current_comparison.get("key_moments_comparison", {})
        moments_cols = st.columns(2)
        with moments_cols[0]:
            st.markdown("### Momentos Partido A")
            st.dataframe(pd.DataFrame(key_moments_comparison.get("rows_a", [])), width="stretch")
        with moments_cols[1]:
            st.markdown("### Momentos Partido B")
            st.dataframe(pd.DataFrame(key_moments_comparison.get("rows_b", [])), width="stretch")

        comparison_warnings = current_comparison.get("warnings", [])
        if comparison_warnings:
            st.warning("Advertencias de comparación")
            for warning in comparison_warnings:
                st.write(f"- {warning}")

    if current_narrative:
        narrative_warnings = current_narrative.get("warnings", [])
        if narrative_warnings:
            st.info("Narrativa generada con avisos.")
            for warning in narrative_warnings:
                st.write(f"- {warning}")
        st.markdown("### Narrativa comparativa")
        st.markdown(current_narrative.get("narrative_markdown") or "")

with tabs[10]:
    st.subheader("Comparador de jugadores")
    st.write(
        "Compara jugadores dentro del mismo partido o entre partidos distintos con lectura estadística y contextual."
    )

    player_match_labels = list(options.keys())
    player_default_a_index = next((idx for idx, label in enumerate(player_match_labels) if options[label] == 7534), 0)
    player_selector_cols = st.columns(2)
    player_label_a = player_selector_cols[0].selectbox(
        "Partido A para jugador",
        player_match_labels,
        index=player_default_a_index,
        key="player_comparison_match_a",
    )
    player_label_b = player_selector_cols[1].selectbox(
        "Partido B para jugador",
        player_match_labels,
        index=player_default_a_index,
        key="player_comparison_match_b",
    )
    player_match_a = options[player_label_a]
    player_match_b = options[player_label_b]

    players_a = load_players_for_match(player_match_a)
    players_b = load_players_for_match(player_match_b)
    player_options_a = {
        f"{row.get('player_name')} | {row.get('team_name')} | {row.get('events')} eventos": int(row["player_id"])
        for row in players_a
        if row.get("player_id") is not None
    }
    player_options_b = {
        f"{row.get('player_name')} | {row.get('team_name')} | {row.get('events')} eventos": int(row["player_id"])
        for row in players_b
        if row.get("player_id") is not None
    }

    if not player_options_a or not player_options_b:
        st.warning("No hay jugadores disponibles para uno de los partidos seleccionados.")
    else:
        default_player_a = next(
            (label for label, player_id in player_options_a.items() if player_id == 5503),
            next(iter(player_options_a)),
        )
        default_player_b = next(
            (
                label
                for label, player_id in player_options_b.items()
                if player_options_b[label] != player_options_a.get(default_player_a)
            ),
            next(iter(player_options_b)),
        )
        player_cols = st.columns(2)
        selected_player_label_a = player_cols[0].selectbox(
            "Jugador A",
            list(player_options_a.keys()),
            index=list(player_options_a.keys()).index(default_player_a),
            key="player_comparison_player_a",
        )
        selected_player_label_b = player_cols[1].selectbox(
            "Jugador B",
            list(player_options_b.keys()),
            index=list(player_options_b.keys()).index(default_player_b),
            key="player_comparison_player_b",
        )
        player_id_a = player_options_a[selected_player_label_a]
        player_id_b = player_options_b[selected_player_label_b]
        player_comparison_key = f"player_comparison_{player_match_a}_{player_id_a}_{player_match_b}_{player_id_b}"
        player_narrative_key = (
            f"player_comparison_narrative_{player_match_a}_{player_id_a}_{player_match_b}_{player_id_b}"
        )

        player_action_cols = st.columns(3)
        if player_action_cols[0].button("Comparar jugadores"):
            with st.spinner("Comparando jugadores..."):
                try:
                    st.session_state[player_comparison_key] = compare_players(
                        player_match_a,
                        player_id_a,
                        player_match_b,
                        player_id_b,
                    )
                    st.session_state.pop(player_narrative_key, None)
                except Exception as exc:
                    st.error(f"No se pudo comparar jugadores: {exc}")

        current_player_comparison = st.session_state.get(player_comparison_key)
        if player_action_cols[1].button(
            "Generar narrativa comparativa",
            disabled=current_player_comparison is None,
            key="player_comparison_generate_narrative",
        ):
            with st.spinner("Generando narrativa comparativa de jugadores..."):
                try:
                    st.session_state[player_narrative_key] = generate_player_comparison_narrative(
                        player_match_a,
                        player_id_a,
                        player_match_b,
                        player_id_b,
                        use_api=False,
                    )
                except Exception as exc:
                    st.error(f"No se pudo generar narrativa comparativa: {exc}")

        current_player_narrative = st.session_state.get(player_narrative_key)
        if player_action_cols[2].button(
            "Guardar comparación",
            disabled=current_player_comparison is None,
            key="player_comparison_save",
        ):
            if current_player_comparison:
                try:
                    paths = save_player_comparison(current_player_comparison, current_player_narrative)
                    st.success(f"Comparación guardada: {paths['markdown']} | {paths['json']}")
                except Exception as exc:
                    st.error(f"No se pudo guardar la comparación: {exc}")

        if current_player_comparison:
            player_a = current_player_comparison.get("player_a", {})
            player_b = current_player_comparison.get("player_b", {})
            player_summary = current_player_comparison.get("summary_comparison", {})
            summary_cols = st.columns(2)
            with summary_cols[0]:
                st.markdown("### Jugador A")
                st.write(f"{player_a.get('player_name')} ({player_a.get('team_name')})")
                a_cols = st.columns(4)
                a_cols[0].metric("Goles", player_a.get("goals"))
                a_cols[1].metric("xG", format_float(player_a.get("xg")))
                a_cols[2].metric("Pases clave", player_a.get("key_passes"))
                a_cols[3].metric("Impacto", format_float(player_a.get("impact_score")))
            with summary_cols[1]:
                st.markdown("### Jugador B")
                st.write(f"{player_b.get('player_name')} ({player_b.get('team_name')})")
                b_cols = st.columns(4)
                b_cols[0].metric("Goles", player_b.get("goals"))
                b_cols[1].metric("xG", format_float(player_b.get("xg")))
                b_cols[2].metric("Pases clave", player_b.get("key_passes"))
                b_cols[3].metric("Impacto", format_float(player_b.get("impact_score")))

            radar_metrics = build_player_radar_metrics(current_player_comparison)
            strengths_weaknesses = plot_player_strengths_weaknesses(radar_metrics)
            st.markdown("### Radar comparativo")
            st.plotly_chart(plot_player_radar(radar_metrics), width="stretch")

            visual_cols = st.columns(2)
            with visual_cols[0]:
                st.markdown("### Métricas comparativas")
                st.plotly_chart(plot_player_metric_bars(current_player_comparison), width="stretch")
            with visual_cols[1]:
                st.markdown("### Perfil por grupos")
                st.plotly_chart(plot_player_profile_groups(current_player_comparison), width="stretch")

            st.markdown("### Fortalezas y debilidades")
            sw_cols = st.columns(2)
            with sw_cols[0]:
                st.write(f"**{radar_metrics.get('player_a', {}).get('name') or 'Jugador A'}**")
                st.write("Fortalezas")
                st.write(strengths_weaknesses.get("player_a_strengths", []) or ["Sin fortalezas >= 70"])
                st.write("Debilidades")
                st.write(strengths_weaknesses.get("player_a_weaknesses", []) or ["Sin debilidades <= 30"])
            with sw_cols[1]:
                st.write(f"**{radar_metrics.get('player_b', {}).get('name') or 'Jugador B'}**")
                st.write("Fortalezas")
                st.write(strengths_weaknesses.get("player_b_strengths", []) or ["Sin fortalezas >= 70"])
                st.write("Debilidades")
                st.write(strengths_weaknesses.get("player_b_weaknesses", []) or ["Sin debilidades <= 30"])
            for warning in strengths_weaknesses.get("warnings", []):
                st.info(warning)

            diff_rows = [
                {"métrica": "Goles", "diferencia_b_menos_a": player_summary.get("diff_goals")},
                {"métrica": "xG", "diferencia_b_menos_a": player_summary.get("diff_xg")},
                {"métrica": "Tiros", "diferencia_b_menos_a": player_summary.get("diff_shots")},
                {"métrica": "Asistencias", "diferencia_b_menos_a": player_summary.get("diff_assists")},
                {"métrica": "Pases clave", "diferencia_b_menos_a": player_summary.get("diff_key_passes")},
                {"métrica": "Presiones", "diferencia_b_menos_a": player_summary.get("diff_pressures")},
                {"métrica": "Impact score", "diferencia_b_menos_a": player_summary.get("diff_impact_score")},
            ]
            st.markdown("### Diferencias")
            st.dataframe(pd.DataFrame(diff_rows), width="stretch")

            comparison_sections = {
                "Comparación ofensiva": current_player_comparison.get("attacking_comparison", {}),
                "Comparación de pases": current_player_comparison.get("passing_comparison", {}),
                "Comparación defensiva": current_player_comparison.get("defensive_comparison", {}),
                "Impacto": current_player_comparison.get("impact_comparison", {}),
            }
            for section_title, section in comparison_sections.items():
                rows = [
                    {
                        "métrica": metric,
                        "jugador_a": values.get("player_a"),
                        "jugador_b": values.get("player_b"),
                        "diferencia_b_menos_a": values.get("difference_b_minus_a"),
                        "mayor": values.get("higher_player"),
                    }
                    for metric, values in section.items()
                    if isinstance(values, dict)
                ]
                st.markdown(f"### {section_title}")
                st.dataframe(pd.DataFrame(rows), width="stretch")

            key_moments_player = current_player_comparison.get("key_moments_comparison", {})
            moment_cols = st.columns(2)
            with moment_cols[0]:
                st.markdown("### Momentos Jugador A")
                st.dataframe(pd.DataFrame(key_moments_player.get("rows_a", [])), width="stretch")
            with moment_cols[1]:
                st.markdown("### Momentos Jugador B")
                st.dataframe(pd.DataFrame(key_moments_player.get("rows_b", [])), width="stretch")

            player_warnings = current_player_comparison.get("warnings", [])
            if player_warnings:
                st.warning("Advertencias de comparación")
                for warning in player_warnings:
                    st.write(f"- {warning}")

        if current_player_narrative:
            narrative_warnings = current_player_narrative.get("warnings", [])
            if narrative_warnings:
                st.info("Narrativa generada con avisos.")
                for warning in narrative_warnings:
                    st.write(f"- {warning}")
            st.markdown("### Narrativa comparativa de jugadores")
            st.markdown(current_player_narrative.get("narrative_markdown") or "")

        st.markdown("### Scouting AI")
        scouting_api_available = has_openai_api_key()
        scouting_use_api = st.checkbox(
            "Usar OpenAI API para Scouting AI",
            value=scouting_api_available,
            key=f"scouting_use_api_{player_match_a}_{player_id_a}_{player_match_b}_{player_id_b}",
        )
        if not scouting_api_available:
            st.caption("OPENAI_API_KEY no está configurada. Scouting AI usará fallback local.")

        scouting_export_cols = st.columns(3)
        scouting_include_html = scouting_export_cols[0].checkbox(
            "Generar HTML",
            value=True,
            key=f"scouting_export_html_{player_match_a}_{player_id_a}_{player_match_b}_{player_id_b}",
        )
        scouting_include_docx = scouting_export_cols[1].checkbox(
            "Generar DOCX",
            value=False,
            key=f"scouting_export_docx_{player_match_a}_{player_id_a}_{player_match_b}_{player_id_b}",
        )
        scouting_include_pdf = scouting_export_cols[2].checkbox(
            "Generar PDF",
            value=False,
            key=f"scouting_export_pdf_{player_match_a}_{player_id_a}_{player_match_b}_{player_id_b}",
        )

        scouting_result_key = f"scouting_result_{player_match_a}_{player_id_a}_{player_match_b}_{player_id_b}"
        scouting_paths_key = f"scouting_paths_{player_match_a}_{player_id_a}_{player_match_b}_{player_id_b}"
        scouting_cols = st.columns(4)
        if scouting_cols[0].button(
            "Scouting individual A",
            key=f"scouting_individual_a_{player_match_a}_{player_id_a}",
        ):
            with st.spinner("Generando scouting individual de Jugador A..."):
                try:
                    st.session_state[scouting_result_key] = generate_scouting_narrative(
                        player_match_a,
                        player_id_a,
                        use_api=scouting_use_api,
                    )
                    st.session_state.pop(scouting_paths_key, None)
                except Exception as exc:
                    st.error(f"No se pudo generar scouting individual A: {exc}")

        if scouting_cols[1].button(
            "Scouting individual B",
            key=f"scouting_individual_b_{player_match_b}_{player_id_b}",
        ):
            with st.spinner("Generando scouting individual de Jugador B..."):
                try:
                    st.session_state[scouting_result_key] = generate_scouting_narrative(
                        player_match_b,
                        player_id_b,
                        use_api=scouting_use_api,
                    )
                    st.session_state.pop(scouting_paths_key, None)
                except Exception as exc:
                    st.error(f"No se pudo generar scouting individual B: {exc}")

        if scouting_cols[2].button(
            "Scouting comparativo",
            key=f"scouting_comparative_{player_match_a}_{player_id_a}_{player_match_b}_{player_id_b}",
        ):
            with st.spinner("Generando scouting comparativo..."):
                try:
                    st.session_state[scouting_result_key] = generate_scouting_narrative(
                        player_match_a,
                        player_id_a,
                        player_match_b,
                        player_id_b,
                        use_api=scouting_use_api,
                    )
                    st.session_state.pop(scouting_paths_key, None)
                except Exception as exc:
                    st.error(f"No se pudo generar scouting comparativo: {exc}")

        current_scouting = st.session_state.get(scouting_result_key)
        if scouting_cols[3].button(
            "Guardar scouting profesional",
            disabled=current_scouting is None,
            key=f"scouting_save_{player_match_a}_{player_id_a}_{player_match_b}_{player_id_b}",
        ):
            if current_scouting:
                try:
                    paths = save_scouting_report(
                        current_scouting,
                        include_html=scouting_include_html,
                        include_docx=scouting_include_docx,
                        include_pdf=scouting_include_pdf,
                        use_api=scouting_use_api,
                    )
                    st.session_state[scouting_paths_key] = paths
                    st.success("Scouting profesional guardado.")
                except Exception as exc:
                    st.error(f"No se pudo guardar scouting: {exc}")

        if current_scouting:
            scouting_warnings = current_scouting.get("warnings", [])
            if scouting_warnings:
                st.warning("Advertencias de Scouting AI")
                for warning in scouting_warnings:
                    st.write(f"- {warning}")
            scouting_language_warnings = current_scouting.get("language_warnings", [])
            if scouting_language_warnings:
                st.warning("Warnings de lenguaje")
                for warning in scouting_language_warnings:
                    st.write(f"- {warning}")
            st.markdown(current_scouting.get("narrative_markdown") or "")

        scouting_paths = st.session_state.get(scouting_paths_key)
        if scouting_paths:
            st.markdown("#### Rutas generadas")
            route_labels = {
                "markdown": "Markdown",
                "html": "HTML",
                "json": "JSON",
                "pdf": "PDF",
                "docx": "DOCX",
            }
            for key, label in route_labels.items():
                if scouting_paths.get(key):
                    st.write(f"**{label}:** `{scouting_paths[key]}`")
            status_cols = st.columns(2)
            status_cols[0].metric("PDF", scouting_paths.get("pdf_status", "not_requested"))
            status_cols[1].metric("DOCX", scouting_paths.get("docx_status", "not_requested"))
            if scouting_paths.get("pdf_warning_message"):
                st.info(f"PDF: {scouting_paths.get('pdf_warning_message')}")
            if scouting_paths.get("pdf_error_message"):
                st.warning(f"PDF: {scouting_paths.get('pdf_error_message')}")
            if scouting_paths.get("docx_error_message"):
                st.warning(f"DOCX: {scouting_paths.get('docx_error_message')}")
            if scouting_paths.get("history_error_message"):
                st.warning(f"Historial: {scouting_paths.get('history_error_message')}")

        st.markdown("#### Historial de scouting")
        scouting_history_rows = list_scouting_history(limit=25)
        if scouting_history_rows:
            st.dataframe(pd.DataFrame(scouting_history_rows), width="stretch")
        else:
            st.caption("Aún no hay historial de scouting.")

with tabs[11]:
    st.subheader("Scouting AI v2")
    st.write("Perfil táctico y arquetipos inferidos desde métricas observadas del partido.")

    v2_match_labels = list(options.keys())
    v2_default_a_index = next((idx for idx, label in enumerate(v2_match_labels) if options[label] == 7534), 0)
    v2_mode = st.radio(
        "Modo",
        ["Individual", "Comparativo"],
        horizontal=True,
        key="scouting_v2_mode",
    )
    v2_selector_cols = st.columns(2)
    v2_label_a = v2_selector_cols[0].selectbox(
        "Partido A",
        v2_match_labels,
        index=v2_default_a_index,
        key="scouting_v2_match_a",
    )
    v2_match_a = options[v2_label_a]
    v2_players_a = list_players_for_match(v2_match_a)
    if not v2_players_a:
        st.warning("No hay jugadores transformados para el Partido A.")
    else:
        v2_player_options_a = {
            f"{row.get('player_name')} | {row.get('team_name')} | eventos {row.get('events')} | id {row.get('player_id')}": int(
                row["player_id"]
            )
            for row in v2_players_a
        }
        v2_default_player_a = next(
            (label for label, value in v2_player_options_a.items() if value == 5571),
            next(iter(v2_player_options_a)),
        )
        v2_player_label_a = v2_selector_cols[0].selectbox(
            "Jugador A",
            list(v2_player_options_a.keys()),
            index=list(v2_player_options_a.keys()).index(v2_default_player_a),
            key="scouting_v2_player_a",
        )
        v2_player_a = v2_player_options_a[v2_player_label_a]

        v2_match_b = None
        v2_player_b = None
        if v2_mode == "Comparativo":
            v2_label_b = v2_selector_cols[1].selectbox(
                "Partido B",
                v2_match_labels,
                index=v2_default_a_index,
                key="scouting_v2_match_b",
            )
            v2_match_b = options[v2_label_b]
            v2_players_b = list_players_for_match(v2_match_b)
            if not v2_players_b:
                st.warning("No hay jugadores transformados para el Partido B.")
            else:
                v2_player_options_b = {
                    f"{row.get('player_name')} | {row.get('team_name')} | eventos {row.get('events')} | id {row.get('player_id')}": int(
                        row["player_id"]
                    )
                    for row in v2_players_b
                }
                v2_default_player_b = next(
                    (label for label, value in v2_player_options_b.items() if value == 5579),
                    next(iter(v2_player_options_b)),
                )
                v2_player_label_b = v2_selector_cols[1].selectbox(
                    "Jugador B",
                    list(v2_player_options_b.keys()),
                    index=list(v2_player_options_b.keys()).index(v2_default_player_b),
                    key="scouting_v2_player_b",
                )
                v2_player_b = v2_player_options_b[v2_player_label_b]

        export_v2_cols = st.columns(3)
        v2_include_html = export_v2_cols[0].checkbox("Generar HTML", value=True, key="scouting_v2_html")
        v2_include_docx = export_v2_cols[1].checkbox("Generar DOCX", value=False, key="scouting_v2_docx")
        v2_include_pdf = export_v2_cols[2].checkbox("Generar PDF", value=False, key="scouting_v2_pdf")

        v2_result_key = f"scouting_v2_result_{v2_mode}_{v2_match_a}_{v2_player_a}_{v2_match_b}_{v2_player_b}"
        v2_paths_key = f"scouting_v2_paths_{v2_mode}_{v2_match_a}_{v2_player_a}_{v2_match_b}_{v2_player_b}"
        v2_action_cols = st.columns(2)
        can_generate_v2 = v2_mode == "Individual" or (v2_match_b is not None and v2_player_b is not None)
        if v2_action_cols[0].button("Generar Scouting AI v2", disabled=not can_generate_v2):
            with st.spinner("Generando perfil táctico v2..."):
                try:
                    if v2_mode == "Comparativo":
                        st.session_state[v2_result_key] = generate_scouting_v2(
                            v2_match_a,
                            v2_player_a,
                            int(v2_match_b),
                            int(v2_player_b),
                        )
                    else:
                        st.session_state[v2_result_key] = generate_scouting_v2(v2_match_a, v2_player_a)
                    st.session_state.pop(v2_paths_key, None)
                except Exception as exc:
                    st.error(f"No se pudo generar Scouting AI v2: {exc}")

        current_v2 = st.session_state.get(v2_result_key)
        if v2_action_cols[1].button(
            "Guardar Scouting AI v2",
            disabled=current_v2 is None,
            key=f"save_{v2_paths_key}",
        ):
            if current_v2:
                try:
                    st.session_state[v2_paths_key] = save_scouting_v2_report(
                        current_v2,
                        include_html=v2_include_html,
                        include_docx=v2_include_docx,
                        include_pdf=v2_include_pdf,
                    )
                    st.success("Scouting AI v2 guardado.")
                except Exception as exc:
                    st.error(f"No se pudo guardar Scouting AI v2: {exc}")

        if current_v2:
            profile_a = current_v2.get("profile_a", {})
            profile_b = current_v2.get("profile_b") or {}
            metric_cols = st.columns(4)
            metric_cols[0].metric("Arquetipo A", profile_a.get("archetype"))
            metric_cols[1].metric("Confianza A", profile_a.get("confidence"))
            metric_cols[2].metric("Secundario A", profile_a.get("secondary_archetype", {}).get("name"))
            metric_cols[3].metric("Rol observado A", profile_a.get("position_name"))
            if profile_b:
                metric_cols_b = st.columns(4)
                metric_cols_b[0].metric("Arquetipo B", profile_b.get("archetype"))
                metric_cols_b[1].metric("Confianza B", profile_b.get("confidence"))
                metric_cols_b[2].metric("Secundario B", profile_b.get("secondary_archetype", {}).get("name"))
                metric_cols_b[3].metric("Rol observado B", profile_b.get("position_name"))

            st.plotly_chart(plot_player_radar(current_v2.get("radar_metrics", {})), width="stretch")
            strength_cols = st.columns(2)
            with strength_cols[0]:
                st.markdown("#### Fortalezas A")
                st.write(profile_a.get("strengths", []) or ["Sin fortalezas dominantes"])
                st.markdown("#### Limitaciones A")
                st.write(profile_a.get("weaknesses", []) or ["Sin limitaciones dominantes"])
            with strength_cols[1]:
                if profile_b:
                    st.markdown("#### Fortalezas B")
                    st.write(profile_b.get("strengths", []) or ["Sin fortalezas dominantes"])
                    st.markdown("#### Limitaciones B")
                    st.write(profile_b.get("weaknesses", []) or ["Sin limitaciones dominantes"])
                else:
                    st.markdown("#### Scores de arquetipo")
                    st.dataframe(pd.DataFrame(profile_a.get("archetype_scores", [])[:8]), width="stretch")

            warnings_v2 = current_v2.get("warnings", [])
            if warnings_v2:
                st.warning("Riesgos de interpretación")
                for warning in warnings_v2:
                    st.write(f"- {warning}")
            st.markdown(current_v2.get("narrative_markdown") or "")

        v2_paths = st.session_state.get(v2_paths_key)
        if v2_paths:
            st.markdown("#### Rutas generadas")
            for key, label in {
                "markdown": "Markdown",
                "html": "HTML",
                "json": "JSON",
                "pdf": "PDF",
                "docx": "DOCX",
            }.items():
                if v2_paths.get(key):
                    st.write(f"**{label}:** `{v2_paths[key]}`")
            status_v2_cols = st.columns(2)
            status_v2_cols[0].metric("PDF", v2_paths.get("pdf_status", "not_requested"))
            status_v2_cols[1].metric("DOCX", v2_paths.get("docx_status", "not_requested"))
            if v2_paths.get("pdf_warning_message"):
                st.info(f"PDF: {v2_paths.get('pdf_warning_message')}")
            if v2_paths.get("pdf_error_message"):
                st.warning(f"PDF: {v2_paths.get('pdf_error_message')}")
            if v2_paths.get("docx_error_message"):
                st.warning(f"DOCX: {v2_paths.get('docx_error_message')}")

with tabs[12]:
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

with tabs[13]:
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
