"""Pass-level analytics."""

from __future__ import annotations

from typing import Any

from src.analytics.db import query_records


def get_pass_summary(match_id: int) -> dict[str, Any]:
    rows = query_records(
        """
        SELECT
            e.team_name,
            COUNT(*) AS passes,
            SUM(CASE WHEN p.pass_outcome_name IS NULL THEN 1 ELSE 0 END) AS successful_passes,
            SUM(CASE WHEN p.pass_goal_assist THEN 1 ELSE 0 END) AS assists,
            SUM(CASE WHEN p.pass_shot_assist THEN 1 ELSE 0 END) AS key_passes,
            SUM(CASE WHEN p.pass_cross THEN 1 ELSE 0 END) AS crosses,
            SUM(CASE WHEN p.pass_switch THEN 1 ELSE 0 END) AS switches,
            SUM(CASE WHEN p.pass_through_ball THEN 1 ELSE 0 END) AS through_balls
        FROM event e
        INNER JOIN "pass" p ON p.event_id = e.event_id
        WHERE e.match_id = ?
        GROUP BY e.team_name
        ORDER BY e.team_name
        """,
        (match_id,),
    )
    total_passes = sum(int(row.get("passes") or 0) for row in rows)
    successful_passes = sum(int(row.get("successful_passes") or 0) for row in rows)
    completion = round(100.0 * successful_passes / total_passes, 2) if total_passes else None

    return {
        "total_passes": total_passes,
        "successful_passes": successful_passes,
        "pass_completion_pct": completion,
        "passes_by_team": {str(row.get("team_name")): int(row.get("passes") or 0) for row in rows},
        "completion_by_team": {
            str(row.get("team_name")): (
                round(100.0 * int(row.get("successful_passes") or 0) / int(row.get("passes") or 0), 2)
                if int(row.get("passes") or 0)
                else None
            )
            for row in rows
        },
        "assists": sum(int(row.get("assists") or 0) for row in rows),
        "key_passes": sum(int(row.get("key_passes") or 0) for row in rows),
        "crosses": sum(int(row.get("crosses") or 0) for row in rows),
        "switches": sum(int(row.get("switches") or 0) for row in rows),
        "through_balls": sum(int(row.get("through_balls") or 0) for row in rows),
    }


def get_progressive_passes(match_id: int) -> list[dict[str, Any]]:
    return query_records(
        """
        SELECT
            e.event_id,
            e.minute,
            e.second,
            e.team_name,
            e.player_name,
            p.recipient_player_name,
            e.location_x,
            e.location_y,
            p.pass_end_x,
            p.pass_end_y,
            ABS(p.pass_end_x - e.location_x) AS progressive_distance,
            p.pass_outcome_name
        FROM event e
        INNER JOIN "pass" p ON p.event_id = e.event_id
        WHERE e.match_id = ?
          AND e.location_x IS NOT NULL
          AND p.pass_end_x IS NOT NULL
          AND ABS(p.pass_end_x - e.location_x) >= 10
        ORDER BY progressive_distance DESC, e.minute, e.second
        """,
        (match_id,),
    )
