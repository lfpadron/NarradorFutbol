"""Build and persist narrative review reports."""

from __future__ import annotations

import json
from typing import Any

from src.analytics.ai_context import build_ai_match_context
from src.config import ANALYTICS_EXPORTS_DIR
from src.ingestion.utils import to_jsonable
from src.narrative.tone_comparison import compare_tones
from src.ui.i18n import is_english


def build_review_report(match_id: int, use_api: bool = False, language: str = "es") -> dict[str, Any]:
    context = build_ai_match_context(match_id)
    summary = context.get("match_summary", {})
    comparison = compare_tones(match_id, tones=None, use_api=use_api, language=language)
    recommendations = _build_recommendations(comparison, language=language)
    return to_jsonable(
        {
            "match_id": match_id,
            "language": language,
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
    language = "en" if is_english(report.get("language")) else "es"
    md_path = ANALYTICS_EXPORTS_DIR / f"review.match-{match_id}.{language}.md"
    json_path = ANALYTICS_EXPORTS_DIR / f"review.match-{match_id}.{language}.json"

    md_path.write_text(_report_to_markdown(report), encoding="utf-8")
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(report), file, ensure_ascii=False, indent=2)
        file.write("\n")
    return md_path.as_posix(), json_path.as_posix()


def _build_recommendations(comparison: dict[str, Any], language: str = "es") -> list[str]:
    tones = comparison.get("tones", [])
    best_tone = comparison.get("best_tone_label") or comparison.get("best_tone")
    recommendations = []
    if best_tone:
        recommendations.append(
            f"Use {best_tone} as the publishing baseline."
            if is_english(language)
            else f"Usar el tono {best_tone} como base para publicación."
        )
    low_coverage = [row for row in tones if int(row.get("coverage_score") or 0) < 75]
    if low_coverage:
        recommendations.append(
            "Strengthen coverage of scoreline, dominance, xG, players, and key moments."
            if is_english(language)
            else "Reforzar cobertura de marcador, dominio, xG, jugadores y momentos clave."
        )
    factual_warnings = [
        warning for row in tones for warning in row.get("warnings", []) if "marcador" in warning.lower()
    ]
    if factual_warnings:
        recommendations.append(
            "Manually review factual warnings before publishing."
            if is_english(language)
            else "Revisar manualmente las advertencias factuales antes de publicar."
        )
    if not recommendations:
        recommendations.append(
            "The narrative is consistent for exploratory and portfolio use."
            if is_english(language)
            else "La narrativa es consistente para uso exploratorio y portafolio."
        )
    return recommendations


def _report_to_markdown(report: dict[str, Any]) -> str:
    summary = report.get("context_summary", {})
    tones = report.get("tone_comparison", {}).get("tones", [])
    warnings = sorted({warning for row in tones for warning in row.get("warnings", [])})
    english = is_english(report.get("language"))
    title = "Match Narrative Review" if english else "Revisión narrativa del partido"
    match_title = "Match" if english else "Partido"
    comparison_title = "Tone Comparison" if english else "Comparación de tonos"
    best_title = "Suggested Best Tone" if english else "Mejor tono sugerido"
    warning_title = "Factual Warnings" if english else "Advertencias factuales"
    recommendation_title = "Recommendations" if english else "Recomendaciones"
    lines = [
        f"# {title}",
        "",
        f"## {match_title}",
        "",
        (
            f"{summary.get('home_team_name')} {summary.get('home_score')}-"
            f"{summary.get('away_score')} {summary.get('away_team_name')}"
        ),
        "",
        f"## {comparison_title}",
        "",
        (
            "| Tone | Status | Overall | Factuality | Coverage | Clarity | Excitement | Tactics |"
            if english
            else "| Tono | Status | Overall | Factualidad | Cobertura | Claridad | Emoción | Táctica |"
        ),
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
            f"## {best_title}",
            "",
            str(report.get("best_tone_label") or report.get("best_tone") or "N/D"),
            "",
            f"## {warning_title}",
            "",
        ]
    )
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- No relevant factual warnings." if english else "- Sin advertencias factuales relevantes.")
    lines.extend(["", f"## {recommendation_title}", ""])
    lines.extend(f"- {item}" for item in report.get("recommendations", []))
    lines.append("")
    return "\n".join(lines)
