"""Shot-level analytics."""

from __future__ import annotations

from typing import Any

from src.analytics.db import query_records


def get_shots(match_id: int) -> list[dict[str, Any]]:
    return query_records(
        """
        SELECT
            event_id,
            minute,
            second,
            team_name,
            player_name,
            location_x,
            location_y,
            shot_statsbomb_xg,
            shot_outcome_name,
            shot_body_part_name,
            shot_type_name,
            shot_technique_name
        FROM vw_shots
        WHERE match_id = ?
        ORDER BY minute, second, event_index
        """,
        (match_id,),
    )


def get_shot_summary(match_id: int) -> dict[str, Any]:
    shots = get_shots(match_id)
    total_shots = len(shots)
    total_goals = sum(1 for shot in shots if shot.get("shot_outcome_name") == "Goal")
    total_xg = sum(float(shot.get("shot_statsbomb_xg") or 0) for shot in shots)
    best_chance = max(shots, key=lambda shot: float(shot.get("shot_statsbomb_xg") or 0), default=None)

    shots_by_team: dict[str, int] = {}
    goals_by_team: dict[str, int] = {}
    xg_by_team: dict[str, float] = {}
    for shot in shots:
        team_name = str(shot.get("team_name") or "Unknown")
        shots_by_team[team_name] = shots_by_team.get(team_name, 0) + 1
        xg_by_team[team_name] = xg_by_team.get(team_name, 0.0) + float(shot.get("shot_statsbomb_xg") or 0)
        if shot.get("shot_outcome_name") == "Goal":
            goals_by_team[team_name] = goals_by_team.get(team_name, 0) + 1

    return {
        "total_shots": total_shots,
        "total_goals": total_goals,
        "total_xg": total_xg,
        "best_chance": best_chance,
        "shots_by_team": shots_by_team,
        "goals_by_team": goals_by_team,
        "xg_by_team": xg_by_team,
    }
