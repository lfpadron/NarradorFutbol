"""Tactical profile inference for Scouting AI v2."""

from __future__ import annotations

from typing import Any

from src.comparison.player_comparison import compare_players
from src.ingestion.utils import to_jsonable
from src.scouting.player_archetypes import ARCHETYPES, PlayerArchetype


NORMALIZATION_CAPS: dict[str, float] = {
    "xg": 0.7,
    "shots": 6,
    "goals": 1,
    "assists": 2,
    "key_passes": 6,
    "passes": 90,
    "successful_passes": 80,
    "pass_accuracy_pct": 92,
    "progressive_passes": 7,
    "carries": 70,
    "carry_distance": 500,
    "pressures": 30,
    "counterpressures": 8,
    "duels": 8,
    "events": 220,
    "impact_score": 35,
}


def build_tactical_profile(match_id: int, player_id: int) -> dict[str, Any]:
    """Infer a tactical profile from one player's observed match metrics."""

    comparison = compare_players(match_id, player_id, match_id, player_id)
    player = comparison.get("player_a", {})
    normalized = _normalized_metrics(player)
    archetype_scores = _score_archetypes(normalized, str(player.get("position_name") or ""))
    primary = archetype_scores[0] if archetype_scores else {}
    secondary = archetype_scores[1] if len(archetype_scores) > 1 else {}

    profile = {
        "player_name": player.get("player_name"),
        "player_id": player.get("player_id"),
        "match_id": player.get("match_id"),
        "team_name": player.get("team_name"),
        "position_name": player.get("position_name"),
        "archetype": primary.get("name"),
        "primary_archetype": primary,
        "secondary_archetype": secondary,
        "confidence": primary.get("score", 0),
        "attack_profile": _attack_profile(player, normalized),
        "creation_profile": _creation_profile(player, normalized),
        "progression_profile": _progression_profile(player, normalized),
        "defensive_profile": _defensive_profile(player, normalized),
        "impact_profile": _impact_profile(player, normalized),
        "strengths": _strengths(normalized, player),
        "weaknesses": _weaknesses(normalized),
        "raw_metrics": player,
        "normalized_metrics": normalized,
        "archetype_scores": archetype_scores,
        "warnings": _warnings(player, primary),
    }
    return to_jsonable(profile)


def _normalized_metrics(player: dict[str, Any]) -> dict[str, float]:
    normalized = {}
    for key, cap in NORMALIZATION_CAPS.items():
        value = _number(player.get(key))
        normalized[key] = 0.0 if cap <= 0 else round(min(100.0, (value / cap) * 100.0), 1)
    return normalized


def _score_archetypes(normalized: dict[str, float], position_name: str) -> list[dict[str, Any]]:
    scores = []
    for archetype in ARCHETYPES:
        weighted = sum(normalized.get(metric, 0.0) * weight for metric, weight in archetype.weights.items())
        bonus = _position_bonus(archetype, position_name)
        adjustment = _compatibility_adjustment(archetype.name, position_name)
        score = round(max(0.0, min(100.0, weighted + bonus + adjustment)), 1)
        scores.append(
            {
                "name": archetype.name,
                "description": archetype.description,
                "score": score,
                "metrics": list(archetype.relevant_metrics),
                "weights": archetype.weights,
                "position_bonus": bonus,
                "position_adjustment": adjustment,
            }
        )
    scores.sort(key=lambda item: item["score"], reverse=True)
    return scores


def _position_bonus(archetype: PlayerArchetype, position_name: str) -> float:
    if not position_name or not archetype.position_keywords:
        return 0.0
    normalized_position = position_name.lower()
    if any(keyword in normalized_position for keyword in archetype.position_keywords):
        return archetype.position_bonus
    return 0.0


def _compatibility_adjustment(archetype_name: str, position_name: str) -> float:
    normalized_position = position_name.lower()
    if archetype_name in {"Central constructor", "Central defensivo"} and not any(
        keyword in normalized_position for keyword in ("center back", "central")
    ):
        return -18.0
    if archetype_name in {"Recuperador", "Mediocentro destructor", "Box-to-box"} and "wing" in normalized_position:
        return -12.0
    return 0.0


def _attack_profile(player: dict[str, Any], normalized: dict[str, float]) -> dict[str, Any]:
    score = _weighted_average(normalized, {"xg": 0.3, "shots": 0.25, "goals": 0.25, "impact_score": 0.2})
    return {
        "score": score,
        "label": _label(score),
        "xg": player.get("xg"),
        "shots": player.get("shots"),
        "goals": player.get("goals"),
    }


def _creation_profile(player: dict[str, Any], normalized: dict[str, float]) -> dict[str, Any]:
    score = _weighted_average(normalized, {"key_passes": 0.45, "assists": 0.25, "pass_accuracy_pct": 0.15, "progressive_passes": 0.15})
    return {
        "score": score,
        "label": _label(score),
        "key_passes": player.get("key_passes"),
        "assists": player.get("assists"),
        "pass_accuracy_pct": player.get("pass_accuracy_pct"),
    }


def _progression_profile(player: dict[str, Any], normalized: dict[str, float]) -> dict[str, Any]:
    score = _weighted_average(normalized, {"progressive_passes": 0.35, "carries": 0.3, "carry_distance": 0.25, "passes": 0.1})
    return {
        "score": score,
        "label": _label(score),
        "progressive_passes": player.get("progressive_passes"),
        "carries": player.get("carries"),
        "carry_distance": player.get("carry_distance"),
    }


def _defensive_profile(player: dict[str, Any], normalized: dict[str, float]) -> dict[str, Any]:
    score = _weighted_average(normalized, {"pressures": 0.45, "duels": 0.25, "counterpressures": 0.2, "events": 0.1})
    return {
        "score": score,
        "label": _label(score),
        "pressures": player.get("pressures"),
        "duels": player.get("duels"),
        "counterpressures": player.get("counterpressures"),
    }


def _impact_profile(player: dict[str, Any], normalized: dict[str, float]) -> dict[str, Any]:
    score = _weighted_average(normalized, {"impact_score": 0.45, "events": 0.2, "goals": 0.2, "key_passes": 0.15})
    return {
        "score": score,
        "label": _label(score),
        "impact_score": player.get("impact_score"),
        "events": player.get("events"),
        "key_moments_count": player.get("key_moments_count"),
    }


def _strengths(normalized: dict[str, float], player: dict[str, Any]) -> list[str]:
    items = []
    candidates = [
        ("Definición e incidencia ofensiva", max(normalized["goals"], normalized["xg"], normalized["shots"])),
        ("Creación de ventaja", max(normalized["key_passes"], normalized["assists"])),
        ("Volumen de pase y organización", max(normalized["passes"], normalized["successful_passes"], normalized["events"])),
        ("Progresión con pase o conducción", max(normalized["progressive_passes"], normalized["carries"], normalized["carry_distance"])),
        ("Presión y actividad sin balón", max(normalized["pressures"], normalized["counterpressures"])),
        ("Impacto observable", normalized["impact_score"]),
    ]
    for label, score in candidates:
        if score >= 70:
            items.append(label)
    if not items and _number(player.get("events")) > 0:
        items.append("Participación observable en el plan de partido")
    return items


def _weaknesses(normalized: dict[str, float]) -> list[str]:
    items = []
    candidates = [
        ("Amenaza de remate limitada en este partido", max(normalized["xg"], normalized["shots"], normalized["goals"])),
        ("Creación directa limitada", max(normalized["key_passes"], normalized["assists"])),
        ("Progresión limitada", max(normalized["progressive_passes"], normalized["carries"], normalized["carry_distance"])),
        ("Participación defensiva baja", max(normalized["pressures"], normalized["duels"], normalized["counterpressures"])),
    ]
    for label, score in candidates:
        if score <= 30:
            items.append(label)
    return items


def _warnings(player: dict[str, Any], primary: dict[str, Any]) -> list[str]:
    warnings = [
        "Perfil inferido a partir de métricas observadas en un solo partido; no equivale a posición oficial ni proyección de carrera."
    ]
    if _number(player.get("events")) < 30:
        warnings.append("Muestra de eventos baja; leer el arquetipo con cautela.")
    if _number(primary.get("score")) < 45:
        warnings.append("Confianza baja: ningún arquetipo domina claramente con los datos disponibles.")
    return warnings


def _weighted_average(normalized: dict[str, float], weights: dict[str, float]) -> float:
    return round(sum(normalized.get(metric, 0.0) * weight for metric, weight in weights.items()), 1)


def _label(score: float) -> str:
    if score >= 75:
        return "alto"
    if score >= 50:
        return "medio"
    if score > 0:
        return "bajo"
    return "sin dato"


def _number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
