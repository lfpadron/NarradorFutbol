"""Build and persist narrative review reports."""

from __future__ import annotations

import json
from typing import Any

from src.analytics.ai_context import build_ai_match_context
from src.config import ANALYTICS_EXPORTS_DIR
from src.ingestion.utils import to_jsonable
from src.narrative.tone_comparison import compare_tones


def build_review_report(match_id: int, use_api: bool = False) -> dict[str, Any]:
    context = build_ai_match_context(match_id)
    summary = context.get("match_summary", {})
    comparison = compare_tones(match_id, tones=None, use_api=use_api)
    recommendations = _build_recommendations(comparison)
    return to_jsonable(
        {
            "match_id": match_id,
            "context_summary": {
                "home_team_name": summary.get("home_team_name"),
                "away_team_name": summary.get("away_team_name"),
                "home_score": summary.get("home_score"),
                "away_score": summary.get("away_score"),
                "winner_team_name": summary.get("winner_team_name"),
            },
            "tone_comparison": comparison,
            "best_tone": comparison.get("best_tone"),
            "best_tone_label": comparison.get("best_tone_label"),
            "recommendations": recommendations,
        }
    )


def save_review_report(report: dict[str, Any]) -> tuple[str, str]:
    ANALYTICS_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    match_id = report["match_id"]
    md_path = ANALYTICS_EXPORTS_DIR / f"review.match-{match_id}.md"
    json_path = ANALYTICS_EXPORTS_DIR / f"review.match-{match_id}.json"

    md_path.write_text(_report_to_markdown(report), encoding="utf-8")
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(report), file, ensure_ascii=False, indent=2)
        file.write("\n")
    return md_path.as_posix(), json_path.as_posix()


def _build_recommendations(comparison: dict[str, Any]) -> list[str]:
    tones = comparison.get("tones", [])
    best_tone = comparison.get("best_tone_label") or comparison.get("best_tone")
    recommendations = []
    if best_tone:
        recommendations.append(f"Usar el tono {best_tone} como base para publicación.")
    low_coverage = [row for row in tones if int(row.get("coverage_score") or 0) < 75]
    if low_coverage:
        recommendations.append("Reforzar cobertura de marcador, dominio, xG, jugadores y momentos clave.")
    factual_warnings = [
        warning for row in tones for warning in row.get("warnings", []) if "marcador" in warning.lower()
    ]
    if factual_warnings:
        recommendations.append("Revisar manualmente las advertencias factuales antes de publicar.")
    if not recommendations:
        recommendations.append("La narrativa es consistente para uso exploratorio y portafolio.")
    return recommendations


def _report_to_markdown(report: dict[str, Any]) -> str:
    summary = report.get("context_summary", {})
    tones = report.get("tone_comparison", {}).get("tones", [])
    warnings = sorted({warning for row in tones for warning in row.get("warnings", [])})
    lines = [
        "# Revisión narrativa del partido",
        "",
        "## Partido",
        "",
        (
            f"{summary.get('home_team_name')} {summary.get('home_score')}-"
            f"{summary.get('away_score')} {summary.get('away_team_name')}"
        ),
        "",
        "## Comparación de tonos",
        "",
        "| Tono | Status | Overall | Factualidad | Cobertura | Claridad | Emoción | Táctica |",
        "| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for row in tones:
        lines.append(
            f"| {row.get('tone_label') or row.get('tone')} | {row.get('status')} | "
            f"{row.get('overall_score')} | {row.get('factuality_score')} | "
            f"{row.get('coverage_score')} | {row.get('clarity_score')} | "
            f"{row.get('excitement_score')} | {row.get('tactical_depth_score')} |"
        )
    lines.extend(
        [
            "",
            "## Mejor tono sugerido",
            "",
            str(report.get("best_tone_label") or report.get("best_tone") or "N/D"),
            "",
            "## Advertencias factuales",
            "",
        ]
    )
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- Sin advertencias factuales relevantes.")
    lines.extend(["", "## Recomendaciones", ""])
    lines.extend(f"- {item}" for item in report.get("recommendations", []))
    lines.append("")
    return "\n".join(lines)
