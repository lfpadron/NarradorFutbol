"""Dangerous possession detection."""

from __future__ import annotations

from typing import Any

from src.analytics.db import query_records


def get_dangerous_attacks(match_id: int) -> list[dict[str, Any]]:
    rows = query_records(
        """
        WITH possession_base AS (
            SELECT
                e.possession,
                e.possession_team_id AS team_id,
                e.possession_team_name AS team_name,
                MIN(e.minute) AS start_minute,
                MAX(e.minute) AS end_minute,
                COUNT(*) AS event_count,
                SUM(CASE WHEN e.type_name = 'Shot' THEN 1 ELSE 0 END) > 0 AS has_shot,
                SUM(CASE WHEN s.shot_outcome_name = 'Goal' THEN 1 ELSE 0 END) > 0 AS has_goal,
                SUM(COALESCE(s.shot_statsbomb_xg, 0)) AS xg
            FROM event e
            LEFT JOIN shot s ON s.event_id = e.event_id
            WHERE e.match_id = ?
              AND e.possession IS NOT NULL
            GROUP BY e.possession, e.possession_team_id, e.possession_team_name
        ),
        progressive AS (
            SELECT
                e.possession,
                COUNT(*) AS progressive_passes
            FROM event e
            INNER JOIN "pass" p ON p.event_id = e.event_id
            WHERE e.match_id = ?
              AND e.possession IS NOT NULL
              AND e.location_x IS NOT NULL
              AND p.pass_end_x IS NOT NULL
              AND p.pass_outcome_name IS NULL
              AND e.location_x < 80
              AND p.pass_end_x >= 80
            GROUP BY e.possession
        )
        SELECT
            pb.possession,
            pb.team_id,
            pb.team_name,
            pb.start_minute,
            pb.end_minute,
            pb.event_count,
            pb.xg,
            pb.has_shot,
            pb.has_goal,
            COALESCE(p.progressive_passes, 0) AS progressive_passes
        FROM possession_base pb
        LEFT JOIN progressive p ON p.possession = pb.possession
        WHERE pb.has_shot
           OR COALESCE(pb.xg, 0) >= 0.10
           OR COALESCE(p.progressive_passes, 0) > 0
        ORDER BY pb.start_minute, pb.possession
        """,
        (match_id, match_id),
    )
    for row in rows:
        row["xg"] = round(float(row.get("xg") or 0), 4)
    return rows
