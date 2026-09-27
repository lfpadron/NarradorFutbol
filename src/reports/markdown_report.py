"""Markdown renderer for final match reports."""

from __future__ import annotations

from typing import Any

from src.ui.i18n import is_english


def render_markdown_report(report: dict[str, Any]) -> str:
    summary = report.get("match_summary", {})
    metadata = report.get("match_metadata", {})
    analytics = report.get("analytics", {})
    narrative = report.get("narrative", {})
    quality = report.get("quality", {})
    validation = analytics.get("validation", {})
    english = is_english(report.get("language"))

    return "\n".join(
        [
            "# Match Report" if english else "# Reporte del partido",
            "",
            "## General Data" if english else "## Datos generales",
            "",
            f"- **{'Competition' if english else 'Competencia'}:** {_value(metadata.get('competition_name'))}",
            f"- **{'Season' if english else 'Temporada'}:** {_value(metadata.get('season_name'))}",
            f"- **{'Date' if english else 'Fecha'}:** {_value(summary.get('match_date') or metadata.get('match_date'))}",
            f"- **{'Match' if english else 'Partido'}:** {_score_line(summary)}",
            f"- **{'Score' if english else 'Marcador'}:** {summary.get('home_score')}-{summary.get('away_score')}",
            f"- **Match ID:** {summary.get('match_id') or report.get('match_id')}",
            f"- **{'Stadium' if english else 'Estadio'}:** {_value(metadata.get('stadium_name'))}",
            f"- **{'Referee' if english else 'Árbitro'}:** {_value(metadata.get('referee_name'))}",
            "",
            "## Executive Summary" if english else "## Resumen ejecutivo",
            "",
            _executive_summary(report, english=english),
            "",
            "## Main Statistics" if english else "## Estadísticas principales",
            "",
            _team_stats_table(analytics, english=english),
            "",
            "## Dominance Read" if english else "## Lectura del dominio",
            "",
            _dominance_reading(report, english=english),
            "",
            "## Key Moments" if english else "## Momentos clave",
            "",
            _key_moments(analytics.get("key_moments", []), english=english),
            "",
            "## Standout Players" if english else "## Jugadores destacados",
            "",
            _impact_players_table(analytics.get("impact_players", []), english=english),
            "",
            "## AI Narrative" if english else "## Narración AI",
            "",
            str(
                narrative.get("narrative_markdown")
                or ("Narrative unavailable." if english else "Narración no disponible.")
            ),
            "",
            "## Narrative Quality Evaluation" if english else "## Evaluación de calidad narrativa",
            "",
            _quality_table(quality, english=english),
            "",
            _warnings_list("Warnings" if english else "Advertencias", quality.get("warnings", []), english=english),
            "",
            "## Football Validation" if english else "## Validación futbolística",
            "",
            f"- **Status:** {validation.get('status', 'N/D')}",
            "",
            _validation_findings(validation, english=english),
            "",
            "## Traceability" if english else "## Trazabilidad",
            "",
            _traceability(report, english=english),
            "",
        ]
    )


def _score_line(summary: dict[str, Any]) -> str:
    return (
        f"{summary.get('home_team_name')} {summary.get('home_score')}-"
        f"{summary.get('away_score')} {summary.get('away_team_name')}"
    )


def _executive_summary(report: dict[str, Any], english: bool = False) -> str:
    summary = report.get("match_summary", {})
    analytics = report.get("analytics", {})
    dominance = analytics.get("dominance", [])
    winner = summary.get("winner_team_name") or "N/D"
    leader = dominance[0] if dominance else {}
    if english:
        return (
            f"{_score_line(summary)}. The winner was **{winner}**. "
            f"Estimated dominance favored **{leader.get('team_name', 'N/D')}** "
            f"with a score of {leader.get('dominance_score', 'N/D')}, while the final read combines "
            "attacking volume, xG, dangerous attacks, and finishing efficiency."
        )
    return (
        f"{_score_line(summary)}. El ganador fue **{winner}**. "
        f"El dominio estimado favoreció a **{leader.get('team_name', 'N/D')}** "
        f"con score {leader.get('dominance_score', 'N/D')}, mientras la lectura final combina "
        "volumen ofensivo, xG, ataques peligrosos y eficacia frente al arco."
    )


def _team_stats_table(analytics: dict[str, Any], english: bool = False) -> str:
    team_stats = analytics.get("team_stats", [])
    dangerous_counts = _dangerous_counts(analytics.get("dangerous_attacks", []))
    possession_summary = analytics.get("possession_summary", {})
    possessions_by_team = (
        possession_summary.get("possessions_by_team", {}) if isinstance(possession_summary, dict) else {}
    )
    lines = (
        [
            "| Team | Shots | Goals | xG | Passes | Pass accuracy | Possessions | Dangerous attacks |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        if english
        else [
            "| Equipo | Tiros | Goles | xG | Pases | Precisión pase | Posesiones | Ataques peligrosos |",
            "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for team in team_stats:
        name = team.get("team_name")
        lines.append(
            f"| {name} | {team.get('shots', 0)} | {team.get('goals', 0)} | "
            f"{_number(team.get('xg'))} | {team.get('passes', 0)} | "
            f"{_number(team.get('pass_completion_pct'))}% | "
            f"{possessions_by_team.get(str(name), 'N/D')} | {dangerous_counts.get(str(name), 0)} |"
        )
    return "\n".join(lines)


def _dominance_reading(report: dict[str, Any], english: bool = False) -> str:
    analytics = report.get("analytics", {})
    summary = report.get("match_summary", {})
    dominance = analytics.get("dominance", [])
    xg_breakdown = analytics.get("xg_breakdown", [])
    winner = summary.get("winner_team_name")
    if not dominance:
        return "No dominance data is available." if english else "No hay datos de dominio disponibles."
    leader = dominance[0]
    xg_lines = ", ".join(f"{row.get('team_name')} xG {row.get('xg_total')}" for row in xg_breakdown)
    if english:
        return (
            f"The dominant team by volume was **{leader.get('team_name')}**, with "
            f"{leader.get('shots')} shots, {leader.get('final_third_entries')} final-third entries "
            f"and a dominance score of {leader.get('dominance_score')}. "
            f"In xG: {xg_lines}. "
            f"The winner was **{winner}**, which points to finishing efficiency against territorial dominance."
        )
    return (
        f"El equipo dominante por volumen fue **{leader.get('team_name')}**, con "
        f"{leader.get('shots')} tiros, {leader.get('final_third_entries')} entradas al último tercio "
        f"y score de dominio {leader.get('dominance_score')}. "
        f"En xG: {xg_lines}. "
        f"El ganador fue **{winner}**, lo que apunta a una lectura de efectividad frente al dominio territorial."
    )


def _key_moments(key_moments: list[dict[str, Any]], english: bool = False) -> str:
    if not key_moments:
        return "- No key moments were detected." if english else "- No se detectaron momentos clave."
    lines = []
    for moment in key_moments:
        second = int(moment.get("second") or 0)
        separator = " - " if english else " — "
        lines.append(
            f"- {moment.get('minute')}:{second:02d}{separator}"
            f"**{moment.get('type')}**{separator}{moment.get('title')}"
        )
    return "\n".join(lines)


def _impact_players_table(players: list[dict[str, Any]], limit: int = 10, english: bool = False) -> str:
    if not players:
        return "No standout players are available." if english else "No hay jugadores destacados disponibles."
    lines = (
        [
            "| Player | Team | Score | Goals | Assists | Shots | xG | Key passes |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
        if english
        else [
            "| Jugador | Equipo | Score | Goles | Asistencias | Tiros | xG | Pases clave |",
            "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for player in players[:limit]:
        lines.append(
            f"| {player.get('player_name')} | {player.get('team_name')} | {player.get('impact_score')} | "
            f"{player.get('goals')} | {player.get('assists')} | {player.get('shots')} | "
            f"{player.get('xg')} | {player.get('key_passes')} |"
        )
    return "\n".join(lines)


def _quality_table(quality: dict[str, Any], english: bool = False) -> str:
    rows = (
        [
            ("overall_score", "Overall"),
            ("factuality_score", "Factuality"),
            ("coverage_score", "Coverage"),
            ("clarity_score", "Clarity"),
            ("excitement_score", "Excitement"),
            ("tactical_depth_score", "Tactical depth"),
        ]
        if english
        else [
            ("overall_score", "Overall"),
            ("factuality_score", "Factualidad"),
            ("coverage_score", "Cobertura"),
            ("clarity_score", "Claridad"),
            ("excitement_score", "Emoción"),
            ("tactical_depth_score", "Profundidad táctica"),
        ]
    )
    lines = ["| Metric | Score |" if english else "| Métrica | Score |", "| --- | ---: |"]
    lines.extend(f"| {label} | {quality.get(key, 'N/D')} |" for key, label in rows)
    return "\n".join(lines)


def _validation_findings(validation: dict[str, Any], english: bool = False) -> str:
    findings = validation.get("findings", [])
    if not findings:
        return "- No findings." if english else "- Sin hallazgos."
    return "\n".join(
        f"- **{finding.get('severity')}** - {finding.get('message')} "
        f"({finding.get('rows')} {'rows' if english else 'filas'})"
        for finding in findings
    )


def _warnings_list(title: str, warnings: list[str], english: bool = False) -> str:
    if not warnings:
        return f"**{title}:** {'no warnings.' if english else 'sin advertencias.'}"
    lines = [f"**{title}:**"]
    lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines)


def _traceability(report: dict[str, Any], english: bool = False) -> str:
    model = report.get("narrative", {}).get("model") or ("N/A" if english else "N/D")
    if english:
        return "\n".join(
            [
                "- **Source:** StatsBomb Open Data.",
                "- **Raw JSON:** preserved in `data/raw/` without analytical modifications.",
                "- **Analytical DuckDB:** `data/analytics/statsbomb.duckdb`.",
                "- **AI context:** built from `src/analytics/ai_context.py`, without sending all raw events to the narrator.",
                f"- **Model:** {model}.",
                f"- **Generated at:** {report.get('generated_at')}.",
            ]
        )
    return "\n".join(
        [
            "- **Fuente:** StatsBomb Open Data.",
            "- **Raw JSON:** preservado en `data/raw/` sin modificaciones analíticas.",
            "- **DuckDB analítico:** `data/analytics/statsbomb.duckdb`.",
            "- **Contexto AI:** construido desde `src/analytics/ai_context.py`, sin pasar todos los eventos crudos al narrador.",
            f"- **Modelo:** {model}.",
            f"- **Fecha de generación:** {report.get('generated_at')}.",
        ]
    )


def _dangerous_counts(attacks: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for attack in attacks:
        team = str(attack.get("team_name") or "Sin equipo")
        counts[team] = counts.get(team, 0) + 1
    return counts


def _number(value: Any) -> str:
    if value is None:
        return "N/D"
    try:
        return f"{float(value):.2f}"
    except (TypeError, ValueError):
        return str(value)


def _value(value: Any) -> str:
    return str(value) if value not in (None, "") else "N/D"
