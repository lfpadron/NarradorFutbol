"""CLI runner for the AI narrator."""

from __future__ import annotations

import argparse

from src.analytics.ai_context import build_ai_match_context
from src.analytics.db import AnalyticsDatabaseError
from src.narrative.config import SUPPORTED_TONES
from src.narrative.narrative_store import save_narrative
from src.narrative.narrator import generate_match_narrative
from src.narrative.quality_checker import evaluate_narrative_quality
from src.narrative.review_report import build_review_report, save_review_report
from src.narrative.tone_comparison import compare_tones


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a curated football match narrative.")
    parser.add_argument("--match-id", type=int, required=True, help="Transformed match_id to narrate.")
    parser.add_argument(
        "--tone",
        choices=sorted(SUPPORTED_TONES),
        default="cronica_emocionante",
        help="Narrative tone.",
    )
    parser.add_argument("--no-api", action="store_true", help="Force local fallback without OpenAI API.")
    parser.add_argument("--save", action="store_true", help="Save Markdown and JSON narrative files.")
    parser.add_argument("--quality", action="store_true", help="Evaluate narrative quality with local heuristics.")
    parser.add_argument("--compare-tones", action="store_true", help="Compare all supported tones.")
    parser.add_argument("--review-save", action="store_true", help="Save a full narrative review report.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.review_save:
            report = build_review_report(args.match_id, use_api=not args.no_api)
            md_path, json_path = save_review_report(report)
            print_review_report(report)
            print(f"\nReview Markdown saved: {md_path}")
            print(f"Review JSON saved: {json_path}")
            return

        if args.compare_tones:
            comparison = compare_tones(args.match_id, tones=None, use_api=not args.no_api)
            print_tone_comparison(comparison)
            return

        result = generate_match_narrative(args.match_id, args.tone, use_api=not args.no_api)
        context = build_ai_match_context(args.match_id) if args.quality else None
    except (AnalyticsDatabaseError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    summary = result["context_summary"]
    print("Resumen del partido")
    print(
        f"{summary.get('home_team_name')} {summary.get('home_score')}-"
        f"{summary.get('away_score')} {summary.get('away_team_name')}"
    )
    print(f"status={result.get('status')} | tone={result.get('tone')} | model={result.get('model')}")

    warnings = result.get("warnings") or []
    print("\nWarnings")
    if not warnings:
        print("- none")
    for warning in warnings:
        print(f"- {warning}")

    if args.save:
        md_path, json_path = save_narrative(result)
        print(f"\nMarkdown saved: {md_path}")
        print(f"JSON saved: {json_path}")

    if args.quality and context is not None:
        quality = evaluate_narrative_quality(result["narrative_markdown"], context)
        print_quality(quality)

    print("\nNarrativa Markdown")
    print(result["narrative_markdown"])


def print_quality(quality: dict) -> None:
    print("\nQuality scores")
    print(
        f"overall={quality.get('overall_score')} | "
        f"factuality={quality.get('factuality_score')} | "
        f"coverage={quality.get('coverage_score')} | "
        f"clarity={quality.get('clarity_score')} | "
        f"excitement={quality.get('excitement_score')} | "
        f"tactical_depth={quality.get('tactical_depth_score')}"
    )
    print("\nDetected elements")
    for element in quality.get("detected_elements", []):
        print(f"- {element}")
    print("\nMissing elements")
    missing = quality.get("missing_elements", [])
    if not missing:
        print("- none")
    for element in missing:
        print(f"- {element}")
    print("\nQuality warnings")
    warnings = quality.get("warnings", [])
    if not warnings:
        print("- none")
    for warning in warnings:
        print(f"- {warning}")


def print_tone_comparison(comparison: dict) -> None:
    print(f"Tone comparison for match_id={comparison.get('match_id')}")
    print("tone | status | overall | factuality | coverage | clarity | " "excitement | tactical_depth | warnings")
    for row in comparison.get("tones", []):
        print(
            f"{row.get('tone')} | {row.get('status')} | {row.get('overall_score')} | "
            f"{row.get('factuality_score')} | {row.get('coverage_score')} | "
            f"{row.get('clarity_score')} | {row.get('excitement_score')} | "
            f"{row.get('tactical_depth_score')} | {len(row.get('warnings', []))}"
        )
        important_warnings = row.get("warnings", [])[:3]
        for warning in important_warnings:
            print(f"  - {warning}")
    print(f"\nBest tone: {comparison.get('best_tone')} ({comparison.get('best_tone_label')})")


def print_review_report(report: dict) -> None:
    summary = report.get("context_summary", {})
    print("Revisión narrativa del partido")
    print(
        f"{summary.get('home_team_name')} {summary.get('home_score')}-"
        f"{summary.get('away_score')} {summary.get('away_team_name')}"
    )
    comparison = report.get("tone_comparison", {})
    print(f"Best tone: {comparison.get('best_tone')} ({comparison.get('best_tone_label')})")
    print("\nRecomendaciones")
    for item in report.get("recommendations", []):
        print(f"- {item}")
    print("\nResumen por tono")
    for row in comparison.get("tones", []):
        print(f"- {row.get('tone')}: overall={row.get('overall_score')}, " f"warnings={len(row.get('warnings', []))}")


if __name__ == "__main__":
    main()
