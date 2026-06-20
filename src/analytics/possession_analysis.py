"""Possession sequence analytics."""

from __future__ import annotations

from typing import Any

from src.analytics.db import query_records


def get_possession_sequences(match_id: int) -> list[dict[str, Any]]:
    return query_records(
        """
        SELECT
            e.match_id,
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
        GROUP BY e.match_id, e.possession, e.possession_team_id, e.possession_team_name
        ORDER BY e.possession
        """,
        (match_id,),
    )


def get_possession_summary(match_id: int) -> dict[str, Any]:
    sequences = get_possession_sequences(match_id)
    possessions_total = len(sequences)
    possessions_by_team: dict[str, int] = {}
    for sequence in sequences:
        team_name = str(sequence.get("team_name") or "Unknown")
        possessions_by_team[team_name] = possessions_by_team.get(team_name, 0) + 1

    avg_events = (
        sum(int(sequence.get("event_count") or 0) for sequence in sequences) / possessions_total
        if possessions_total
        else None
    )

    return {
        "possessions_total": possessions_total,
        "possessions_by_team": possessions_by_team,
        "avg_events_per_possession": avg_events,
        "possessions_ending_in_shot": sum(1 for sequence in sequences if sequence.get("has_shot")),
        "possessions_ending_in_goal": sum(1 for sequence in sequences if sequence.get("has_goal")),
    }
