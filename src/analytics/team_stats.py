"""Team-level match statistics."""

from __future__ import annotations

from typing import Any

from src.analytics.db import query_records


def get_team_stats(match_id: int) -> list[dict[str, Any]]:
    return query_records(
        """
        WITH teams AS (
            SELECT DISTINCT team_id, team_name
            FROM event
            WHERE match_id = ? AND team_id IS NOT NULL
        ),
        event_counts AS (
            SELECT team_id, COUNT(*) AS events
            FROM event
            WHERE match_id = ?
            GROUP BY team_id
        ),
        pass_counts AS (
            SELECT
                e.team_id,
                COUNT(*) AS passes,
                SUM(CASE WHEN p.pass_outcome_name IS NULL THEN 1 ELSE 0 END) AS successful_passes
            FROM event e
            INNER JOIN "pass" p ON p.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.team_id
        ),
        shot_counts AS (
            SELECT
                e.team_id,
                COUNT(*) AS shots,
                SUM(CASE WHEN s.shot_outcome_name = 'Goal' THEN 1 ELSE 0 END) AS goals,
                SUM(COALESCE(s.shot_statsbomb_xg, 0)) AS xg
            FROM event e
            INNER JOIN shot s ON s.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.team_id
        ),
        carry_counts AS (
            SELECT e.team_id, COUNT(*) AS carries
            FROM event e INNER JOIN carry c ON c.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.team_id
        ),
        duel_counts AS (
            SELECT e.team_id, COUNT(*) AS duels
            FROM event e INNER JOIN duel d ON d.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.team_id
        ),
        pressure_counts AS (
            SELECT e.team_id, COUNT(*) AS pressures
            FROM event e INNER JOIN pressure p ON p.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.team_id
        ),
        foul_counts AS (
            SELECT
                e.team_id,
                SUM(CASE WHEN f.foul_type = 'committed' THEN 1 ELSE 0 END) AS fouls_committed,
                SUM(CASE WHEN f.foul_type = 'won' THEN 1 ELSE 0 END) AS fouls_won,
                SUM(CASE WHEN LOWER(COALESCE(f.card_name, '')) LIKE '%yellow%' THEN 1 ELSE 0 END) AS yellow_cards,
                SUM(CASE WHEN LOWER(COALESCE(f.card_name, '')) LIKE '%red%' THEN 1 ELSE 0 END) AS red_cards
            FROM event e INNER JOIN foul f ON f.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.team_id
        )
        SELECT
            t.team_id,
            t.team_name,
            COALESCE(ec.events, 0) AS events,
            COALESCE(pc.passes, 0) AS passes,
            COALESCE(pc.successful_passes, 0) AS successful_passes,
            CASE
                WHEN COALESCE(pc.passes, 0) = 0 THEN NULL
                ELSE ROUND(100.0 * pc.successful_passes / pc.passes, 2)
            END AS pass_completion_pct,
            COALESCE(sc.shots, 0) AS shots,
            COALESCE(sc.goals, 0) AS goals,
            COALESCE(sc.xg, 0) AS xg,
            COALESCE(cc.carries, 0) AS carries,
            COALESCE(dc.duels, 0) AS duels,
            COALESCE(pr.pressures, 0) AS pressures,
            COALESCE(fc.fouls_committed, 0) AS fouls_committed,
            COALESCE(fc.fouls_won, 0) AS fouls_won,
            COALESCE(fc.yellow_cards, 0) AS yellow_cards,
            COALESCE(fc.red_cards, 0) AS red_cards
        FROM teams t
        LEFT JOIN event_counts ec ON ec.team_id = t.team_id
        LEFT JOIN pass_counts pc ON pc.team_id = t.team_id
        LEFT JOIN shot_counts sc ON sc.team_id = t.team_id
        LEFT JOIN carry_counts cc ON cc.team_id = t.team_id
        LEFT JOIN duel_counts dc ON dc.team_id = t.team_id
        LEFT JOIN pressure_counts pr ON pr.team_id = t.team_id
        LEFT JOIN foul_counts fc ON fc.team_id = t.team_id
        ORDER BY t.team_name
        """,
        (match_id,) * 8,
    )
