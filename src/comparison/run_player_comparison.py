"""CLI runner for player comparisons."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta
from pathlib import Path

from src.comparison.player_comparison import build_player_radar_metrics, compare_players, list_players_for_match
from src.comparison.player_comparison_narrative import generate_player_comparison_narrative
from src.comparison.player_comparison_report import save_player_comparison
from src.comparison.player_visuals import plot_player_strengths_weaknesses
from src.config import COMPARISONS_DIR, project_relative
from src.ingestion.utils import to_jsonable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compara jugadores dentro o entre partidos.")
    parser.add_argument("--list-players", action="store_true", help="Lista jugadores disponibles para un partido.")
    parser.add_argument("--match-id", type=int, help="Match ID para listar jugadores.")
    parser.add_argument("--match-a", type=int, help="Match ID del Jugador A.")
    parser.add_argument("--player-a", type=int, help="Player ID del Jugador A.")
    parser.add_argument("--match-b", type=int, help="Match ID del Jugador B.")
    parser.add_argument("--player-b", type=int, help="Player ID del Jugador B.")
    parser.add_argument("--narrative", action="store_true", help="Genera narrativa comparativa.")
    parser.add_argument("--save", action="store_true", help="Guarda comparación en JSON y Markdown.")
    parser.add_argument(
        "--export-visual-data", action="store_true", help="Guarda datos visuales para radar y fortalezas."
    )
    parser.add_argument("--no-api", action="store_true", help="Desactiva OpenAI API para la narrativa.")
    args = parser.parse_args()

    if args.list_players:
        if args.match_id is None:
            parser.error("--list-players requiere --match-id.")
        return args

    required = {
        "--match-a": args.match_a,
        "--player-a": args.player_a,
        "--match-b": args.match_b,
        "--player-b": args.player_b,
    }
    missing = [name for name, value in required.items() if value is None]
    if missing:
        parser.error("Faltan argumentos: " + ", ".join(missing))
    return args


def main() -> None:
    args = parse_args()
    if args.list_players:
        print_players(args.match_id)
        return

    comparison = compare_players(args.match_a, args.player_a, args.match_b, args.player_b)
    narrative = None
    if args.narrative:
        narrative = generate_player_comparison_narrative(
            args.match_a,
            args.player_a,
            args.match_b,
            args.player_b,
            use_api=not args.no_api,
        )

    print_comparison(comparison)
    if narrative:
        print("\nNarrativa comparativa")
        print(str(narrative.get("narrative_markdown") or ""))

    if args.save:
        paths = save_player_comparison(comparison, narrative)
        print("\nRutas guardadas")
        print(f"- markdown: {paths['markdown']}")
        print(f"- json: {paths['json']}")

    if args.export_visual_data:
        visual_path = save_visual_data(comparison)
        print("\nDatos visuales guardados")
        print(f"- json: {visual_path}")


def print_players(match_id: int) -> None:
    rows = list_players_for_match(match_id)
    print(f"Jugadores disponibles para match_id={match_id}")
    for row in rows:
        print(
            f"- {row.get('player_id')} | {row.get('player_name')} | "
            f"{row.get('team_name')} | events={row.get('events')} | minutes={row.get('minutes')}"
        )


def print_comparison(comparison: dict) -> None:
    player_a = comparison.get("player_a", {})
    player_b = comparison.get("player_b", {})
    match_a = comparison.get("match_a", {})
    match_b = comparison.get("match_b", {})
    summary = comparison.get("summary_comparison", {})
    print("Comparador de jugadores")
    print(
        f"Jugador A: {player_a.get('player_id')} | {player_a.get('player_name')} "
        f"({player_a.get('team_name')}) | {match_a.get('scoreline')}"
    )
    print(
        f"Jugador B: {player_b.get('player_id')} | {player_b.get('player_name')} "
        f"({player_b.get('team_name')}) | {match_b.get('scoreline')}"
    )
    print("\nDiferencias principales B-A")
    for label, key in (
        ("Goles", "diff_goals"),
        ("xG", "diff_xg"),
        ("Tiros", "diff_shots"),
        ("Asistencias", "diff_assists"),
        ("Pases clave", "diff_key_passes"),
        ("Presiones", "diff_pressures"),
        ("Impact score", "diff_impact_score"),
    ):
        print(f"- {label}: {summary.get(key)}")
    warnings = comparison.get("warnings", [])
    if warnings:
        print("\nAdvertencias")
        for warning in warnings:
            print(f"- {warning}")


def save_visual_data(comparison: dict) -> str:
    radar_metrics = build_player_radar_metrics(comparison)
    strengths = plot_player_strengths_weaknesses(radar_metrics)
    player_a = comparison.get("player_a", {})
    player_b = comparison.get("player_b", {})
    exported_at, path = _visual_data_path(
        int(player_a["match_id"]),
        int(player_a["player_id"]),
        int(player_b["match_id"]),
        int(player_b["player_id"]),
    )
    payload = {
        "mode": "player_visual_data",
        "exported_at": exported_at.isoformat(timespec="seconds"),
        "radar_metrics": radar_metrics,
        "strengths_weaknesses": strengths,
    }
    with path.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(payload), file, ensure_ascii=False, indent=2)
        file.write("\n")
    return project_relative(path)


def _visual_data_path(match_a: int, player_a: int, match_b: int, player_b: int) -> tuple[datetime, Path]:
    COMPARISONS_DIR.mkdir(parents=True, exist_ok=True)
    exported_at = datetime.now()
    while True:
        suffix = exported_at.strftime("%Y%m%d_%H%M%S")
        path = (
            COMPARISONS_DIR
            / f"player_visual_data.match-{match_a}.{player_a}_vs_match-{match_b}.{player_b}_{suffix}.json"
        )
        if not path.exists():
            return exported_at, path
        exported_at += timedelta(seconds=1)


if __name__ == "__main__":
    main()
