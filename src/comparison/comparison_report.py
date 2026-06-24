"""Render and persist match comparison reports."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.config import COMPARISONS_DIR, project_relative
from src.ingestion.utils import to_jsonable


def render_match_comparison_markdown(
    comparison: dict[str, Any],
    narrative: dict[str, Any] | None = None,
) -> str:
    match_a = comparison.get("match_a", {})
    match_b = comparison.get("match_b", {})
    summary = comparison.get("summary_comparison", {})
    dominance = comparison.get("dominance_comparison", {})
    impact = comparison.get("impact_players_comparison", {})
    lines = [
        "# Comparación de partidos",
        "",
        "## Partidos",
        "",
        f"- **Partido A:** `{match_a.get('match_id')}` | {match_a.get('scoreline')}",
        f"- **Partido B:** `{match_b.get('match_id')}` | {match_b.get('scoreline')}",
        "",
        "## Resumen de diferencias",
        "",
        "| Métrica | Partido A | Partido B | Diferencia B-A | Mayor |",
        "| --- | ---: | ---: | ---: | --- |",
        _metric_row("Goles", summary.get("goal_difference", {})),
        _metric_row("Tiros", summary.get("shot_difference", {})),
        _metric_row("xG", summary.get("xg_difference", {})),
        _metric_row("Pases", summary.get("pass_difference", {})),
        _metric_row("Ataques peligrosos", summary.get("dangerous_attack_difference", {})),
        "",
        "## Intensidad",
        "",
        f"- **Partido A:** {summary.get('intensity_a', {}).get('score')} ({summary.get('intensity_a', {}).get('label')})",
        f"- **Partido B:** {summary.get('intensity_b', {}).get('score')} ({summary.get('intensity_b', {}).get('label')})",
        f"- **Mayor intensidad:** {summary.get('more_intense_match')}",
        "",
        "## Dominio comparado",
        "",
        f"- **Partido A:** {dominance.get('leader_a', {}).get('team_name')} | score {dominance.get('leader_a', {}).get('dominance_score')}",
        f"- **Partido B:** {dominance.get('leader_b', {}).get('team_name')} | score {dominance.get('leader_b', {}).get('dominance_score')}",
        "",
        "## Jugadores determinantes",
        "",
        f"- **Partido A:** {impact.get('top_player_a', {}).get('player_name')} ({impact.get('top_player_a', {}).get('team_name')}) | impacto {impact.get('top_player_a', {}).get('impact_score')}",
        f"- **Partido B:** {impact.get('top_player_b', {}).get('player_name')} ({impact.get('top_player_b', {}).get('team_name')}) | impacto {impact.get('top_player_b', {}).get('impact_score')}",
        "",
    ]

    warnings = comparison.get("warnings", [])
    if warnings:
        lines.extend(["## Advertencias", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")

    if narrative:
        lines.extend(["## Narrativa comparativa", "", str(narrative.get("narrative_markdown") or ""), ""])

    return "\n".join(lines)


def save_match_comparison(
    comparison: dict[str, Any],
    narrative: dict[str, Any] | None = None,
) -> dict[str, str]:
    COMPARISONS_DIR.mkdir(parents=True, exist_ok=True)
    match_a = comparison.get("match_a", {}).get("match_id")
    match_b = comparison.get("match_b", {}).get("match_id")
    exported_at, suffix, paths = _build_paths(int(match_a), int(match_b))
    payload = {
        "comparison": comparison,
        "narrative": narrative,
        "exported_at": exported_at.isoformat(timespec="seconds"),
        "export_suffix": suffix,
    }
    with paths["json"].open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(payload), file, ensure_ascii=False, indent=2)
        file.write("\n")
    paths["markdown"].write_text(render_match_comparison_markdown(comparison, narrative), encoding="utf-8")
    return {
        "json": project_relative(paths["json"]),
        "markdown": project_relative(paths["markdown"]),
        "exported_at": exported_at.isoformat(timespec="seconds"),
        "export_suffix": suffix,
    }


def _metric_row(label: str, values: dict[str, Any]) -> str:
    return (
        f"| {label} | {values.get('match_a')} | {values.get('match_b')} | "
        f"{values.get('difference_b_minus_a')} | {values.get('higher_match')} |"
    )


def _build_paths(match_a: int, match_b: int) -> tuple[datetime, str, dict[str, Path]]:
    exported_at = datetime.now()
    while True:
        suffix = exported_at.strftime("%Y%m%d_%H%M%S")
        base_name = f"comparison.match-{match_a}_vs_{match_b}_{suffix}"
        paths = {
            "json": COMPARISONS_DIR / f"{base_name}.json",
            "markdown": COMPARISONS_DIR / f"{base_name}.md",
        }
        if not any(path.exists() for path in paths.values()):
            return exported_at, suffix, paths
        exported_at += timedelta(seconds=1)

