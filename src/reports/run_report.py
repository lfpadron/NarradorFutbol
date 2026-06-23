"""CLI runner for final match reports."""

from __future__ import annotations

import argparse

from src.analytics.db import AnalyticsDatabaseError
from src.narrative.config import SUPPORTED_TONES
from src.reports.html_report import render_html_report
from src.reports.markdown_report import render_markdown_report
from src.reports.report_builder import build_match_report
from src.reports.report_history import (
    build_history_record,
    get_report_history_for_match,
    list_report_history,
    record_report_generation,
)
from src.reports.report_store import save_report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate final exportable match reports.")
    parser.add_argument("--match-id", type=int, default=None, help="Transformed match_id to report.")
    parser.add_argument(
        "--tone",
        choices=sorted(SUPPORTED_TONES),
        default="cronica_emocionante",
        help="Narrative tone.",
    )
    parser.add_argument("--no-api", action="store_true", help="Force local narrative fallback.")
    parser.add_argument("--save", action="store_true", help="Save Markdown, HTML and JSON files.")
    parser.add_argument("--pdf", action="store_true", help="Generate PDF when saving.")
    parser.add_argument("--docx", action="store_true", help="Generate DOCX when saving.")
    parser.add_argument("--history", action="store_true", help="List report generation history.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.history:
        rows = get_report_history_for_match(args.match_id) if args.match_id else list_report_history()
        print_history(rows)
        return

    if args.match_id is None:
        raise SystemExit("Use --match-id <MATCH_ID> or --history.")

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
        paths = save_report(
            report,
            markdown_text,
            html_text,
            include_pdf=args.pdf,
            include_docx=args.docx,
        )
        record_report_generation(
            build_history_record(report, paths, use_api=not args.no_api)
        )
        print("\nRutas guardadas")
        for label in ("markdown", "html", "json", "pdf", "docx"):
            path = paths.get(label)
            if path:
                print(f"- {label}: {path}")
        print(f"- pdf_status: {paths.get('pdf_status')}")
        if paths.get("pdf_error_message"):
            print(f"  pdf_error: {paths.get('pdf_error_message')}")
        print(f"- docx_status: {paths.get('docx_status')}")
        if paths.get("docx_error_message"):
            print(f"  docx_error: {paths.get('docx_error_message')}")

    print("\nVista previa Markdown")
    preview = "\n".join(markdown_text.splitlines()[:60])
    print(preview)


def print_history(rows: list[dict]) -> None:
    if not rows:
        print("No report history found.")
        return
    print("Report history")
    print(
        "generated_at | match_id | tone | generated_by | status | "
        "pdf_status | docx_status | quality | markdown_path"
    )
    for row in rows:
        print(
            f"{row.get('generated_at')} | {row.get('match_id')} | {row.get('tone')} | "
            f"{row.get('generated_by')} | {row.get('status')} | {row.get('pdf_status')} | "
            f"{row.get('docx_status')} | {row.get('quality_overall_score')} | "
            f"{row.get('markdown_path')}"
        )


if __name__ == "__main__":
    main()
