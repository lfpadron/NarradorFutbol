"""CLI runner for final match reports."""

from __future__ import annotations

import argparse

from src.analytics.db import AnalyticsDatabaseError
from src.narrative.config import SUPPORTED_TONES
from src.reports.html_report import render_html_report
from src.reports.markdown_report import render_markdown_report
from src.reports.report_builder import build_match_report
from src.reports.report_store import save_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate final exportable match reports.")
    parser.add_argument("--match-id", type=int, required=True, help="Transformed match_id to report.")
    parser.add_argument(
        "--tone",
        choices=sorted(SUPPORTED_TONES),
        default="cronica_emocionante",
        help="Narrative tone.",
    )
    parser.add_argument("--no-api", action="store_true", help="Force local narrative fallback.")
    parser.add_argument("--save", action="store_true", help="Save Markdown, HTML and JSON files.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        report = build_match_report(args.match_id, tone=args.tone, use_api=not args.no_api)
    except (AnalyticsDatabaseError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    markdown_text = render_markdown_report(report)
    html_text = render_html_report(report)
    summary = report["match_summary"]
    print("Reporte del partido")
    print(
        f"{summary.get('home_team_name')} {summary.get('home_score')}-"
        f"{summary.get('away_score')} {summary.get('away_team_name')}"
    )
    print(f"match_id={report.get('match_id')} | tone={report.get('tone')}")

    warnings = report.get("warnings", [])
    print("\nWarnings")
    if not warnings:
        print("- none")
    for warning in warnings:
        print(f"- {warning}")

    if args.save:
        paths = save_report(report, markdown_text, html_text)
        print("\nRutas guardadas")
        for label, path in paths.items():
            print(f"- {label}: {path}")

    print("\nVista previa Markdown")
    preview = "\n".join(markdown_text.splitlines()[:60])
    print(preview)


if __name__ == "__main__":
    main()
