"""Detection of key football moments for a match."""

from __future__ import annotations

from typing import Any

from src.analytics.db import query_records


def get_key_moments(match_id: int) -> list[dict[str, Any]]:
    moments: list[dict[str, Any]] = []
    moments.extend(_goal_moments(match_id))
    moments.extend(_big_chance_moments(match_id))
    moments.extend(_card_moments(match_id))
    moments.extend(_substitution_moments(match_id))
    moments.extend(_penalty_moments(match_id))
    moments.extend(_assist_moments(match_id))
    return sorted(
        moments,
        key=lambda row: (
            int(row.get("minute") or 0),
            int(row.get("second") or 0),
            -int(row.get("importance_score") or 0),
        ),
    )


def _goal_moments(match_id: int) -> list[dict[str, Any]]:
    rows = query_records(
        """
        SELECT event_id, minute, second, team_name, player_name, shot_statsbomb_xg
        FROM vw_shots
        WHERE match_id = ? AND shot_outcome_name = 'Goal'
        """,
        (match_id,),
    )
    return [
        _moment(
            row,
            moment_type="goal",
            title=f"Gol de {row.get('player_name')}",
            description=f"{row.get('team_name')} anota con xG {float(row.get('shot_statsbomb_xg') or 0):.2f}.",
            importance_score=100,
        )
        for row in rows
    ]


def _big_chance_moments(match_id: int) -> list[dict[str, Any]]:
    rows = query_records(
        """
        SELECT event_id, minute, second, team_name, player_name, shot_statsbomb_xg, shot_outcome_name
        FROM vw_shots
        WHERE match_id = ?
          AND COALESCE(shot_statsbomb_xg, 0) >= 0.20
          AND COALESCE(shot_outcome_name, '') <> 'Goal'
        """,
        (match_id,),
    )
    return [
        _moment(
            row,
            moment_type="big_chance",
            title=f"Ocasión clara de {row.get('player_name')}",
            description=(
                f"Tiro de {row.get('team_name')} con xG "
                f"{float(row.get('shot_statsbomb_xg') or 0):.2f}; resultado: {row.get('shot_outcome_name')}."
            ),
            importance_score=75,
        )
        for row in rows
    ]


def _card_moments(match_id: int) -> list[dict[str, Any]]:
    rows = query_records(
        """
        SELECT e.event_id, e.minute, e.second, e.team_name, e.player_name, f.card_name
        FROM event e
        INNER JOIN foul f ON f.event_id = e.event_id
        WHERE e.match_id = ? AND f.card_name IS NOT NULL
        """,
        (match_id,),
    )
    moments = []
    for row in rows:
        card = str(row.get("card_name") or "")
        is_red = "red" in card.lower()
        moments.append(
            _moment(
                row,
                moment_type="red_card" if is_red else "yellow_card",
                title=f"{card} para {row.get('player_name')}",
                description=f"{row.get('player_name')} de {row.get('team_name')} recibe {card}.",
                importance_score=90 if is_red else 35,
            )
        )
    return moments


def _substitution_moments(match_id: int) -> list[dict[str, Any]]:
    rows = query_records(
        """
        SELECT
            e.event_id,
            e.minute,
            e.second,
            e.team_name,
            e.player_name,
            s.replacement_player_name
        FROM event e
        INNER JOIN substitution s ON s.event_id = e.event_id
        WHERE e.match_id = ?
        """,
        (match_id,),
    )
    return [
        _moment(
            row,
            moment_type="substitution",
            title=f"Cambio de {row.get('team_name')}",
            description=f"Sale {row.get('player_name')}; entra {row.get('replacement_player_name')}.",
            importance_score=40,
        )
        for row in rows
    ]


def _penalty_moments(match_id: int) -> list[dict[str, Any]]:
    rows = query_records(
        """
        SELECT event_id, minute, second, team_name, player_name, shot_outcome_name
        FROM vw_shots
        WHERE match_id = ? AND shot_type_name = 'Penalty'
        """,
        (match_id,),
    )
    return [
        _moment(
            row,
            moment_type="penalty",
            title=f"Penalti de {row.get('player_name')}",
            description=f"Penalti para {row.get('team_name')}; resultado: {row.get('shot_outcome_name')}.",
            importance_score=85,
        )
        for row in rows
    ]


def _assist_moments(match_id: int) -> list[dict[str, Any]]:
    rows = query_records(
        """
        SELECT e.event_id, e.minute, e.second, e.team_name, e.player_name, p.recipient_player_name
        FROM event e
        INNER JOIN "pass" p ON p.event_id = e.event_id
        WHERE e.match_id = ? AND p.pass_goal_assist
        """,
        (match_id,),
    )
    return [
        _moment(
            row,
            moment_type="assist",
            title=f"Asistencia de {row.get('player_name')}",
            description=f"{row.get('player_name')} asiste a {row.get('recipient_player_name')}.",
            importance_score=70,
        )
        for row in rows
    ]


def _moment(
    row: dict[str, Any],
    moment_type: str,
    title: str,
    description: str,
    importance_score: int,
) -> dict[str, Any]:
    return {
        "minute": row.get("minute"),
        "second": row.get("second"),
        "type": moment_type,
        "team_name": row.get("team_name"),
        "player_name": row.get("player_name"),
        "title": title,
        "description": description,
        "importance_score": importance_score,
        "evidence_event_ids": [row.get("event_id")] if row.get("event_id") else [],
    }
