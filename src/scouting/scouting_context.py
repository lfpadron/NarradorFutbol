"""Build scouting context from player comparisons and visual metrics."""

from __future__ import annotations

from typing import Any

from src.comparison.player_comparison import build_player_radar_metrics, compare_players
from src.comparison.player_visuals import plot_player_strengths_weaknesses
from src.ingestion.utils import to_jsonable

INDIVIDUAL_RADAR_CAPS = {
    "Ataque": 28,
    "Creación": 22,
    "Pase": 115,
    "Progresión": 90,
    "Presión": 45,
    "Duelos": 12,
    "Impacto": 45,
}


def build_player_scouting_context(
    match_id_a: int,
    player_id_a: int,
    match_id_b: int | None = None,
    player_id_b: int | None = None,
) -> dict[str, Any]:
    """Build JSON-serializable context for individual or comparative scouting."""

    has_player_b = match_id_b is not None and player_id_b is not None
    if has_player_b:
        comparison = compare_players(match_id_a, player_id_a, int(match_id_b), int(player_id_b))
        radar_metrics = build_player_radar_metrics(comparison)
        strengths = plot_player_strengths_weaknesses(radar_metrics)
        mode = "comparativo"
    else:
        comparison = compare_players(match_id_a, player_id_a, match_id_a, player_id_a)
        comparison["warnings"] = [
            warning
            for warning in comparison.get("warnings", [])
            if "Comparación dentro del mismo partido" not in warning
        ]
        radar_metrics = _build_individual_radar_metrics(comparison.get("player_a", {}))
        strengths = _individual_strengths_weaknesses(radar_metrics)
        mode = "individual"

    player_a = comparison.get("player_a", {})
    player_b = comparison.get("player_b") if has_player_b else None
    context = {
        "mode": mode,
        "match_a": comparison.get("match_a", {}),
        "match_b": comparison.get("match_b") if has_player_b else None,
        "player_a": player_a,
        "player_b": player_b,
        "comparison": comparison if has_player_b else None,
        "metrics": {
            "offensive": comparison.get("attacking_comparison", {}),
            "creation": comparison.get("passing_comparison", {}),
            "passing": comparison.get("passing_comparison", {}),
            "defensive": comparison.get("defensive_comparison", {}),
            "impact": comparison.get("impact_comparison", {}),
        },
        "radar_metrics": radar_metrics,
        "strengths_weaknesses": strengths,
        "warnings": comparison.get("warnings", []),
        "key_moments": {
            "player_a": player_a.get("key_moments", []),
            "player_b": player_b.get("key_moments", []) if player_b else [],
        },
        "context_summary": _context_summary(mode, comparison),
    }
    return to_jsonable(context)


def _build_individual_radar_metrics(player: dict[str, Any]) -> dict[str, Any]:
    raw = {
        "Ataque": _number(player.get("goals")) * 8 + _number(player.get("shots")) * 2 + _number(player.get("xg")) * 10,
        "Creación": _number(player.get("assists")) * 8 + _number(player.get("key_passes")) * 3,
        "Pase": _number(player.get("successful_passes")) * 0.35 + _number(player.get("pass_accuracy_pct")) * 0.65,
        "Progresión": _number(player.get("progressive_passes")) * 4 + _number(player.get("carries")) * 0.8,
        "Presión": _number(player.get("pressures")),
        "Duelos": _number(player.get("duels")),
        "Impacto": _number(player.get("impact_score")),
    }
    categories = list(raw.keys())
    values = [
        (
            0
            if INDIVIDUAL_RADAR_CAPS[category] <= 0
            else round(min(100, raw[category] / INDIVIDUAL_RADAR_CAPS[category] * 100), 1)
        )
        for category in categories
    ]
    return {
        "categories": categories,
        "player_a": {
            "name": player.get("player_name"),
            "team_name": player.get("team_name"),
            "values": values,
            "raw": raw,
        },
        "player_b": {
            "name": None,
            "team_name": None,
            "values": [0 for _ in categories],
            "raw": {category: 0 for category in categories},
        },
    }


def _individual_strengths_weaknesses(radar_metrics: dict[str, Any]) -> dict[str, Any]:
    categories = list(radar_metrics.get("categories", []))
    values = list(radar_metrics.get("player_a", {}).get("values", []))
    strengths = [category for category, value in zip(categories, values) if _number(value) >= 70]
    weaknesses = [category for category, value in zip(categories, values) if _number(value) <= 30]
    warnings = []
    if values and max(values) <= 35:
        warnings.append("El radar individual tiene valores bajos; puede haber poco dato observable para scouting.")
    if not strengths:
        warnings.append("No hay categorías individuales >= 70; conviene leer el perfil con cautela.")
    return {
        "player_a_strengths": strengths,
        "player_a_weaknesses": weaknesses,
        "player_b_strengths": [],
        "player_b_weaknesses": [],
        "warnings": warnings,
    }


def _context_summary(mode: str, comparison: dict[str, Any]) -> dict[str, Any]:
    player_a = comparison.get("player_a", {})
    player_b = comparison.get("player_b", {})
    return {
        "mode": mode,
        "player_a": player_a.get("player_name"),
        "team_a": player_a.get("team_name"),
        "match_a": comparison.get("match_a", {}).get("scoreline"),
        "player_b": player_b.get("player_name") if mode == "comparativo" else None,
        "team_b": player_b.get("team_name") if mode == "comparativo" else None,
        "match_b": comparison.get("match_b", {}).get("scoreline") if mode == "comparativo" else None,
        "warnings_count": len(comparison.get("warnings", [])),
    }


def _number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
