"""Narrative regression helpers for benchmark cases."""

from __future__ import annotations

from typing import Any

from src.analytics.ai_context import build_ai_match_context
from src.narrative.fact_guard import validate_narrative_against_context
from src.narrative.narrator import generate_match_narrative
from src.narrative.quality_checker import evaluate_narrative_quality
from src.narrative_v2.narrator_v2 import compare_specialized_styles


def run_basic_narrative_regression(match_id: int, use_api: bool = False) -> dict[str, Any]:
    context = build_ai_match_context(match_id)
    result = generate_match_narrative(match_id, use_api=use_api)
    narrative = str(result.get("narrative_markdown") or "")
    fact_warnings = validate_narrative_against_context(narrative, context)
    quality = evaluate_narrative_quality(narrative, context)
    return {
        "status": result.get("status"),
        "model": result.get("model"),
        "warnings": result.get("warnings", []),
        "fact_warnings": fact_warnings,
        "quality": quality,
        "narrative_markdown": narrative,
    }


def run_v2_narrative_regression(match_id: int, use_api: bool = False) -> dict[str, Any]:
    comparison = compare_specialized_styles(match_id, use_api=use_api)
    styles = comparison.get("styles", [])
    fact_warnings_count = sum(int(row.get("fact_warnings_count") or 0) for row in styles)
    min_score = min((int(row.get("style_score") or 0) for row in styles), default=0)
    return {
        "status": "generated",
        "best_style": comparison.get("best_style"),
        "fact_warnings_count": fact_warnings_count,
        "min_style_score": min_score,
        "comparison": comparison,
    }
