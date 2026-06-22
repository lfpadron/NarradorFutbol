"""Lightweight narrative fact checks against curated context."""

from __future__ import annotations

import re
import unicodedata
from typing import Any


SCORE_RE = re.compile(r"\b(\d{1,2})\s*[-–]\s*(\d{1,2})\b")
NAME_RE = re.compile(
    r"\b([A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+(?:\s+[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+){1,4})\b"
)
GOAL_CLAIM_RE = re.compile(
    r"(?i:gol de|anot[óo]|marc[óo])\s+"
    r"([A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+"
    r"(?:\s+(?!de\b|del\b|en\b|por\b|con\b|desde\b)[A-ZÁÉÍÓÚÑÜ][a-záéíóúñü]+){0,4})",
)

IGNORED_NAME_PHRASES = {
    "Resumen Ejecutivo",
    "Crónica Partido",
    "Claves Tácticas",
    "Jugadores Destacados",
    "Momentos Clave",
    "Lectura Final",
    "Validación Futbolística",
    "Tono Seleccionado",
    "Análisis Técnico",
    "Narrativa Markdown",
}

COMMON_TEAMS = {
    "alemania",
    "argentina",
    "belgica",
    "brazil",
    "brasil",
    "chile",
    "colombia",
    "corea",
    "croacia",
    "croatia",
    "england",
    "espana",
    "france",
    "francia",
    "germany",
    "inglaterra",
    "italia",
    "italy",
    "japon",
    "japan",
    "mexico",
    "netherlands",
    "paises bajos",
    "poland",
    "polonia",
    "portugal",
    "south korea",
    "spain",
    "suecia",
    "sweden",
    "uruguay",
}

TEAM_ALIASES = {
    "germany": {"germany", "alemania"},
    "mexico": {"mexico", "méxico"},
}


def validate_narrative_against_context(narrative: str, context: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    summary = context.get("match_summary", {})
    key_moments = context.get("key_moments", [])
    home_score = int(summary.get("home_score") or 0)
    away_score = int(summary.get("away_score") or 0)
    score_diff = abs(home_score - away_score)

    _check_scores(narrative, home_score, away_score, warnings)
    lowered = normalize_text(narrative)
    _check_winner_claims(lowered, context, warnings)
    _check_team_mentions(lowered, context, warnings)
    _check_goal_scorer_claims(narrative, context, warnings)

    if home_score != away_score and "empate" in lowered:
        warnings.append("La narrativa menciona empate, pero el partido no terminó empatado.")
    if score_diff < 3 and "goleada" in lowered:
        warnings.append("La narrativa menciona goleada, pero la diferencia fue menor a 3 goles.")
    if "penal" in lowered and not _has_key_moment(key_moments, ("penalty", "penal")):
        warnings.append("La narrativa menciona penal, pero no hay penal registrado en momentos clave.")
    if ("expulsion" in lowered or "roja" in lowered) and not _has_key_moment(
        key_moments, ("red_card", "expulsion", "roja")
    ):
        warnings.append("La narrativa menciona expulsión o roja, pero no hay tarjeta roja registrada.")
    if "remontada" in lowered and not _context_has_comeback(context):
        warnings.append("La narrativa menciona remontada, pero la secuencia de goles no la sustenta.")

    warnings.extend(_check_player_mentions(narrative, context))
    return warnings


def _check_scores(narrative: str, home_score: int, away_score: int, warnings: list[str]) -> None:
    expected = {(home_score, away_score), (away_score, home_score)}
    for left, right in SCORE_RE.findall(narrative):
        score = (int(left), int(right))
        if score not in expected:
            warnings.append(
                f"La narrativa menciona marcador {score[0]}-{score[1]}, "
                f"distinto al partido {home_score}-{away_score}."
            )


def _check_player_mentions(narrative: str, context: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    allowed_names = _collect_allowed_names(context)
    allowed_norm = {normalize_text(name) for name in allowed_names}
    ignored_norm = {normalize_text(name) for name in IGNORED_NAME_PHRASES}

    for candidate in sorted(set(NAME_RE.findall(narrative))):
        candidate_norm = normalize_text(candidate)
        if candidate_norm in ignored_norm:
            continue
        if candidate_norm in allowed_norm:
            continue
        if _candidate_matches_known_name(candidate_norm, allowed_norm):
            continue
        if _is_team_or_common_phrase(candidate_norm, context):
            continue
        warnings.append(f"Posible jugador no trazado en contexto: {candidate}.")
    return warnings


def _collect_allowed_names(context: dict[str, Any]) -> set[str]:
    names: set[str] = set()
    for key in ("player_stats", "top_players", "impact_players"):
        for row in context.get(key, []):
            name = row.get("player_name")
            if name:
                names.add(str(name))
    for moment in context.get("key_moments", []):
        name = moment.get("player_name")
        if name:
            names.add(str(name))
    return names


def _candidate_matches_known_name(candidate_norm: str, allowed_norm: set[str]) -> bool:
    tokens = candidate_norm.split()
    if len(tokens) < 2:
        return True
    for name in allowed_norm:
        cursor = 0
        name_tokens = name.split()
        for token in tokens:
            try:
                cursor = name_tokens.index(token, cursor) + 1
            except ValueError:
                break
        else:
            return True
    return False


def _is_team_or_common_phrase(candidate_norm: str, context: dict[str, Any]) -> bool:
    summary = context.get("match_summary", {})
    teams = _participant_aliases(summary)
    teams.update(
        {
        "fifa world cup",
        "openai api",
        "statsbomb",
    }
    )
    return candidate_norm in teams


def _check_winner_claims(lowered: str, context: dict[str, Any], warnings: list[str]) -> None:
    summary = context.get("match_summary", {})
    winner = normalize_text(str(summary.get("winner_team_name") or ""))
    teams = [
        normalize_text(str(summary.get("home_team_name") or "")),
        normalize_text(str(summary.get("away_team_name") or "")),
    ]
    if not winner:
        return
    for team in teams:
        if not team or team == winner:
            continue
        aliases = _team_aliases(team)
        for alias in aliases:
            patterns = (
                f"gano {alias}",
                f"{alias} gano",
                f"victoria de {alias}",
                f"triunfo de {alias}",
                f"{alias} fue el ganador",
            )
            if any(pattern in lowered for pattern in patterns):
                warnings.append(f"La narrativa atribuye el triunfo a {alias}, pero el ganador fue {winner}.")
                return


def _check_team_mentions(lowered: str, context: dict[str, Any], warnings: list[str]) -> None:
    summary = context.get("match_summary", {})
    participants = _participant_aliases(summary)
    for team in sorted(COMMON_TEAMS):
        if team in participants:
            continue
        if re.search(rf"\b{re.escape(team)}\b", lowered):
            warnings.append(f"La narrativa menciona un equipo que no participó: {team}.")


def _check_goal_scorer_claims(narrative: str, context: dict[str, Any], warnings: list[str]) -> None:
    goal_scorers = _goal_scorer_names(context)
    if not goal_scorers:
        return
    goal_scorer_norm = {normalize_text(name) for name in goal_scorers}
    for candidate in GOAL_CLAIM_RE.findall(narrative):
        candidate_norm = normalize_text(candidate)
        if _candidate_matches_known_name(candidate_norm, goal_scorer_norm):
            continue
        warnings.append(f"La narrativa atribuye un gol a {candidate}, pero ese jugador no aparece como goleador.")


def _has_key_moment(key_moments: list[dict[str, Any]], needles: tuple[str, ...]) -> bool:
    for moment in key_moments:
        haystack = normalize_text(
            " ".join(
                str(moment.get(key) or "")
                for key in ("type", "title", "description")
            )
        )
        if any(needle in haystack for needle in needles):
            return True
    return False


def _context_has_comeback(context: dict[str, Any]) -> bool:
    summary = context.get("match_summary", {})
    winner = summary.get("winner_team_name")
    if not winner:
        return False
    home = summary.get("home_team_name")
    away = summary.get("away_team_name")
    score = {home: 0, away: 0}
    trailed = False
    goals = [
        moment
        for moment in context.get("key_moments", [])
        if normalize_text(str(moment.get("type") or "")) == "goal"
    ]
    for goal in sorted(goals, key=lambda row: (int(row.get("minute") or 0), int(row.get("second") or 0))):
        team = goal.get("team_name")
        if team in score:
            score[team] += 1
        opponent_scores = [value for team_name, value in score.items() if team_name != winner]
        if opponent_scores and score.get(winner, 0) < max(opponent_scores):
            trailed = True
    return trailed and score.get(winner, 0) == max(score.values())


def _goal_scorer_names(context: dict[str, Any]) -> set[str]:
    names = set()
    for moment in context.get("key_moments", []):
        if normalize_text(str(moment.get("type") or "")) == "goal":
            name = moment.get("player_name")
            if name:
                names.add(str(name))
    return names


def _participant_aliases(summary: dict[str, Any]) -> set[str]:
    aliases: set[str] = set()
    for key in ("home_team_name", "away_team_name", "winner_team_name"):
        team = normalize_text(str(summary.get(key) or ""))
        aliases.update(_team_aliases(team))
    return aliases


def _team_aliases(team: str) -> set[str]:
    team_norm = normalize_text(team)
    return set(TEAM_ALIASES.get(team_norm, {team_norm}))


def normalize_text(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_value).strip().lower()
