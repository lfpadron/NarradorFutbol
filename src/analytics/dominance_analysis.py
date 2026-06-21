"""Match dominance metrics."""

from __future__ import annotations

from typing import Any

from src.analytics.db import query_records


def get_match_dominance(match_id: int) -> list[dict[str, Any]]:
    rows = query_records(
        """
        WITH teams AS (
            SELECT DISTINCT team_id, team_name
            FROM event
            WHERE match_id = ? AND team_id IS NOT NULL
        ),
        events AS (
            SELECT
                team_id,
                SUM(CASE WHEN location_x >= 60 THEN 1 ELSE 0 END) AS offensive_events,
                SUM(CASE WHEN location_x >= 80 THEN 1 ELSE 0 END) AS final_third_entries
            FROM event
            WHERE match_id = ?
            GROUP BY team_id
        ),
        shots AS (
            SELECT
                e.team_id,
                COUNT(*) AS shots,
                SUM(COALESCE(s.shot_statsbomb_xg, 0)) AS xg
            FROM event e
            INNER JOIN shot s ON s.event_id = e.event_id
            WHERE e.match_id = ?
            GROUP BY e.team_id
        ),
        progressive AS (
            SELECT
                e.team_id,
                COUNT(*) AS progressive_passes
            FROM event e
            INNER JOIN "pass" p ON p.event_id = e.event_id
            WHERE e.match_id = ?
              AND e.location_x IS NOT NULL
              AND p.pass_end_x IS NOT NULL
              AND p.pass_outcome_name IS NULL
              AND e.location_x < 80
              AND p.pass_end_x >= 80
            GROUP BY e.team_id
        ),
        offensive_possessions AS (
            SELECT possession_team_id AS team_id, COUNT(*) AS offensive_possessions
            FROM (
                SELECT
                    possession,
                    possession_team_id,
                    MAX(CASE WHEN location_x >= 60 THEN 1 ELSE 0 END) AS has_offensive_event
                FROM event
                WHERE match_id = ?
                  AND possession IS NOT NULL
                  AND possession_team_id IS NOT NULL
                GROUP BY possession, possession_team_id
            )
            WHERE has_offensive_event = 1
            GROUP BY possession_team_id
        )
        SELECT
            t.team_id,
            t.team_name,
            COALESCE(e.offensive_events, 0) AS offensive_events,
            COALESCE(s.shots, 0) AS shots,
            COALESCE(s.xg, 0) AS xg,
            COALESCE(e.final_third_entries, 0) AS final_third_entries,
            COALESCE(p.progressive_passes, 0) AS progressive_passes,
            COALESCE(op.offensive_possessions, 0) AS offensive_possessions,
            COALESCE(s.xg, 0) * 10
              + COALESCE(s.shots, 0) * 3
              + COALESCE(p.progressive_passes, 0) * 1
              + COALESCE(e.final_third_entries, 0) * 0.5 AS dominance_score
        FROM teams t
        LEFT JOIN events e ON e.team_id = t.team_id
        LEFT JOIN shots s ON s.team_id = t.team_id
        LEFT JOIN progressive p ON p.team_id = t.team_id
        LEFT JOIN offensive_possessions op ON op.team_id = t.team_id
        ORDER BY dominance_score DESC, t.team_name
        """,
        (match_id,) * 5,
    )
    return [_round_score(row) for row in rows]


def get_dominance_intervals(match_id: int, interval_minutes: int = 5) -> list[dict[str, Any]]:
    rows = query_records(
        """
        WITH interval_teams AS (
            SELECT
                FLOOR(minute / ?) * ? AS interval_start,
                FLOOR(minute / ?) * ? + ? AS interval_end,
                team_id,
                team_name,
                SUM(CASE WHEN location_x >= 60 THEN 1 ELSE 0 END) AS offensive_events,
                SUM(CASE WHEN location_x >= 80 THEN 1 ELSE 0 END) AS final_third_entries
            FROM event
            WHERE match_id = ?
              AND team_id IS NOT NULL
              AND minute IS NOT NULL
            GROUP BY interval_start, interval_end, team_id, team_name
        ),
        interval_shots AS (
            SELECT
                FLOOR(e.minute / ?) * ? AS interval_start,
                e.team_id,
                COUNT(*) AS shots,
                SUM(COALESCE(s.shot_statsbomb_xg, 0)) AS xg
            FROM event e
            INNER JOIN shot s ON s.event_id = e.event_id
            WHERE e.match_id = ?
              AND e.team_id IS NOT NULL
              AND e.minute IS NOT NULL
            GROUP BY interval_start, e.team_id
        ),
        interval_progressive AS (
            SELECT
                FLOOR(e.minute / ?) * ? AS interval_start,
                e.team_id,
                COUNT(*) AS progressive_passes
            FROM event e
            INNER JOIN "pass" p ON p.event_id = e.event_id
            WHERE e.match_id = ?
              AND e.team_id IS NOT NULL
              AND e.minute IS NOT NULL
              AND e.location_x IS NOT NULL
              AND p.pass_end_x IS NOT NULL
              AND p.pass_outcome_name IS NULL
              AND e.location_x < 80
              AND p.pass_end_x >= 80
            GROUP BY interval_start, e.team_id
        ),
        scored AS (
            SELECT
                it.interval_start,
                it.interval_end,
                it.team_id,
                it.team_name,
                COALESCE(s.shots, 0) AS shots,
                COALESCE(s.xg, 0) AS xg,
                COALESCE(it.final_third_entries, 0) AS final_third_entries,
                COALESCE(ip.progressive_passes, 0) AS progressive_passes,
                COALESCE(s.xg, 0) * 10
                  + COALESCE(s.shots, 0) * 3
                  + COALESCE(ip.progressive_passes, 0) * 1
                  + COALESCE(it.final_third_entries, 0) * 0.5 AS dominance_score
            FROM interval_teams it
            LEFT JOIN interval_shots s
              ON s.interval_start = it.interval_start AND s.team_id = it.team_id
            LEFT JOIN interval_progressive ip
              ON ip.interval_start = it.interval_start AND ip.team_id = it.team_id
        )
        SELECT *
        FROM scored
        ORDER BY interval_start, dominance_score DESC, team_name
        """,
        (
            interval_minutes,
            interval_minutes,
            interval_minutes,
            interval_minutes,
            interval_minutes,
            match_id,
            interval_minutes,
            interval_minutes,
            match_id,
            interval_minutes,
            interval_minutes,
            match_id,
        ),
    )

    by_interval: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for row in rows:
        key = (int(row["interval_start"]), int(row["interval_end"]))
        by_interval.setdefault(key, []).append(_round_score(row))

    intervals: list[dict[str, Any]] = []
    for (start, end), interval_rows in sorted(by_interval.items()):
        leader = interval_rows[0]
        runner_up = interval_rows[1] if len(interval_rows) > 1 else None
        leader_score = float(leader.get("dominance_score") or 0)
        runner_score = float(runner_up.get("dominance_score") or 0) if runner_up else 0.0
        margin = leader_score - runner_score
        if margin < 3:
            intervals.append(
                {
                    "interval_start": start,
                    "interval_end": end,
                    "team_id": None,
                    "team_name": "Equilibrio",
                    "dominance_score": round(leader_score, 3),
                    "score_margin": round(margin, 3),
                    "dominance_label": "equilibrio",
                }
            )
        else:
            enriched = dict(leader)
            enriched["score_margin"] = round(margin, 3)
            enriched["dominance_label"] = "dominio"
            intervals.append(enriched)
    return intervals


def _round_score(row: dict[str, Any]) -> dict[str, Any]:
    clean = dict(row)
    if clean.get("xg") is not None:
        clean["xg"] = round(float(clean["xg"]), 4)
    if clean.get("dominance_score") is not None:
        clean["dominance_score"] = round(float(clean["dominance_score"]), 3)
    return clean
