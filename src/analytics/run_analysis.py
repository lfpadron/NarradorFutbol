"""CLI runner for match analytics."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from src.analytics.ai_context import build_ai_match_context
from src.analytics.db import AnalyticsDatabaseError, query_records
from src.config import ANALYTICS_EXPORTS_DIR, ensure_directories
from src.ingestion.utils import to_jsonable


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run analytical football metrics for a transformed match.")
    parser.add_argument("--match-id", type=int, default=None, help="Transformed match_id to analyze.")
    parser.add_argument("--export-json", action="store_true", help="Export analysis to data/analytics/exports.")
    parser.add_argument("--list-matches", action="store_true", help="List transformed matches available for analysis.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_directories()

    try:
        if args.list_matches:
            print_matches()
            return

        if args.match_id is None:
            raise SystemExit("Use --match-id <MATCH_ID> or --list-matches.")

        context = build_ai_match_context(args.match_id)
        print_context(context)

        if args.export_json:
            path = export_context(args.match_id, context)
            print(f"\nJSON export: {path.as_posix()}")
    except (AnalyticsDatabaseError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc


def print_matches() -> None:
    rows = query_records(
        """
        SELECT
            match_id,
            match_date,
            home_team_name,
            away_team_name,
            home_score,
            away_score,
            total_events,
            total_shots,
            total_goals
        FROM vw_match_summary
        WHERE total_events > 0
        ORDER BY match_date, match_id
        """
    )
    if not rows:
        print("No transformed matches found. Run `uv run python -m src.transform.build_duckdb --limit 3 --force`.")
        return

    print("Transformed matches:")
    for row in rows:
        print(
            f"- {row['match_id']} | {row.get('match_date')} | "
            f"{row.get('home_team_name')} {row.get('home_score')}-{row.get('away_score')} "
            f"{row.get('away_team_name')} | events={row.get('total_events')} "
            f"shots={row.get('total_shots')} goals={row.get('total_goals')}"
        )


def print_context(context: dict[str, Any]) -> None:
    summary = context["match_summary"]
    print("Match summary")
    print(
        f"{summary.get('home_team_name')} {summary.get('home_score')}-"
        f"{summary.get('away_score')} {summary.get('away_team_name')}"
    )
    print(
        f"match_id={summary.get('match_id')} | {summary.get('match_date')} | "
        f"{summary.get('result_label')} | events={summary.get('total_events')} | "
        f"shots={summary.get('total_shots')} | goals={summary.get('total_goals')} | "
        f"xG={float(summary.get('total_xg') or 0):.2f}"
    )

    print("\nTeam stats")
    for team in context["team_stats"]:
        print(
            f"- {team.get('team_name')}: shots={team.get('shots')}, goals={team.get('goals')}, "
            f"xG={float(team.get('xg') or 0):.2f}, passes={team.get('passes')} "
            f"({team.get('pass_completion_pct')}%), pressures={team.get('pressures')}"
        )

    shot_summary = context["shot_summary"]
    print("\nShot summary")
    print(
        f"shots={shot_summary.get('total_shots')} | goals={shot_summary.get('total_goals')} | "
        f"xG={float(shot_summary.get('total_xg') or 0):.2f}"
    )
    best_chance = shot_summary.get("best_chance")
    if best_chance:
        print(
            f"Best chance: {best_chance.get('player_name')} ({best_chance.get('team_name')}) "
            f"xG={float(best_chance.get('shot_statsbomb_xg') or 0):.2f}, "
            f"outcome={best_chance.get('shot_outcome_name')}"
        )

    pass_summary = context["pass_summary"]
    print("\nPass summary")
    print(
        f"passes={pass_summary.get('total_passes')} | successful={pass_summary.get('successful_passes')} | "
        f"completion={pass_summary.get('pass_completion_pct')}% | assists={pass_summary.get('assists')} | "
        f"key_passes={pass_summary.get('key_passes')}"
    )

    print("\nTop players")
    for player in context["top_players"]:
        print(
            f"- {player.get('player_name')} ({player.get('team_name')}): "
            f"score={player.get('impact_score')}, goals={player.get('goals')}, "
            f"assists={player.get('assists')}, shots={player.get('shots')}, "
            f"pressures={player.get('pressures')}"
        )

    print("\nDominance / Dominio")
    for team in context.get("dominance", []):
        print(
            f"- {team.get('team_name')}: score={team.get('dominance_score')}, "
            f"shots={team.get('shots')}, xG={float(team.get('xg') or 0):.2f}, "
            f"final_third_entries={team.get('final_third_entries')}, "
            f"progressive_passes={team.get('progressive_passes')}"
        )

    print("\nxG breakdown")
    for team in context.get("xg_breakdown", []):
        print(
            f"- {team.get('team_name')}: shots={team.get('shots')}, goals={team.get('goals')}, "
            f"xG={float(team.get('xg_total') or 0):.2f}, "
            f"best_chance={float(team.get('best_chance') or 0):.2f} "
            f"at minute {team.get('best_chance_minute')}"
        )

    dangerous_attacks = context.get("dangerous_attacks", [])
    print(f"\nDangerous attacks / Ataques peligrosos: {len(dangerous_attacks)}")
    for attack in dangerous_attacks[:10]:
        print(
            f"- possession={attack.get('possession')} | {attack.get('team_name')} | "
            f"{attack.get('start_minute')}-{attack.get('end_minute')} min | "
            f"xG={float(attack.get('xg') or 0):.2f} | shot={attack.get('has_shot')} | "
            f"goal={attack.get('has_goal')}"
        )

    print("\nImpact players / Jugadores de impacto")
    for player in context.get("impact_players", []):
        print(
            f"- {player.get('player_name')} ({player.get('team_name')}): "
            f"score={player.get('impact_score')}, goals={player.get('goals')}, "
            f"assists={player.get('assists')}, key_passes={player.get('key_passes')}, "
            f"progressive_passes={player.get('progressive_passes')}"
        )

    validation = context.get("validation", {})
    print(f"\nValidation / Validacion: {validation.get('status')}")
    findings = validation.get("findings", [])
    if not findings:
        print("- No validation findings.")
    for finding in findings:
        print(
            f"- [{finding.get('severity')}] {finding.get('code')}: "
            f"{finding.get('message')} rows={finding.get('rows')}"
        )

    comparison = context.get("reference_comparison", {})
    target = comparison.get("target", {})
    print("\nReference comparison / Comparacion con referencia")
    print(
        f"- winner={target.get('winner')} | dominance={target.get('estimated_dominance')} | "
        f"home_xG={target.get('home_xg')} | away_xG={target.get('away_xg')} | "
        f"home_shots={target.get('home_shots')} | away_shots={target.get('away_shots')}"
    )
    influential = target.get("most_influential_player")
    if influential:
        print(
            f"- most_influential_player={influential.get('player_name')} "
            f"({influential.get('team_name')}) score={influential.get('impact_score')}"
        )

    print("\nKey moments")
    key_moments = context["key_moments"][:12]
    if not key_moments:
        print("- No key moments detected.")
    for moment in key_moments:
        print(
            f"- {moment.get('minute')}:{int(moment.get('second') or 0):02d} "
            f"[{moment.get('type')}] {moment.get('title')} "
            f"(importance={moment.get('importance_score')})"
        )


def export_context(match_id: int, context: dict[str, Any]) -> Path:
    ANALYTICS_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    path = ANALYTICS_EXPORTS_DIR / f"analysis.match-{match_id}.json"
    with path.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(context), file, ensure_ascii=False, indent=2)
        file.write("\n")
    return path


if __name__ == "__main__":
    main()
