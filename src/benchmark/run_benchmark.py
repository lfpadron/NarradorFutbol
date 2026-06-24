"""CLI runner for football benchmarks."""

from __future__ import annotations

import argparse

from src.analytics.db import AnalyticsDatabaseError
from src.benchmark.benchmark_report import save_benchmark_result
from src.benchmark.benchmark_runner import run_all_benchmarks, run_selected_benchmark
from src.benchmark.generic_report import save_generic_validation_result
from src.benchmark.generic_validation import validate_any_match


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Ejecuta benchmark curado o validación genérica.")
    parser.add_argument("--case", help="ID del caso de benchmark curado.")
    parser.add_argument("--match-id", type=int, help="Match ID transformado para validación genérica.")
    parser.add_argument("--generic", action="store_true", help="Ejecuta validación genérica para cualquier partido.")
    parser.add_argument("--save", action="store_true", help="Guarda reportes JSON y Markdown.")
    parser.add_argument("--use-api", action="store_true", help="Usa OpenAI API para regresión narrativa.")
    args = parser.parse_args()
    if args.generic and args.case:
        parser.error("No mezcles --case con --generic.")
    if args.generic and args.match_id is None:
        parser.error("--generic requiere --match-id.")
    if args.match_id is not None and not args.generic:
        parser.error("Usa --generic junto con --match-id para validación genérica.")
    return args


def main() -> None:
    args = parse_args()
    try:
        if args.generic:
            result = validate_any_match(int(args.match_id), use_api=args.use_api)
            print_generic_result(result)
            if args.save:
                paths = save_generic_validation_result(result)
                print("\nRutas guardadas")
                print(f"- markdown: {paths['markdown']}")
                print(f"- json: {paths['json']}")
            return

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
    print("Benchmark futbolístico y regresión narrativa")
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


def print_generic_result(result: dict) -> None:
    summary = result.get("summary", {})
    checks = result.get("checks", [])
    passed = sum(1 for check in checks if check.get("status") == "PASS")
    warnings = sum(1 for check in checks if check.get("status") == "WARNING")
    failed = sum(1 for check in checks if check.get("status") == "FAIL")
    print("Validación genérica de partido")
    print(
        f"match_id={result.get('match_id')} | status={result.get('status')} | "
        f"pass={passed} | warning={warnings} | fail={failed}"
    )
    print(
        f"partido={summary.get('home_team')} {summary.get('home_score')}-"
        f"{summary.get('away_score')} {summary.get('away_team')}"
    )
    for check in checks:
        print(f"- {check.get('status')} {check.get('check_name')}: {check.get('message')}")


if __name__ == "__main__":
    main()
