"""Advanced player impact metrics."""

from __future__ import annotations

from typing import Any

from src.analytics.db import query_records


def get_impact_players(match_id: int, limit: int = 10) -> list[dict[str, Any]]:
    rows = query_records(
        """
        WITH players AS (
            SELECT DISTINCT player_id, player_name, team_id, team_name
            FROM event
            WHERE match_id = ? AND player_id IS NOT NULL
        ),
        pass_counts AS (
            SELECT
                e.player_id,
                SUM(CASE WHEN p.pass_goal_assist THEN 1 ELSE 0 END) AS assists,
                SUM(CASE WHEN p.pass_shot_assist THEN 1 ELSE 0 END) AS key_passes,
                SUM(
                    CASE
                        WHEN e.location_x IS NOT NULL
                         AND p.pass_end_x IS NOT NULL
                         AND p.pass_outcome_name IS NULL
                         AND e.location_x < 80
                         AND p.pass_end_x >= 80
                        THEN 1 ELSE 0
                    END
                ) AS progressive_passes
            FROM event e
            INNER JOIN "pass" p ON p.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.player_id
        ),
        shot_counts AS (
            SELECT
                e.player_id,
                COUNT(*) AS shots,
                SUM(CASE WHEN s.shot_outcome_name = 'Goal' THEN 1 ELSE 0 END) AS goals,
                SUM(COALESCE(s.shot_statsbomb_xg, 0)) AS xg
            FROM event e
            INNER JOIN shot s ON s.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.player_id
        )
        SELECT
            p.player_id,
            p.player_name,
            p.team_id,
            p.team_name,
            COALESCE(sc.goals, 0) AS goals,
            COALESCE(pc.assists, 0) AS assists,
            COALESCE(pc.key_passes, 0) AS key_passes,
            COALESCE(sc.shots, 0) AS shots,
            COALESCE(sc.xg, 0) AS xg,
            COALESCE(pc.progressive_passes, 0) AS progressive_passes,
            COALESCE(sc.goals, 0) * 8
              + COALESCE(pc.assists, 0) * 6
              + COALESCE(pc.key_passes, 0) * 3
              + COALESCE(sc.shots, 0) * 1.5
              + COALESCE(sc.xg, 0) * 5
              + COALESCE(pc.progressive_passes, 0) * 2 AS impact_score
        FROM players p
        LEFT JOIN pass_counts pc ON pc.player_id = p.player_id
        LEFT JOIN shot_counts sc ON sc.player_id = p.player_id
        ORDER BY impact_score DESC, goals DESC, xg DESC, player_name
        LIMIT ?
        """,
        (match_id, match_id, match_id, limit),
    )
    for row in rows:
        if row.get("xg") is not None:
            row["xg"] = round(float(row["xg"]), 4)
        if row.get("impact_score") is not None:
            row["impact_score"] = round(float(row["impact_score"]), 3)
    return rows
