"""Automatic validation checks for transformed match analytics."""

from __future__ import annotations

from typing import Any

from src.analytics.db import query_one
from src.analytics.advanced_metrics import get_impact_players
from src.analytics.dominance_analysis import get_match_dominance
from src.analytics.match_summary import get_match_summary
from src.analytics.xg_analysis import get_xg_breakdown


REFERENCE_MATCH_ID = 7534


def validate_match(match_id: int) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []

    _append_count_finding(
        findings,
        match_id,
        "goals_gt_shots",
        "FAIL",
        "Hay más goles que tiros registrados.",
        """
        SELECT COUNT(*) AS rows
        FROM (
            SELECT COUNT(*) AS shots, SUM(CASE WHEN shot_outcome_name = 'Goal' THEN 1 ELSE 0 END) AS goals
            FROM shot
            WHERE match_id = ?
        )
        WHERE goals > shots
        """,
    )
    _append_count_finding(
        findings,
        match_id,
        "negative_xg",
        "FAIL",
        "Existen tiros con xG negativo.",
        "SELECT COUNT(*) AS rows FROM shot WHERE match_id = ? AND shot_statsbomb_xg < 0",
    )
    _append_count_finding(
        findings,
        match_id,
        "player_without_team",
        "WARNING",
        "Existen eventos con jugador pero sin equipo.",
        "SELECT COUNT(*) AS rows FROM event WHERE match_id = ? AND player_id IS NOT NULL AND team_id IS NULL",
    )
    _append_count_finding(
        findings,
        match_id,
        "event_without_minute",
        "WARNING",
        "Existen eventos sin minuto.",
        "SELECT COUNT(*) AS rows FROM event WHERE match_id = ? AND minute IS NULL",
    )
    _append_count_finding(
        findings,
        match_id,
        "event_coordinates_out_of_range",
        "FAIL",
        "Existen eventos con coordenadas fuera del rango StatsBomb 120x80.",
        """
        SELECT COUNT(*) AS rows
        FROM event
        WHERE match_id = ?
          AND (
            location_x < 0 OR location_x > 120
            OR location_y < 0 OR location_y > 80
          )
        """,
    )
    _append_count_finding(
        findings,
        match_id,
        "pass_coordinates_out_of_range",
        "FAIL",
        "Existen pases con destino fuera del rango StatsBomb 120x80.",
        """
        SELECT COUNT(*) AS rows
        FROM "pass"
        WHERE match_id = ?
          AND (
            pass_end_x < 0 OR pass_end_x > 120
            OR pass_end_y < 0 OR pass_end_y > 80
          )
        """,
    )
    _append_count_finding(
        findings,
        match_id,
        "inconsistent_possessions",
        "WARNING",
        "Existen posesiones asignadas a más de un equipo de posesión.",
        """
        SELECT COUNT(*) AS rows
        FROM (
            SELECT possession
            FROM event
            WHERE match_id = ? AND possession IS NOT NULL
            GROUP BY possession
            HAVING COUNT(DISTINCT possession_team_id) > 1
        )
        """,
    )

    if any(finding["severity"] == "FAIL" for finding in findings):
        status = "FAIL"
    elif findings:
        status = "WARNING"
    else:
        status = "PASS"

    return {"match_id": match_id, "status": status, "findings": findings}


def compare_against_reference(match_id: int = REFERENCE_MATCH_ID) -> dict[str, Any]:
    target = _reference_summary(match_id)
    comparison = {"reference_match_id": REFERENCE_MATCH_ID, "target": target}
    if match_id != REFERENCE_MATCH_ID:
        comparison["reference"] = _reference_summary(REFERENCE_MATCH_ID)
    return comparison


def _reference_summary(match_id: int) -> dict[str, Any]:
    summary = get_match_summary(match_id)
    xg_rows = get_xg_breakdown(match_id)
    impact_players = get_impact_players(match_id)
    dominance_rows = get_match_dominance(match_id)
    home_team = summary.get("home_team_name")
    away_team = summary.get("away_team_name")
    by_team = {row["team_name"]: row for row in xg_rows}
    return {
        "match_id": match_id,
        "winner": summary.get("winner_team_name"),
        "result_label": summary.get("result_label"),
        "score": f"{summary.get('home_team_name')} {summary.get('home_score')}-{summary.get('away_score')} {summary.get('away_team_name')}",
        "home_xg": by_team.get(home_team, {}).get("xg_total"),
        "away_xg": by_team.get(away_team, {}).get("xg_total"),
        "home_shots": by_team.get(home_team, {}).get("shots"),
        "away_shots": by_team.get(away_team, {}).get("shots"),
        "xg_by_team": {row["team_name"]: round(float(row.get("xg_total") or 0), 4) for row in xg_rows},
        "shots_by_team": {row["team_name"]: int(row.get("shots") or 0) for row in xg_rows},
        "estimated_dominance": dominance_rows[0].get("team_name") if dominance_rows else None,
        "most_influential_player": impact_players[0] if impact_players else None,
    }


def _append_count_finding(
    findings: list[dict[str, Any]],
    match_id: int,
    code: str,
    severity: str,
    message: str,
    sql: str,
) -> None:
    row = query_one(sql, (match_id,))
    count = int(row.get("rows") or 0) if row else 0
    if count:
        findings.append(
            {
                "code": code,
                "severity": severity,
                "message": message,
                "rows": count,
            }
        )
