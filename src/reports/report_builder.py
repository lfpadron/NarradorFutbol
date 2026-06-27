"""Build consolidated match reports."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.analytics.ai_context import build_ai_match_context
from src.analytics.db import query_one
from src.ingestion.utils import to_jsonable
from src.narrative.narrator import generate_match_narrative
from src.narrative.quality_checker import evaluate_narrative_quality


def build_match_report(
    match_id: int,
    tone: str = "cronica_emocionante",
    use_api: bool = False,
) -> dict[str, Any]:
    context = build_ai_match_context(match_id)
    narrative = generate_match_narrative(match_id, tone=tone, use_api=use_api)
    quality = evaluate_narrative_quality(narrative["narrative_markdown"], context)
    validation = context.get("validation", {})
    validation_warnings = [
        f"{finding.get('severity')}: {finding.get('message')}" for finding in validation.get("findings", [])
    ]
    warnings = list(narrative.get("warnings") or []) + list(quality.get("warnings") or []) + validation_warnings

    return to_jsonable(
        {
            "match_id": match_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "tone": tone,
            "match_summary": context.get("match_summary", {}),
            "match_metadata": _get_match_metadata(match_id),
            "analytics": {
                "team_stats": context.get("team_stats", []),
                "player_stats": context.get("player_stats", []),
                "shot_summary": context.get("shot_summary", {}),
                "pass_summary": context.get("pass_summary", {}),
                "possession_summary": context.get("possession_summary", {}),
                "momentum": context.get("momentum", []),
                "key_moments": context.get("key_moments", []),
                "dominance": context.get("dominance", []),
                "dangerous_attacks": context.get("dangerous_attacks", []),
                "impact_players": context.get("impact_players", []),
                "xg_breakdown": context.get("xg_breakdown", []),
                "validation": validation,
            },
            "narrative": narrative,
            "quality": quality,
            "warnings": warnings,
        }
    )


def _get_match_metadata(match_id: int) -> dict[str, Any]:
    row = query_one(
        """
        SELECT
            m.match_id,
            m.match_date,
            m.kick_off,
            m.stadium_name,
            m.referee_name,
            c.competition_name,
            c.country_name,
            s.season_name
        FROM match m
        LEFT JOIN competition c ON c.competition_id = m.competition_id
        LEFT JOIN season s
          ON s.competition_id = m.competition_id
         AND s.season_id = m.season_id
        WHERE m.match_id = ?
        """,
        (match_id,),
    )
    return row or {}
