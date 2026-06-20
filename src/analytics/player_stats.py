"""Player-level match statistics."""

from __future__ import annotations

from typing import Any

from src.analytics.db import query_records


def get_player_stats(match_id: int) -> list[dict[str, Any]]:
    return query_records(
        """
        WITH players AS (
            SELECT DISTINCT player_id, player_name, team_id, team_name
            FROM event
            WHERE match_id = ? AND player_id IS NOT NULL
        ),
        event_counts AS (
            SELECT player_id, COUNT(*) AS events
            FROM event
            WHERE match_id = ?
            GROUP BY player_id
        ),
        pass_counts AS (
            SELECT
                e.player_id,
                COUNT(*) AS passes,
                SUM(CASE WHEN p.pass_outcome_name IS NULL THEN 1 ELSE 0 END) AS successful_passes,
                SUM(CASE WHEN p.pass_goal_assist THEN 1 ELSE 0 END) AS assists,
                SUM(CASE WHEN p.pass_shot_assist THEN 1 ELSE 0 END) AS key_passes
            FROM event e INNER JOIN "pass" p ON p.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.player_id
        ),
        shot_counts AS (
            SELECT
                e.player_id,
                COUNT(*) AS shots,
                SUM(CASE WHEN s.shot_outcome_name = 'Goal' THEN 1 ELSE 0 END) AS goals,
                SUM(COALESCE(s.shot_statsbomb_xg, 0)) AS xg
            FROM event e INNER JOIN shot s ON s.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.player_id
        ),
        carry_counts AS (
            SELECT e.player_id, COUNT(*) AS carries
            FROM event e INNER JOIN carry c ON c.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.player_id
        ),
        duel_counts AS (
            SELECT e.player_id, COUNT(*) AS duels
            FROM event e INNER JOIN duel d ON d.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.player_id
        ),
        pressure_counts AS (
            SELECT e.player_id, COUNT(*) AS pressures
            FROM event e INNER JOIN pressure p ON p.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.player_id
        ),
        foul_counts AS (
            SELECT
                e.player_id,
                SUM(CASE WHEN f.foul_type = 'committed' THEN 1 ELSE 0 END) AS fouls_committed,
                SUM(CASE WHEN f.foul_type = 'won' THEN 1 ELSE 0 END) AS fouls_won
            FROM event e INNER JOIN foul f ON f.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.player_id
        )
        SELECT
            p.player_id,
            p.player_name,
            p.team_id,
            p.team_name,
            COALESCE(ec.events, 0) AS events,
            COALESCE(pc.passes, 0) AS passes,
            COALESCE(pc.successful_passes, 0) AS successful_passes,
            COALESCE(sc.shots, 0) AS shots,
            COALESCE(sc.goals, 0) AS goals,
            COALESCE(sc.xg, 0) AS xg,
            COALESCE(pc.assists, 0) AS assists,
            COALESCE(pc.key_passes, 0) AS key_passes,
            COALESCE(cc.carries, 0) AS carries,
            COALESCE(dc.duels, 0) AS duels,
            COALESCE(pr.pressures, 0) AS pressures,
            COALESCE(fc.fouls_committed, 0) AS fouls_committed,
            COALESCE(fc.fouls_won, 0) AS fouls_won
        FROM players p
        LEFT JOIN event_counts ec ON ec.player_id = p.player_id
        LEFT JOIN pass_counts pc ON pc.player_id = p.player_id
        LEFT JOIN shot_counts sc ON sc.player_id = p.player_id
        LEFT JOIN carry_counts cc ON cc.player_id = p.player_id
        LEFT JOIN duel_counts dc ON dc.player_id = p.player_id
        LEFT JOIN pressure_counts pr ON pr.player_id = p.player_id
        LEFT JOIN foul_counts fc ON fc.player_id = p.player_id
        ORDER BY goals DESC, xg DESC, shots DESC, events DESC, player_name
        """,
        (match_id,) * 8,
    )
