"""CLI runner for football benchmarks."""

from __future__ import annotations

import argparse

from src.analytics.db import AnalyticsDatabaseError
from src.benchmark.benchmark_report import save_benchmark_result
from src.benchmark.benchmark_runner import run_all_benchmarks, run_selected_benchmark


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run football benchmark and narrative regression checks.")
    parser.add_argument("--case", help="Benchmark case id to run.")
    parser.add_argument("--save", action="store_true", help="Save benchmark JSON and Markdown reports.")
    parser.add_argument("--use-api", action="store_true", help="Use OpenAI API for narrative regression.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    try:
        result = (
            run_selected_benchmark(args.case, use_api=args.use_api)
            if args.case
            else run_all_benchmarks(use_api=args.use_api)
        )
    except (AnalyticsDatabaseError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc

    print_result(result)
    if args.save:
        paths = save_benchmark_result(result)
        print("\nRutas guardadas")
        print(f"- markdown: {paths['markdown']}")
        print(f"- json: {paths['json']}")


def print_result(result: dict) -> None:
    summary = result.get("summary", {})
    print("Benchmark futbolistico y regresion narrativa")
    print(
        f"status={result.get('status')} | total={summary.get('total')} | "
        f"pass={summary.get('pass')} | warning={summary.get('warning')} | fail={summary.get('fail')}"
    )
    for case in result.get("cases", []):
        print(f"\nCase: {case.get('case_id')} | {case.get('status')} | {case.get('label')}")
        for check in case.get("checks", []):
            print(f"- {check.get('status')} {check.get('check_name')}: {check.get('message')}")
        basic = case.get("basic_narrative", {})
        v2 = case.get("v2_narrative", {})
        print(
            f"  basic_quality={basic.get('quality_overall_score')} | "
            f"basic_fact_warnings={basic.get('fact_warnings_count')} | "
            f"v2_best={v2.get('best_style')} | v2_fact_warnings={v2.get('fact_warnings_count')}"
        )


if __name__ == "__main__":
    main()
