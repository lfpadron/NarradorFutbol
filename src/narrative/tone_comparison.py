"""Compare narrative tones for one match."""

from __future__ import annotations

from typing import Any

from src.analytics.ai_context import build_ai_match_context
from src.ingestion.utils import to_jsonable
from src.narrative.config import SUPPORTED_TONES, validate_tone
from src.narrative.narrator import generate_match_narrative
from src.narrative.quality_checker import evaluate_narrative_quality


DEFAULT_COMPARISON_TONES = [
    "cronica_emocionante",
    "analisis_tecnico",
    "resumen_ejecutivo",
    "scouting",
    "television",
]


def compare_tones(match_id: int, tones: list[str] | None = None, use_api: bool = False) -> dict[str, Any]:
    selected_tones = tones or DEFAULT_COMPARISON_TONES
    for tone in selected_tones:
        validate_tone(tone)

    context = build_ai_match_context(match_id)
    rows: list[dict[str, Any]] = []
    for tone in selected_tones:
        result = generate_match_narrative(match_id, tone=tone, use_api=use_api)
        quality = evaluate_narrative_quality(result["narrative_markdown"], context)
        generation_warnings = list(result.get("warnings") or [])
        narrative_warnings = [
            warning for warning in generation_warnings if not _is_operational_warning(str(warning))
        ]
        narrative_warnings.extend(quality.get("warnings") or [])
        rows.append(
            {
                "tone": tone,
                "tone_label": SUPPORTED_TONES[tone],
                "status": result.get("status"),
                "overall_score": quality["overall_score"],
                "factuality_score": quality["factuality_score"],
                "coverage_score": quality["coverage_score"],
                "clarity_score": quality["clarity_score"],
                "excitement_score": quality["excitement_score"],
                "tactical_depth_score": quality["tactical_depth_score"],
                "warnings": narrative_warnings,
                "generation_warnings": generation_warnings,
                "missing_elements": quality.get("missing_elements", []),
                "detected_elements": quality.get("detected_elements", []),
                "narrative_markdown": result.get("narrative_markdown"),
            }
        )

    best = max(rows, key=lambda row: (row["overall_score"], -len(row["warnings"]))) if rows else None
    return to_jsonable(
        {
            "match_id": match_id,
            "tones": rows,
            "best_tone": best.get("tone") if best else None,
            "best_tone_label": best.get("tone_label") if best else None,
        }
    )


def _is_operational_warning(warning: str) -> bool:
    lowered = warning.lower()
    return "openai" in lowered or "api" in lowered or "fallback" in lowered or "narrativa local" in lowered
