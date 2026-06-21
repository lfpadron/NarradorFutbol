"""xG validation and breakdown metrics."""

from __future__ import annotations

from typing import Any

from src.analytics.db import query_records


def get_xg_breakdown(match_id: int) -> list[dict[str, Any]]:
    rows = query_records(
        """
        WITH shots_ranked AS (
            SELECT
                e.team_id,
                e.team_name,
                e.minute,
                s.shot_statsbomb_xg,
                s.shot_outcome_name,
                ROW_NUMBER() OVER (
                    PARTITION BY e.team_id
                    ORDER BY COALESCE(s.shot_statsbomb_xg, 0) DESC, e.minute
                ) AS chance_rank
            FROM event e
            INNER JOIN shot s ON s.event_id = e.event_id
            WHERE e.match_id = ?
        ),
        aggregates AS (
            SELECT
                team_id,
                team_name,
                COUNT(*) AS shots,
                SUM(CASE WHEN shot_outcome_name = 'Goal' THEN 1 ELSE 0 END) AS goals,
                SUM(COALESCE(shot_statsbomb_xg, 0)) AS xg_total,
                AVG(COALESCE(shot_statsbomb_xg, 0)) AS xg_average
            FROM shots_ranked
            GROUP BY team_id, team_name
        ),
        best AS (
            SELECT
                team_id,
                shot_statsbomb_xg AS best_chance,
                minute AS best_chance_minute
            FROM shots_ranked
            WHERE chance_rank = 1
        )
        SELECT
            a.team_id,
            a.team_name,
            a.shots,
            a.goals,
            a.xg_total,
            a.xg_average,
            b.best_chance,
            b.best_chance_minute
        FROM aggregates a
        LEFT JOIN best b ON b.team_id = a.team_id
        ORDER BY a.xg_total DESC, a.shots DESC
        """,
        (match_id,),
    )
    for row in rows:
        for key in ("xg_total", "xg_average", "best_chance"):
            if row.get(key) is not None:
                row[key] = round(float(row[key]), 4)
    return rows
