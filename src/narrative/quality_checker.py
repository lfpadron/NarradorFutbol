"""Heuristic quality checks for generated narratives."""

from __future__ import annotations

from typing import Any

from src.narrative.fact_guard import normalize_text, validate_narrative_against_context


def evaluate_narrative_quality(narrative: str, context: dict[str, Any]) -> dict[str, Any]:
    text = normalize_text(narrative)
    words = narrative.split()
    summary = context.get("match_summary", {})
    home = str(summary.get("home_team_name") or "")
    away = str(summary.get("away_team_name") or "")
    winner = str(summary.get("winner_team_name") or "")
    home_score = int(summary.get("home_score") or 0)
    away_score = int(summary.get("away_score") or 0)
    score_patterns = {
        f"{home_score}-{away_score}",
        f"{home_score} - {away_score}",
        f"{away_score}-{home_score}",
        f"{away_score} - {home_score}",
    }

    checks = {
        "marcador correcto": any(pattern in narrative for pattern in score_patterns),
        "equipos correctos": _contains_team(text, home) and _contains_team(text, away),
        "ganador correcto": not winner or _contains_team(text, winner),
        "dominio del partido": _has_any(
            text, ("dominio", "domino", "dominante", "control territorial", "peso territorial")
        ),
        "xG": "xg" in text,
        "jugador destacado": _mentions_any_player(text, context),
        "momentos clave": _has_any(text, ("momento clave", "minuto", "gol", "ocasion", "asistencia")),
        "explicacion tactica": _has_any(
            text,
            ("tactica", "transicion", "presion", "tercio", "pases", "bloque", "volumen", "eficacia"),
        ),
        "lectura final": "lectura final" in text or "# lectura final" in text,
    }

    detected_elements = [name for name, present in checks.items() if present]
    missing_elements = [name for name, present in checks.items() if not present]
    fact_warnings = validate_narrative_against_context(narrative, context)

    factuality_score = _clamp(100 - len(fact_warnings) * 15)
    coverage_score = _clamp(round(100 * len(detected_elements) / len(checks)))
    clarity_score = _score_clarity(narrative, len(words))
    excitement_score = _score_excitement(text)
    tactical_depth_score = _score_tactical_depth(text)

    warnings = list(fact_warnings)
    warnings.extend(_length_warnings(len(words)))
    warnings.extend(_coverage_warnings(missing_elements))

    overall_score = _clamp(
        round(
            factuality_score * 0.30
            + coverage_score * 0.25
            + clarity_score * 0.15
            + excitement_score * 0.15
            + tactical_depth_score * 0.15
        )
    )

    return {
        "overall_score": overall_score,
        "factuality_score": factuality_score,
        "coverage_score": coverage_score,
        "clarity_score": clarity_score,
        "excitement_score": excitement_score,
        "tactical_depth_score": tactical_depth_score,
        "warnings": warnings,
        "missing_elements": missing_elements,
        "detected_elements": detected_elements,
    }


def _contains_team(text: str, team: str) -> bool:
    if not team:
        return False
    team_norm = normalize_text(team)
    aliases = {
        "germany": {"germany", "alemania"},
        "mexico": {"mexico", "méxico"},
    }.get(team_norm, {team_norm})
    return any(alias in text for alias in aliases)


def _mentions_any_player(text: str, context: dict[str, Any]) -> bool:
    for key in ("impact_players", "top_players", "player_stats"):
        for row in context.get(key, []):
            name = str(row.get("player_name") or "")
            if not name:
                continue
            tokens = [token for token in normalize_text(name).split() if len(token) >= 4]
            if tokens and any(token in text for token in tokens):
                return True
    return False


def _has_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _score_clarity(narrative: str, word_count: int) -> int:
    score = 70
    if "#" in narrative:
        score += 15
    if 120 <= word_count <= 900:
        score += 15
    elif word_count < 80:
        score -= 25
    elif word_count > 1300:
        score -= 20
    return _clamp(score)


def _score_excitement(text: str) -> int:
    words = (
        "emocion",
        "decisivo",
        "tension",
        "amenaza",
        "eficaz",
        "contundencia",
        "ritmo",
        "peligroso",
        "gol",
    )
    matches = sum(1 for word in words if word in text)
    return _clamp(45 + matches * 8)


def _score_tactical_depth(text: str) -> int:
    words = (
        "dominio",
        "xg",
        "transicion",
        "presion",
        "tercio",
        "pases",
        "volumen",
        "eficacia",
        "ataques peligrosos",
        "tactica",
    )
    matches = sum(1 for word in words if word in text)
    return _clamp(35 + matches * 8)


def _length_warnings(word_count: int) -> list[str]:
    if word_count < 80:
        return ["La narrativa es demasiado corta para una revisión analítica útil."]
    if word_count > 1300:
        return ["La narrativa es demasiado larga para un consumo rápido."]
    return []


def _coverage_warnings(missing_elements: list[str]) -> list[str]:
    return [f"Elemento narrativo ausente: {element}." for element in missing_elements]


def _clamp(value: int | float) -> int:
    return max(0, min(100, int(round(value))))
