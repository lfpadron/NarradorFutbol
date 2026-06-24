"""Run benchmark cases and consolidate results."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.analytics.ai_context import build_ai_match_context
from src.benchmark.benchmark_cases import BENCHMARK_CASES, get_benchmark_case
from src.benchmark.benchmark_checks import (
    check_dominance,
    check_key_players,
    check_match_summary,
    check_narrative_claims,
)
from src.benchmark.narrative_regression import (
    run_basic_narrative_regression,
    run_v2_narrative_regression,
)
from src.ingestion.utils import to_jsonable


def run_benchmark_case(case: dict[str, Any], use_api: bool = False) -> dict[str, Any]:
    match_id = int(case["match_id"])
    context = build_ai_match_context(match_id)
    checks = [
        check_match_summary(case, context),
        check_dominance(case, context),
        check_key_players(case, context),
    ]

    basic_narrative = run_basic_narrative_regression(match_id, use_api=use_api)
    checks.append(check_narrative_claims(case, basic_narrative.get("narrative_markdown", "")))

    v2_narrative = run_v2_narrative_regression(match_id, use_api=use_api)
    checks.extend(_narrative_health_checks(basic_narrative, v2_narrative))

    return to_jsonable(
        {
            "case_id": case["case_id"],
            "match_id": match_id,
            "mode": "curated_benchmark",
            "label": case["label"],
            "status": _overall_status(checks),
            "checks": checks,
            "basic_narrative": _summarize_basic_narrative(basic_narrative),
            "v2_narrative": _summarize_v2_narrative(v2_narrative),
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }
    )


def run_all_benchmarks(use_api: bool = False) -> dict[str, Any]:
    cases = [run_benchmark_case(case, use_api=use_api) for case in BENCHMARK_CASES]
    return to_jsonable(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "use_api": use_api,
            "mode": "curated_benchmark",
            "status": _overall_status_from_cases(cases),
            "cases": cases,
            "summary": _summary(cases),
        }
    )


def run_selected_benchmark(case_id: str, use_api: bool = False) -> dict[str, Any]:
    case = get_benchmark_case(case_id)
    result = run_benchmark_case(case, use_api=use_api)
    return to_jsonable(
        {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "use_api": use_api,
            "mode": "curated_benchmark",
            "status": result["status"],
            "cases": [result],
            "summary": _summary([result]),
        }
    )


def _narrative_health_checks(
    basic_narrative: dict[str, Any],
    v2_narrative: dict[str, Any],
) -> list[dict[str, Any]]:
    basic_quality = basic_narrative.get("quality", {})
    basic_fact_warnings = basic_narrative.get("fact_warnings", [])
    v2_fact_warnings_count = int(v2_narrative.get("fact_warnings_count") or 0)
    v2_min_score = int(v2_narrative.get("min_style_score") or 0)
    return [
        {
            "check_name": "basic_narrative_quality",
            "status": "PASS" if int(basic_quality.get("overall_score") or 0) >= 70 else "WARNING",
            "message": "Basic narrative quality is above threshold.",
            "details": {
                "overall_score": basic_quality.get("overall_score"),
                "warnings": basic_quality.get("warnings", []),
                "fact_warnings": basic_fact_warnings,
            },
        },
        {
            "check_name": "v2_narrative_regression",
            "status": "PASS" if v2_fact_warnings_count == 0 and v2_min_score >= 70 else "WARNING",
            "message": "Narrador AI v2 styles are fact-safe and above threshold.",
            "details": {
                "best_style": v2_narrative.get("best_style"),
                "fact_warnings_count": v2_fact_warnings_count,
                "min_style_score": v2_min_score,
            },
        },
    ]


def _summarize_basic_narrative(result: dict[str, Any]) -> dict[str, Any]:
    quality = result.get("quality", {})
    return {
        "status": result.get("status"),
        "model": result.get("model"),
        "warnings_count": len(result.get("warnings", [])),
        "fact_warnings_count": len(result.get("fact_warnings", [])),
        "quality_overall_score": quality.get("overall_score"),
        "quality_warnings": quality.get("warnings", []),
    }


def _summarize_v2_narrative(result: dict[str, Any]) -> dict[str, Any]:
    comparison = result.get("comparison", {})
    return {
        "status": result.get("status"),
        "best_style": result.get("best_style"),
        "fact_warnings_count": result.get("fact_warnings_count"),
        "min_style_score": result.get("min_style_score"),
        "styles": [
            {
                "style_id": row.get("style_id"),
                "style_name": row.get("style_name"),
                "status": row.get("status"),
                "style_score": row.get("style_score"),
                "fact_warnings_count": row.get("fact_warnings_count"),
            }
            for row in comparison.get("styles", [])
        ],
    }


def _overall_status(checks: list[dict[str, Any]]) -> str:
    statuses = {check["status"] for check in checks}
    if "FAIL" in statuses:
        return "FAIL"
    if "WARNING" in statuses:
        return "WARNING"
    return "PASS"


def _overall_status_from_cases(cases: list[dict[str, Any]]) -> str:
    statuses = {case["status"] for case in cases}
    if "FAIL" in statuses:
        return "FAIL"
    if "WARNING" in statuses:
        return "WARNING"
    return "PASS"


def _summary(cases: list[dict[str, Any]]) -> dict[str, int]:
    return {
        "total": len(cases),
        "pass": sum(1 for case in cases if case["status"] == "PASS"),
        "warning": sum(1 for case in cases if case["status"] == "WARNING"),
        "fail": sum(1 for case in cases if case["status"] == "FAIL"),
    }
