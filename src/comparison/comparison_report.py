"""Render and persist match comparison reports."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.config import COMPARISONS_DIR, project_relative
from src.ingestion.utils import to_jsonable
from src.ui.i18n import is_english, translate_text


def render_match_comparison_markdown(
    comparison: dict[str, Any],
    narrative: dict[str, Any] | None = None,
) -> str:
    match_a = comparison.get("match_a", {})
    match_b = comparison.get("match_b", {})
    summary = comparison.get("summary_comparison", {})
    dominance = comparison.get("dominance_comparison", {})
    impact = comparison.get("impact_players_comparison", {})
    language = (narrative or {}).get("language")
    english = is_english(language)
    lines = [
        "# Match Comparison" if english else "# Comparación de partidos",
        "",
        "## Matches" if english else "## Partidos",
        "",
        f"- **{'Match A' if english else 'Partido A'}:** `{match_a.get('match_id')}` | {match_a.get('scoreline')}",
        f"- **{'Match B' if english else 'Partido B'}:** `{match_b.get('match_id')}` | {match_b.get('scoreline')}",
        "",
        "## Difference Summary" if english else "## Resumen de diferencias",
        "",
        (
            "| Metric | Match A | Match B | B-A difference | Higher |"
            if english
            else "| Métrica | Partido A | Partido B | Diferencia B-A | Mayor |"
        ),
        "| --- | ---: | ---: | ---: | --- |",
        _metric_row("Goles", summary.get("goal_difference", {}), language),
        _metric_row("Tiros", summary.get("shot_difference", {}), language),
        _metric_row("xG", summary.get("xg_difference", {}), language),
        _metric_row("Pases", summary.get("pass_difference", {}), language),
        _metric_row("Ataques peligrosos", summary.get("dangerous_attack_difference", {}), language),
        "",
        "## Intensity" if english else "## Intensidad",
        "",
        f"- **{'Match A' if english else 'Partido A'}:** {summary.get('intensity_a', {}).get('score')} ({translate_text(summary.get('intensity_a', {}).get('label'), language=language)})",
        f"- **{'Match B' if english else 'Partido B'}:** {summary.get('intensity_b', {}).get('score')} ({translate_text(summary.get('intensity_b', {}).get('label'), language=language)})",
        f"- **{'Higher intensity' if english else 'Mayor intensidad'}:** {summary.get('more_intense_match')}",
        "",
        "## Compared Dominance" if english else "## Dominio comparado",
        "",
        f"- **{'Match A' if english else 'Partido A'}:** {dominance.get('leader_a', {}).get('team_name')} | score {dominance.get('leader_a', {}).get('dominance_score')}",
        f"- **{'Match B' if english else 'Partido B'}:** {dominance.get('leader_b', {}).get('team_name')} | score {dominance.get('leader_b', {}).get('dominance_score')}",
        "",
        "## Decisive Players" if english else "## Jugadores determinantes",
        "",
        f"- **{'Match A' if english else 'Partido A'}:** {impact.get('top_player_a', {}).get('player_name')} ({impact.get('top_player_a', {}).get('team_name')}) | {'impact' if english else 'impacto'} {impact.get('top_player_a', {}).get('impact_score')}",
        f"- **{'Match B' if english else 'Partido B'}:** {impact.get('top_player_b', {}).get('player_name')} ({impact.get('top_player_b', {}).get('team_name')}) | {'impact' if english else 'impacto'} {impact.get('top_player_b', {}).get('impact_score')}",
        "",
    ]

    warnings = comparison.get("warnings", [])
    if warnings:
        lines.extend(["## Warnings" if english else "## Advertencias", ""])
        lines.extend(f"- {warning}" for warning in warnings)
        lines.append("")

    if narrative:
        lines.extend(
            [
                "## Comparative Narrative" if english else "## Narrativa comparativa",
                "",
                str(narrative.get("narrative_markdown") or ""),
                "",
            ]
        )

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


def _metric_row(label: str, values: dict[str, Any], language: object | None = None) -> str:
    return (
        f"| {translate_text(label, language=language)} | {values.get('match_a')} | {values.get('match_b')} | "
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
