"""Markdown renderer for final match reports."""

from __future__ import annotations

from typing import Any


def render_markdown_report(report: dict[str, Any]) -> str:
    summary = report.get("match_summary", {})
    metadata = report.get("match_metadata", {})
    analytics = report.get("analytics", {})
    narrative = report.get("narrative", {})
    quality = report.get("quality", {})
    validation = analytics.get("validation", {})

    return "\n".join(
        [
            "# Reporte del partido",
            "",
            "## Datos generales",
            "",
            f"- **Competencia:** {_value(metadata.get('competition_name'))}",
            f"- **Temporada:** {_value(metadata.get('season_name'))}",
            f"- **Fecha:** {_value(summary.get('match_date') or metadata.get('match_date'))}",
            f"- **Partido:** {_score_line(summary)}",
            f"- **Marcador:** {summary.get('home_score')}-{summary.get('away_score')}",
            f"- **Match ID:** {summary.get('match_id') or report.get('match_id')}",
            f"- **Estadio:** {_value(metadata.get('stadium_name'))}",
            f"- **Árbitro:** {_value(metadata.get('referee_name'))}",
            "",
            "## Resumen ejecutivo",
            "",
            _executive_summary(report),
            "",
            "## Estadísticas principales",
            "",
            _team_stats_table(analytics),
            "",
            "## Lectura del dominio",
            "",
            _dominance_reading(report),
            "",
            "## Momentos clave",
            "",
            _key_moments(analytics.get("key_moments", [])),
            "",
            "## Jugadores destacados",
            "",
            _impact_players_table(analytics.get("impact_players", [])),
            "",
            "## Narración AI",
            "",
            str(narrative.get("narrative_markdown") or "Narración no disponible."),
            "",
            "## Evaluación de calidad narrativa",
            "",
            _quality_table(quality),
            "",
            _warnings_list("Warnings", quality.get("warnings", [])),
            "",
            "## Validación futbolística",
            "",
            f"- **Status:** {validation.get('status', 'N/D')}",
            "",
            _validation_findings(validation),
            "",
            "## Trazabilidad",
            "",
            _traceability(report),
            "",
        ]
    )


def _score_line(summary: dict[str, Any]) -> str:
    return (
        f"{summary.get('home_team_name')} {summary.get('home_score')}-"
        f"{summary.get('away_score')} {summary.get('away_team_name')}"
    )


def _executive_summary(report: dict[str, Any]) -> str:
    summary = report.get("match_summary", {})
    analytics = report.get("analytics", {})
    dominance = analytics.get("dominance", [])
    winner = summary.get("winner_team_name") or "N/D"
    leader = dominance[0] if dominance else {}
    return (
        f"{_score_line(summary)}. El ganador fue **{winner}**. "
        f"El dominio estimado favoreció a **{leader.get('team_name', 'N/D')}** "
        f"con score {leader.get('dominance_score', 'N/D')}, mientras la lectura final combina "
        "volumen ofensivo, xG, ataques peligrosos y eficacia frente al arco."
    )


def _team_stats_table(analytics: dict[str, Any]) -> str:
    team_stats = analytics.get("team_stats", [])
    dangerous_counts = _dangerous_counts(analytics.get("dangerous_attacks", []))
    possession_summary = analytics.get("possession_summary", {})
    possessions_by_team = (
        possession_summary.get("possessions_by_team", {}) if isinstance(possession_summary, dict) else {}
    )
    lines = [
        "| Equipo | Tiros | Goles | xG | Pases | Precisión pase | Posesiones | Ataques peligrosos |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for team in team_stats:
        name = team.get("team_name")
        lines.append(
            f"| {name} | {team.get('shots', 0)} | {team.get('goals', 0)} | "
            f"{_number(team.get('xg'))} | {team.get('passes', 0)} | "
            f"{_number(team.get('pass_completion_pct'))}% | "
            f"{possessions_by_team.get(str(name), 'N/D')} | {dangerous_counts.get(str(name), 0)} |"
        )
    return "\n".join(lines)


def _dominance_reading(report: dict[str, Any]) -> str:
    analytics = report.get("analytics", {})
    summary = report.get("match_summary", {})
    dominance = analytics.get("dominance", [])
    xg_breakdown = analytics.get("xg_breakdown", [])
    winner = summary.get("winner_team_name")
    if not dominance:
        return "No hay datos de dominio disponibles."
    leader = dominance[0]
    xg_lines = ", ".join(f"{row.get('team_name')} xG {row.get('xg_total')}" for row in xg_breakdown)
    return (
        f"El equipo dominante por volumen fue **{leader.get('team_name')}**, con "
        f"{leader.get('shots')} tiros, {leader.get('final_third_entries')} entradas al último tercio "
        f"y score de dominio {leader.get('dominance_score')}. "
        f"En xG: {xg_lines}. "
        f"El ganador fue **{winner}**, lo que apunta a una lectura de efectividad frente al dominio territorial."
    )


def _key_moments(key_moments: list[dict[str, Any]]) -> str:
    if not key_moments:
        return "- No se detectaron momentos clave."
    lines = []
    for moment in key_moments:
        second = int(moment.get("second") or 0)
        lines.append(f"- {moment.get('minute')}:{second:02d} — **{moment.get('type')}** — {moment.get('title')}")
    return "\n".join(lines)


def _impact_players_table(players: list[dict[str, Any]], limit: int = 10) -> str:
    if not players:
        return "No hay jugadores destacados disponibles."
    lines = [
        "| Jugador | Equipo | Score | Goles | Asistencias | Tiros | xG | Pases clave |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for player in players[:limit]:
        lines.append(
            f"| {player.get('player_name')} | {player.get('team_name')} | {player.get('impact_score')} | "
            f"{player.get('goals')} | {player.get('assists')} | {player.get('shots')} | "
            f"{player.get('xg')} | {player.get('key_passes')} |"
        )
    return "\n".join(lines)


def _quality_table(quality: dict[str, Any]) -> str:
    rows = [
        ("overall_score", "Overall"),
        ("factuality_score", "Factualidad"),
        ("coverage_score", "Cobertura"),
        ("clarity_score", "Claridad"),
        ("excitement_score", "Emoción"),
        ("tactical_depth_score", "Profundidad táctica"),
    ]
    lines = ["| Métrica | Score |", "| --- | ---: |"]
    lines.extend(f"| {label} | {quality.get(key, 'N/D')} |" for key, label in rows)
    return "\n".join(lines)


def _validation_findings(validation: dict[str, Any]) -> str:
    findings = validation.get("findings", [])
    if not findings:
        return "- Sin hallazgos."
    return "\n".join(
        f"- **{finding.get('severity')}** — {finding.get('message')} ({finding.get('rows')} filas)"
        for finding in findings
    )


def _warnings_list(title: str, warnings: list[str]) -> str:
    if not warnings:
        return f"**{title}:** sin advertencias."
    lines = [f"**{title}:**"]
    lines.extend(f"- {warning}" for warning in warnings)
    return "\n".join(lines)


def _traceability(report: dict[str, Any]) -> str:
    return "\n".join(
        [
            "- **Fuente:** StatsBomb Open Data.",
            "- **Raw JSON:** preservado en `data/raw/` sin modificaciones analíticas.",
            "- **DuckDB analítico:** `data/analytics/statsbomb.duckdb`.",
            "- **Contexto AI:** construido desde `src/analytics/ai_context.py`, sin pasar todos los eventos crudos al narrador.",
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
