"""Generic narrative checks for any transformed match."""

from __future__ import annotations

from typing import Any

from src.analytics.ai_context import build_ai_match_context
from src.narrative.fact_guard import validate_narrative_against_context
from src.narrative.narrator import generate_match_narrative
from src.narrative.quality_checker import evaluate_narrative_quality
from src.narrative_v2.narrator_v2 import compare_specialized_styles


def validate_narratives_for_any_match(match_id: int, use_api: bool = False) -> dict[str, Any]:
    context = build_ai_match_context(match_id)
    basic_result = generate_match_narrative(match_id, use_api=use_api)
    basic_text = str(basic_result.get("narrative_markdown") or "")
    basic_fact_warnings = validate_narrative_against_context(basic_text, context)
    basic_quality = evaluate_narrative_quality(basic_text, context)

    v2_comparison = compare_specialized_styles(match_id, use_api=use_api)
    v2_styles = v2_comparison.get("styles", [])
    v2_fact_warnings_total = sum(int(row.get("fact_warnings_count") or 0) for row in v2_styles)

    return {
        "basic": {
            "status": basic_result.get("status"),
            "fact_warnings": basic_fact_warnings,
            "quality": basic_quality,
        },
        "v2": {
            "status": "generated",
            "styles_checked": len(v2_styles),
            "fact_warnings_total": v2_fact_warnings_total,
            "best_style": v2_comparison.get("best_style"),
            "styles": [
                {
                    "style_id": row.get("style_id"),
                    "style_name": row.get("style_name"),
                    "style_score": row.get("style_score"),
                    "fact_warnings_count": row.get("fact_warnings_count"),
                }
                for row in v2_styles
            ],
        },
    }
