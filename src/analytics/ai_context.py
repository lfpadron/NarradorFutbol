"""Consolidated analytical context for future AI narration."""

from __future__ import annotations

from typing import Any

from src.analytics.advanced_metrics import get_impact_players
from src.analytics.dangerous_attacks import get_dangerous_attacks
from src.analytics.dominance_analysis import get_dominance_intervals, get_match_dominance
from src.analytics.key_moments import get_key_moments
from src.analytics.match_summary import get_match_summary
from src.analytics.match_validation import compare_against_reference, validate_match
from src.analytics.momentum import get_momentum_by_interval
from src.analytics.pass_analysis import get_pass_summary
from src.analytics.player_stats import get_player_stats
from src.analytics.possession_analysis import get_possession_summary
from src.analytics.shot_analysis import get_shot_summary
from src.analytics.team_stats import get_team_stats
from src.analytics.xg_analysis import get_xg_breakdown
from src.ingestion.utils import to_jsonable


def build_ai_match_context(match_id: int) -> dict[str, Any]:
    player_stats = get_player_stats(match_id)
    context = {
        "match_summary": get_match_summary(match_id),
        "team_stats": get_team_stats(match_id),
        "player_stats": player_stats,
        "top_players": select_top_players(player_stats),
        "shot_summary": get_shot_summary(match_id),
        "pass_summary": get_pass_summary(match_id),
        "possession_summary": get_possession_summary(match_id),
        "momentum": get_momentum_by_interval(match_id),
        "key_moments": get_key_moments(match_id),
        "dominance": get_match_dominance(match_id),
        "dominance_intervals": get_dominance_intervals(match_id),
        "dangerous_attacks": get_dangerous_attacks(match_id),
        "impact_players": get_impact_players(match_id),
        "xg_breakdown": get_xg_breakdown(match_id),
        "validation": validate_match(match_id),
        "reference_comparison": compare_against_reference(match_id),
    }
    return to_jsonable(context)


def select_top_players(player_stats: list[dict[str, Any]], limit: int = 5) -> list[dict[str, Any]]:
    ranked = []
    for player in player_stats:
        score = (
            float(player.get("goals") or 0) * 5
            + float(player.get("assists") or 0) * 4
            + float(player.get("shots") or 0) * 1.5
            + float(player.get("xg") or 0) * 3
            + float(player.get("key_passes") or 0) * 2
            + float(player.get("pressures") or 0) * 0.5
        )
        enriched = dict(player)
        enriched["impact_score"] = round(score, 3)
        ranked.append(enriched)
    return sorted(
        ranked,
        key=lambda row: (
            float(row.get("impact_score") or 0),
            float(row.get("goals") or 0),
            float(row.get("assists") or 0),
        ),
        reverse=True,
    )[:limit]
