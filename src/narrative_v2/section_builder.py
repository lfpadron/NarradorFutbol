"""Build reduced AI context per specialized narrative style."""

from __future__ import annotations

from typing import Any

from src.ingestion.utils import to_jsonable
from src.narrative_v2.style_profiles import get_style_profile

STYLE_CONTEXT_KEYS = {
    "tactico": [
        "match_summary",
        "dominance",
        "momentum",
        "xg_breakdown",
        "team_stats",
        "dangerous_attacks",
        "key_moments",
        "validation",
    ],
    "television": [
        "match_summary",
        "key_moments",
        "impact_players",
        "shot_summary",
        "momentum",
        "validation",
    ],
    "periodistico": [
        "match_summary",
        "key_moments",
        "dominance",
        "impact_players",
        "shot_summary",
        "validation",
    ],
    "scouting": [
        "match_summary",
        "impact_players",
        "top_players",
        "player_stats",
        "key_moments",
        "validation",
    ],
    "ejecutivo": [
        "match_summary",
        "dominance",
        "xg_breakdown",
        "team_stats",
        "key_moments",
        "validation",
        "reference_comparison",
    ],
}


LIST_LIMITS = {
    "dangerous_attacks": 18,
    "impact_players": 10,
    "key_moments": 16,
    "momentum": 24,
    "player_stats": 16,
    "top_players": 8,
}


def build_context_for_style(context: dict[str, Any], style_id: str) -> dict[str, Any]:
    profile = get_style_profile(style_id)
    keys = STYLE_CONTEXT_KEYS[style_id]
    reduced = {
        "style_profile": {
            "id": profile["id"],
            "name": profile["name"],
            "audience": profile["audience"],
            "objective": profile["objective"],
            "expected_sections": profile["expected_sections"],
        }
    }
    for key in keys:
        value = context.get(key)
        reduced[key] = _limit_value(key, value)
    return to_jsonable(reduced)


def _limit_value(key: str, value: Any) -> Any:
    if isinstance(value, list):
        limit = LIST_LIMITS.get(key)
        return value[:limit] if limit else value
    return value
