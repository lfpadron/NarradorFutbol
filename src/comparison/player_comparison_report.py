"""Render and persist player comparison reports."""

from __future__ import annotations

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from src.config import COMPARISONS_DIR, project_relative
from src.ingestion.utils import to_jsonable


def render_player_comparison_markdown(
    comparison: dict[str, Any],
    narrative: dict[str, Any] | None = None,
) -> str:
    player_a = comparison.get("player_a", {})
    player_b = comparison.get("player_b", {})
    match_a = comparison.get("match_a", {})
    match_b = comparison.get("match_b", {})
    summary = comparison.get("summary_comparison", {})
    lines = [
        "# Comparación de jugadores",
        "",
        "## Jugadores",
        "",
        f"- **Jugador A:** `{player_a.get('player_id')}` | {player_a.get('player_name')} ({player_a.get('team_name')}) | {match_a.get('scoreline')}",
        f"- **Jugador B:** `{player_b.get('player_id')}` | {player_b.get('player_name')} ({player_b.get('team_name')}) | {match_b.get('scoreline')}",
        "",
        "## Diferencias principales",
        "",
        "| Métrica | Diferencia B-A |",
        "| --- | ---: |",
        f"| Goles | {summary.get('diff_goals')} |",
        f"| xG | {summary.get('diff_xg')} |",
        f"| Tiros | {summary.get('diff_shots')} |",
        f"| Asistencias | {summary.get('diff_assists')} |",
        f"| Pases clave | {summary.get('diff_key_passes')} |",
        f"| Presiones | {summary.get('diff_pressures')} |",
        f"| Impact score | {summary.get('diff_impact_score')} |",
        "",
        "## Tabla comparativa",
        "",
        "| Métrica | Jugador A | Jugador B |",
        "| --- | ---: | ---: |",
    ]
    for label, key in (
        ("Eventos", "events"),
        ("Tiros", "shots"),
        ("Goles", "goals"),
        ("xG", "xg"),
        ("Asistencias", "assists"),
        ("Pases clave", "key_passes"),
        ("Pases", "passes"),
        ("Pases exitosos", "successful_passes"),
        ("Precisión pase", "pass_accuracy_pct"),
        ("Pases progresivos", "progressive_passes"),
        ("Carries", "carries"),
        ("Duelos", "duels"),
        ("Presiones", "pressures"),
        ("Faltas cometidas", "fouls_committed"),
        ("Faltas recibidas", "fouls_won"),
        ("Impact score", "impact_score"),
    ):
        lines.append(f"| {label} | {player_a.get(key)} | {player_b.get(key)} |")

    warnings = comparison.get("warnings", [])
    if warnings:
        lines.extend(["", "## Advertencias", ""])
        lines.extend(f"- {warning}" for warning in warnings)

    if narrative:
        lines.extend(["", "## Narrativa comparativa", "", str(narrative.get("narrative_markdown") or "")])

    lines.append("")
    return "\n".join(lines)


def save_player_comparison(
    comparison: dict[str, Any],
    narrative: dict[str, Any] | None = None,
) -> dict[str, str]:
    COMPARISONS_DIR.mkdir(parents=True, exist_ok=True)
    player_a = comparison.get("player_a", {})
    player_b = comparison.get("player_b", {})
    exported_at, suffix, paths = _build_paths(
        int(player_a["match_id"]),
        int(player_a["player_id"]),
        int(player_b["match_id"]),
        int(player_b["player_id"]),
    )
    payload = {
        "comparison": comparison,
        "narrative": narrative,
        "exported_at": exported_at.isoformat(timespec="seconds"),
        "export_suffix": suffix,
    }
    with paths["json"].open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(payload), file, ensure_ascii=False, indent=2)
        file.write("\n")
    paths["markdown"].write_text(render_player_comparison_markdown(comparison, narrative), encoding="utf-8")
    return {
        "json": project_relative(paths["json"]),
        "markdown": project_relative(paths["markdown"]),
        "exported_at": exported_at.isoformat(timespec="seconds"),
        "export_suffix": suffix,
    }


def _build_paths(
    match_a: int,
    player_a: int,
    match_b: int,
    player_b: int,
) -> tuple[datetime, str, dict[str, Path]]:
    exported_at = datetime.now()
    while True:
        suffix = exported_at.strftime("%Y%m%d_%H%M%S")
        base_name = f"player_comparison.match-{match_a}.{player_a}_vs_match-{match_b}.{player_b}_{suffix}"
        paths = {
            "json": COMPARISONS_DIR / f"{base_name}.json",
            "markdown": COMPARISONS_DIR / f"{base_name}.md",
        }
        if not any(path.exists() for path in paths.values()):
            return exported_at, suffix, paths
        exported_at += timedelta(seconds=1)

