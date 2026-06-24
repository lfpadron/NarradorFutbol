"""CLI runner for Narrador AI v2."""

from __future__ import annotations

import argparse

from src.analytics.db import AnalyticsDatabaseError
from src.narrative_v2.narrator_v2 import (
    compare_specialized_styles,
    generate_specialized_narrative,
    save_specialized_narrative,
    save_style_comparison,
)
from src.narrative_v2.style_profiles import STYLE_PROFILES


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate specialized Narrador AI v2 narratives.")
    parser.add_argument("--match-id", type=int, required=True, help="Transformed match_id to narrate.")
    parser.add_argument(
        "--style",
        choices=sorted(STYLE_PROFILES),
        default="tactico",
        help="Specialized narrative style.",
    )
    parser.add_argument("--compare", action="store_true", help="Generate and compare all styles.")
    parser.add_argument("--save", action="store_true", help="Save Markdown and JSON outputs.")
    parser.add_argument("--no-api", action="store_true", help="Force local fallback without OpenAI API.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        if args.compare:
            comparison = compare_specialized_styles(args.match_id, use_api=not args.no_api)
            print_comparison(comparison)
            if args.save:
                json_path = save_style_comparison(comparison)
                print(f"\nComparison JSON saved: {json_path}")
            return

        result = generate_specialized_narrative(args.match_id, args.style, use_api=not args.no_api)
    except (AnalyticsDatabaseError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    print_single_result(result)
    if args.save:
        md_path, json_path = save_specialized_narrative(result)
        print(f"\nMarkdown saved: {md_path}")
        print(f"JSON saved: {json_path}")


def print_single_result(result: dict) -> None:
    quality = result.get("style_quality", {})
    print("Narrador AI v2")
    print(
        f"match_id={result.get('match_id')} | style={result.get('style_id')} | "
        f"status={result.get('status')} | score={quality.get('style_score')}"
    )
    print("\nFact warnings")
    fact_warnings = result.get("fact_warnings", [])
    if not fact_warnings:
        print("- none")
    for warning in fact_warnings:
        print(f"- {warning}")
    print("\nStyle quality")
    print(
        f"style={quality.get('style_score')} | structure={quality.get('structure_score')} | "
        f"audience={quality.get('audience_fit_score')} | factuality={quality.get('factuality_score')}"
    )
    print("\nNarrativa Markdown")
    print(result.get("narrative_markdown"))


def print_comparison(comparison: dict) -> None:
    print(f"Narrador AI v2 comparison for match_id={comparison.get('match_id')}")
    print("style | status | score | fact_warnings")
    for row in comparison.get("styles", []):
        print(
            f"{row.get('style_id')} | {row.get('status')} | "
            f"{row.get('style_score')} | {row.get('fact_warnings_count')}"
        )
    print(f"\nBest style: {comparison.get('best_style')}")


if __name__ == "__main__":
    main()
