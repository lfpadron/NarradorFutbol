"""Markdown and JSON persistence for generic validation results."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from src.config import BENCHMARK_RESULTS_DIR, project_relative
from src.ingestion.utils import to_jsonable


def render_generic_validation_markdown(result: dict[str, Any]) -> str:
    summary = result.get("summary", {})
    lines = [
        "# Validación genérica de partido",
        "",
        "## Partido",
        "",
        f"- **Match ID:** {result.get('match_id')}",
        f"- **Partido:** {summary.get('home_team')} {summary.get('home_score')}-{summary.get('away_score')} {summary.get('away_team')}",
        f"- **Eventos:** {summary.get('events')}",
        f"- **Tiros:** {summary.get('shots')}",
        f"- **Goles detectados:** {summary.get('goals_detected')}",
        f"- **xG total:** {summary.get('total_xg')}",
        "",
        "## Resultado general",
        "",
        f"- **Status:** {result.get('status')}",
        f"- **Generado:** {result.get('generated_at')}",
        "",
        "## Checks",
        "",
    ]
    for check in result.get("checks", []):
        lines.append(f"- **{check.get('status')}** `{check.get('check_name')}`: {check.get('message')}")
    basic = result.get("narrative_basic", {})
    v2 = result.get("narrative_v2", {})
    lines.extend(
        [
            "",
            "## Narrativa básica",
            "",
            f"- Status: {basic.get('status')}",
            f"- Fact warnings: {len(basic.get('fact_warnings', []))}",
            f"- Quality overall: {basic.get('quality', {}).get('overall_score')}",
            "",
            "## Narrativa v2",
            "",
            f"- Status: {v2.get('status')}",
            f"- Estilos revisados: {v2.get('styles_checked')}",
            f"- Fact warnings totales: {v2.get('fact_warnings_total')}",
            f"- Mejor estilo: {v2.get('best_style')}",
            "",
            "## Warnings",
            "",
        ]
    )
    warnings = result.get("warnings", [])
    if warnings:
        lines.extend(f"- {warning}" for warning in warnings)
    else:
        lines.append("- Sin advertencias.")
    lines.extend(["", "## Conclusión", "", _conclusion(result), ""])
    return "\n".join(lines)


def save_generic_validation_result(result: dict[str, Any]) -> dict[str, str]:
    BENCHMARK_RESULTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    match_id = result["match_id"]
    base_name = f"generic_validation.match-{match_id}_{suffix}"
    json_path = BENCHMARK_RESULTS_DIR / f"{base_name}.json"
    md_path = BENCHMARK_RESULTS_DIR / f"{base_name}.md"
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(result), file, ensure_ascii=False, indent=2)
        file.write("\n")
    md_path.write_text(render_generic_validation_markdown(result), encoding="utf-8")
    return {"json": project_relative(json_path), "markdown": project_relative(md_path)}


def _conclusion(result: dict[str, Any]) -> str:
    if result.get("status") == "PASS":
        return "La validación genérica confirma consistencia interna para este partido transformado."
    if result.get("status") == "WARNING":
        return "La validación genérica terminó con advertencias revisables; el partido sigue siendo útil para análisis."
    return "La validación genérica detectó fallas que deben corregirse antes de usar este partido en demos."

