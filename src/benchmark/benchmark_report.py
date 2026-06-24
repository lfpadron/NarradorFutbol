"""Render and persist benchmark reports."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from src.config import BENCHMARK_RESULTS_DIR, project_relative
from src.ingestion.utils import to_jsonable


def render_benchmark_markdown(result: dict[str, Any]) -> str:
    lines = [
        "# Benchmark del Narrador Inteligente de Futbol",
        "",
        "## Resumen",
        "",
        f"- **Status general:** {result.get('status')}",
        f"- **Casos ejecutados:** {result.get('summary', {}).get('total', 0)}",
        f"- **PASS:** {result.get('summary', {}).get('pass', 0)}",
        f"- **WARNING:** {result.get('summary', {}).get('warning', 0)}",
        f"- **FAIL:** {result.get('summary', {}).get('fail', 0)}",
        f"- **Generado:** {result.get('generated_at')}",
        "",
        "## Casos ejecutados",
        "",
    ]
    for case in result.get("cases", []):
        lines.extend(_render_case(case))
    lines.extend(
        [
            "## Conclusión",
            "",
            _conclusion(result),
            "",
        ]
    )
    return "\n".join(lines)


def save_benchmark_result(result: dict[str, Any]) -> dict[str, str]:
    BENCHMARK_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = BENCHMARK_RESULTS_DIR / f"benchmark_{suffix}.json"
    md_path = BENCHMARK_RESULTS_DIR / f"benchmark_{suffix}.md"
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(result), file, ensure_ascii=False, indent=2)
        file.write("\n")
    md_path.write_text(render_benchmark_markdown(result), encoding="utf-8")
    return {"json": project_relative(json_path), "markdown": project_relative(md_path)}


def _render_case(case: dict[str, Any]) -> list[str]:
    lines = [
        f"### {case.get('label')}",
        "",
        f"- **Case ID:** `{case.get('case_id')}`",
        f"- **Match ID:** `{case.get('match_id')}`",
        f"- **Status:** {case.get('status')}",
        "",
        "## Resultado por caso",
        "",
        f"- Narrativa básica: score {case.get('basic_narrative', {}).get('quality_overall_score')} | fact warnings {case.get('basic_narrative', {}).get('fact_warnings_count')}",
        f"- Narrativa v2: mejor estilo {case.get('v2_narrative', {}).get('best_style')} | fact warnings {case.get('v2_narrative', {}).get('fact_warnings_count')}",
        "",
        "## Checks",
        "",
    ]
    for check in case.get("checks", []):
        lines.append(f"- **{check.get('status')}** `{check.get('check_name')}`: {check.get('message')}")
    lines.extend(
        [
            "",
            "## Narrativa básica",
            "",
            f"- Status: {case.get('basic_narrative', {}).get('status')}",
            f"- Quality overall: {case.get('basic_narrative', {}).get('quality_overall_score')}",
            f"- Fact warnings: {case.get('basic_narrative', {}).get('fact_warnings_count')}",
            "",
            "## Narrativa v2",
            "",
            f"- Status: {case.get('v2_narrative', {}).get('status')}",
            f"- Mejor estilo: {case.get('v2_narrative', {}).get('best_style')}",
            f"- Min style score: {case.get('v2_narrative', {}).get('min_style_score')}",
            "",
            "## Advertencias",
            "",
        ]
    )
    warnings = _collect_warnings(case)
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- Sin advertencias críticas.")
    lines.append("")
    return lines


def _collect_warnings(case: dict[str, Any]) -> list[str]:
    warnings = []
    for check in case.get("checks", []):
        if check.get("status") != "PASS":
            warnings.append(f"{check.get('check_name')}: {check.get('message')}")
    warnings.extend(case.get("basic_narrative", {}).get("quality_warnings", []))
    return warnings


def _conclusion(result: dict[str, Any]) -> str:
    if result.get("status") == "PASS":
        return "El benchmark confirma consistencia factual, analítica y narrativa para los casos ejecutados."
    if result.get("status") == "WARNING":
        return "El benchmark es utilizable, pero dejó advertencias que conviene revisar antes de una demo."
    return "El benchmark detectó fallos que deben corregirse antes de usar el sistema como referencia."

