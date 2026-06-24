"""CLI runner for match comparisons."""

from __future__ import annotations

import argparse

from src.comparison.comparison_narrative import generate_match_comparison_narrative
from src.comparison.comparison_report import save_match_comparison
from src.comparison.match_comparison import compare_matches


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Compara dos partidos transformados.")
    parser.add_argument("--match-a", type=int, required=True, help="Match ID del Partido A.")
    parser.add_argument("--match-b", type=int, required=True, help="Match ID del Partido B.")
    parser.add_argument("--narrative", action="store_true", help="Genera narrativa comparativa.")
    parser.add_argument("--save", action="store_true", help="Guarda comparación en JSON y Markdown.")
    parser.add_argument("--no-api", action="store_true", help="Desactiva OpenAI API para la narrativa.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    comparison = compare_matches(args.match_a, args.match_b)
    narrative = None
    if args.narrative:
        narrative = generate_match_comparison_narrative(
            args.match_a,
            args.match_b,
            use_api=not args.no_api,
        )

    print_comparison(comparison)
    if narrative:
        print("\nNarrativa comparativa")
        print(str(narrative.get("narrative_markdown") or ""))

    if args.save:
        paths = save_match_comparison(comparison, narrative)
        print("\nRutas guardadas")
        print(f"- markdown: {paths['markdown']}")
        print(f"- json: {paths['json']}")


def print_comparison(comparison: dict) -> None:
    match_a = comparison.get("match_a", {})
    match_b = comparison.get("match_b", {})
    summary = comparison.get("summary_comparison", {})
    dominance = comparison.get("dominance_comparison", {})
    impact = comparison.get("impact_players_comparison", {})

    print("Comparador de partidos")
    print(f"Partido A: {match_a.get('match_id')} | {match_a.get('scoreline')}")
    print(f"Partido B: {match_b.get('match_id')} | {match_b.get('scoreline')}")
    print("\nDiferencias principales")
    for label, key in (
        ("Goles", "goal_difference"),
        ("Tiros", "shot_difference"),
        ("xG", "xg_difference"),
        ("Pases", "pass_difference"),
        ("Ataques peligrosos", "dangerous_attack_difference"),
    ):
        values = summary.get(key, {})
        print(
            f"- {label}: A={values.get('match_a')} | B={values.get('match_b')} | "
            f"B-A={values.get('difference_b_minus_a')} | mayor={values.get('higher_match')}"
        )
    print(
        f"- Intensidad: A={summary.get('intensity_a', {}).get('score')} "
        f"({summary.get('intensity_a', {}).get('label')}) | "
        f"B={summary.get('intensity_b', {}).get('score')} "
        f"({summary.get('intensity_b', {}).get('label')}) | "
        f"mayor={summary.get('more_intense_match')}"
    )
    print("\nDominio")
    print(
        f"- A: {dominance.get('leader_a', {}).get('team_name')} "
        f"score={dominance.get('leader_a', {}).get('dominance_score')}"
    )
    print(
        f"- B: {dominance.get('leader_b', {}).get('team_name')} "
        f"score={dominance.get('leader_b', {}).get('dominance_score')}"
    )
    print("\nJugadores de impacto")
    print(
        f"- A: {impact.get('top_player_a', {}).get('player_name')} "
        f"({impact.get('top_player_a', {}).get('team_name')})"
    )
    print(
        f"- B: {impact.get('top_player_b', {}).get('player_name')} "
        f"({impact.get('top_player_b', {}).get('team_name')})"
    )
    warnings = comparison.get("warnings", [])
    if warnings:
        print("\nAdvertencias")
        for warning in warnings:
            print(f"- {warning}")


if __name__ == "__main__":
    main()
