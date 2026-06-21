"""Pressure event analytics."""

from __future__ import annotations

from typing import Any

from src.analytics.db import query_records


def get_pressures(match_id: int) -> list[dict[str, Any]]:
    return query_records(
        """
        SELECT
            e.event_id,
            e.minute,
            e.second,
            e.team_name,
            e.player_name,
            e.location_x,
            e.location_y,
            p.counterpress
        FROM event e
        INNER JOIN pressure p ON p.event_id = e.event_id
        WHERE e.match_id = ?
        ORDER BY e.minute, e.second, e.event_index
        """,
        (match_id,),
    )
