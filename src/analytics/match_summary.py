"""Match-level summary metrics."""

from __future__ import annotations

from typing import Any

from src.analytics.db import query_one


def get_match_summary(match_id: int) -> dict[str, Any]:
    row = query_one(
        """
        SELECT
            match_id,
            competition_id,
            season_id,
            match_date,
            home_team_name,
            away_team_name,
            home_score,
            away_score,
            total_events,
            total_shots,
            total_goals,
            total_passes,
            total_xg
        FROM vw_match_summary
        WHERE match_id = ?
        """,
        (match_id,),
    )
    if row is None:
        raise ValueError(f"match_id={match_id} does not exist in the analytics database.")

    home_score = row.get("home_score")
    away_score = row.get("away_score")
    if home_score is None or away_score is None:
        row["winner_team_name"] = None
        row["result_label"] = None
    elif home_score > away_score:
        row["winner_team_name"] = row.get("home_team_name")
        row["result_label"] = "victoria local"
    elif away_score > home_score:
        row["winner_team_name"] = row.get("away_team_name")
        row["result_label"] = "victoria visitante"
    else:
        row["winner_team_name"] = None
        row["result_label"] = "empate"
    return row
