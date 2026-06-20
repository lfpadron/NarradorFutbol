"""Simple MVP momentum metric by time interval."""

from __future__ import annotations

from typing import Any

from src.analytics.db import query_records


def get_momentum_by_interval(match_id: int, interval_minutes: int = 5) -> list[dict[str, Any]]:
    rows = query_records(
        """
        WITH interval_events AS (
            SELECT
                FLOOR(e.minute / ?) * ? AS interval_start,
                FLOOR(e.minute / ?) * ? + ? AS interval_end,
                e.team_id,
                e.team_name,
                SUM(CASE WHEN e.type_name = 'Shot' THEN 1 ELSE 0 END) AS shots,
                SUM(COALESCE(s.shot_statsbomb_xg, 0)) AS xg,
                SUM(CASE WHEN e.location_x >= 80 THEN 1 ELSE 0 END) AS final_third_entries,
                SUM(CASE WHEN e.location_x >= 60 THEN 1 ELSE 0 END) AS attacking_events
            FROM event e
            LEFT JOIN shot s ON s.event_id = e.event_id
            WHERE e.match_id = ?
              AND e.team_id IS NOT NULL
            GROUP BY interval_start, interval_end, e.team_id, e.team_name
        )
        SELECT
            interval_start,
            interval_end,
            team_id,
            team_name,
            shots,
            xg,
            final_third_entries,
            attacking_events,
            shots * 3
              + xg * 10
              + final_third_entries * 1
              + attacking_events * 0.5 AS momentum_score
        FROM interval_events
        ORDER BY interval_start, team_name
        """,
        (
            interval_minutes,
            interval_minutes,
            interval_minutes,
            interval_minutes,
            interval_minutes,
            match_id,
        ),
    )
    for row in rows:
        row["interval_start"] = int(row["interval_start"]) if row.get("interval_start") is not None else None
        row["interval_end"] = int(row["interval_end"]) if row.get("interval_end") is not None else None
    return rows
