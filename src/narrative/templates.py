"""Local fallback narrative templates."""

from __future__ import annotations

from typing import Any

from src.narrative.config import SUPPORTED_TONES, validate_tone


def generate_fallback_narrative(context: dict[str, Any], tone: str) -> str:
    tone = validate_tone(tone)
    summary = context.get("match_summary", {})
    dominance = context.get("dominance", [])
    xg_breakdown = context.get("xg_breakdown", [])
    dangerous_attacks = context.get("dangerous_attacks", [])
    impact_players = context.get("impact_players", [])
    key_moments = context.get("key_moments", [])
    validation = context.get("validation", {})

    home = summary.get("home_team_name", "Local")
    away = summary.get("away_team_name", "Visitante")
    home_score = int(summary.get("home_score") or 0)
    away_score = int(summary.get("away_score") or 0)
    score = f"{home} {home_score}-{away_score} {away}"
    winner = summary.get("winner_team_name") or "sin ganador"
    leader = dominance[0] if dominance else {}
    xg_lines = _format_xg_lines(xg_breakdown)
    impact_lines = _format_impact_players(impact_players)
    moment_lines = _format_key_moments(key_moments)
    transition_note = _format_dangerous_attacks(dangerous_attacks, str(winner))
    validation_note = _format_validation(validation)
    tone_label = SUPPORTED_TONES[tone]

    return f"""
# Resumen ejecutivo

{score}. El resultado terminó con {winner} como ganador. El tono seleccionado es **{tone_label}**.

{validation_note}

# Crónica del partido

El partido dejó una lectura clara: {leader.get("team_name", "un equipo")} llevó el mayor peso territorial y ofensivo, pero el marcador premió la eficacia del rival. El dominio estimado favoreció a {leader.get("team_name", "el equipo más insistente")} con un score de {leader.get("dominance_score", "N/D")}, mientras el marcador quedó en {home_score}-{away_score}.

# Claves tácticas

{xg_lines}

{transition_note}

# Jugadores destacados

{impact_lines}

# Momentos clave

{moment_lines}

# Lectura final

La lectura final combina dominio y eficacia: un equipo produjo más volumen, pero el otro convirtió el momento decisivo. Para una narración posterior, este partido ya ofrece una tensión central muy potente: control territorial contra contundencia.
""".strip()


def _format_xg_lines(xg_breakdown: list[dict[str, Any]]) -> str:
    if not xg_breakdown:
        return "No hay desglose de xG disponible."
    lines = []
    for row in xg_breakdown:
        lines.append(
            f"- {row.get('team_name')}: {row.get('shots')} tiros, "
            f"{row.get('goals')} goles, xG total {row.get('xg_total')}."
        )
    return "\n".join(lines)


def _format_impact_players(impact_players: list[dict[str, Any]], limit: int = 6) -> str:
    if not impact_players:
        return "No hay jugadores de impacto disponibles."
    lines = []
    for player in impact_players[:limit]:
        lines.append(
            f"- {player.get('player_name')} ({player.get('team_name')}): "
            f"score {player.get('impact_score')}, goles {player.get('goals')}, "
            f"pases clave {player.get('key_passes')}."
        )
    return "\n".join(lines)


def _format_key_moments(key_moments: list[dict[str, Any]], limit: int = 6) -> str:
    if not key_moments:
        return "No se detectaron momentos clave."
    lines = []
    for moment in key_moments[:limit]:
        lines.append(
            f"- Minuto {moment.get('minute')}: {moment.get('title')} "
            f"({moment.get('type')})."
        )
    return "\n".join(lines)


def _format_dangerous_attacks(dangerous_attacks: list[dict[str, Any]], winner: str) -> str:
    if not dangerous_attacks:
        return "No se detectaron ataques peligrosos."
    counts: dict[str, int] = {}
    for attack in dangerous_attacks:
        team = str(attack.get("team_name") or "Sin equipo")
        counts[team] = counts.get(team, 0) + 1
    lines = [f"- {team}: {count} ataques peligrosos detectados." for team, count in sorted(counts.items())]
    if winner in counts:
        lines.append(
            f"- {winner} fue eficaz y sostuvo amenaza en transiciones: "
            f"{counts[winner]} ataques peligrosos registrados."
        )
    return "\n".join(lines)


def _format_validation(validation: dict[str, Any]) -> str:
    status = validation.get("status")
    if status and status != "PASS":
        return f"Advertencia: la validación del partido quedó en estado {status}; la lectura puede tener limitaciones."
    return "Validación futbolística: PASS."
