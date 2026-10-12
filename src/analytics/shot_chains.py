"""Connected passing sequences ending in a shot, using observed event locations."""

from __future__ import annotations

import json
from math import isfinite
from typing import Any

from src.analytics.db import query_records

RESTART_PASSES = {"Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"}
CONTROL_EVENTS = {"Pass", "Carry", "Ball Receipt*", "Dribble", "Shot", "Ball Recovery", "Interception", "Clearance"}


def load_shot_chains(match_id: int, home_team: str, away_team: str) -> list[dict[str, Any]]:
    events = query_records(
        """
        SELECT e.event_id, e.event_index, e.period, e.minute, e.second, e.type_name,
               e.possession, e.team_id, e.team_name, e.player_id, e.player_name,
               e.location_x, e.location_y, e.out, e.raw_event_json,
               p.recipient_player_id, p.recipient_player_name, p.pass_outcome_name,
               p.pass_type_name, p.pass_end_x, p.pass_end_y,
               c.carry_end_x, c.carry_end_y,
               s.shot_outcome_name, s.shot_type_name, s.shot_end_x, s.shot_end_y,
               s.shot_statsbomb_xg, s.shot_key_pass_id
        FROM event e
        LEFT JOIN "pass" p ON p.event_id = e.event_id AND p.match_id = e.match_id
        LEFT JOIN carry c ON c.event_id = e.event_id AND c.match_id = e.match_id
        LEFT JOIN shot s ON s.event_id = e.event_id AND s.match_id = e.match_id
        WHERE e.match_id = ?
        ORDER BY e.period, e.event_index
        """,
        (match_id,),
    )
    return build_shot_chains(events, home_team, away_team)


def _point(x: Any, y: Any, *, on_pitch: bool = True) -> list[float] | None:
    try:
        point = [float(x), float(y)]
    except (ValueError, TypeError):
        return None
    if not all(isfinite(value) for value in point):
        return None
    if on_pitch and not (0 <= point[0] <= 120 and 0 <= point[1] <= 80):
        return None
    return point


def _raw(event: dict[str, Any]) -> dict[str, Any]:
    try:
        value = event.get("raw_event_json") or "{}"
        return value if isinstance(value, dict) else json.loads(value)
    except (TypeError, ValueError):
        return {}


def _player(event: dict[str, Any]) -> str:
    return str(event.get("player_id") or event.get("player_name") or event["event_id"])


def _breaks_chain(event: dict[str, Any], team: str) -> bool:
    kind = event.get("type_name")
    raw = _raw(event)
    if kind in {"Half Start", "Half End", "Injury Stoppage", "Referee Ball-Drop", "Offside", "Shot"}:
        return True
    if kind in {"Foul Committed", "Foul Won"}:
        field = "foul_committed" if kind == "Foul Committed" else "foul_won"
        return not raw.get(field, {}).get("advantage", False)
    if event.get("out") or kind in {"Dispossessed", "Miscontrol"}:
        return True
    if kind == "Pass" and event.get("pass_outcome_name"):
        return True
    if kind == "Ball Recovery" and raw.get("ball_recovery", {}).get("recovery_failure"):
        return False
    if kind == "Interception" and raw.get("interception", {}).get("outcome", {}).get("name") in {
        "Lost",
        "Lost In Play",
        "Lost Out",
    }:
        return False
    if kind == "Ball Receipt*" and raw.get("ball_receipt", {}).get("outcome"):
        return event.get("team_name") == team
    return event.get("team_name") != team and kind in CONTROL_EVENTS


def _movement(events: list[dict[str, Any]], target: int, start: int, received: list[float] | None) -> list[list[float]]:
    actor = _player(events[target])
    relevant = []
    for event in reversed(events[start:target]):
        if event.get("type_name") not in CONTROL_EVENTS:
            continue
        if _player(event) != actor or event.get("type_name") == "Pass":
            break
        relevant.append(event)
        if event.get("type_name") in {"Ball Receipt*", "Ball Recovery", "Interception"}:
            break
    points = [received] if received is not None else []
    for event in reversed(relevant):
        point = _point(event.get("location_x"), event.get("location_y"))
        if point is not None:
            points.append(point)
        if event.get("type_name") == "Carry":
            end = _point(event.get("carry_end_x"), event.get("carry_end_y"))
            if end is not None:
                points.append(end)
    points.append(_point(events[target].get("location_x"), events[target].get("location_y")))
    return [
        point for index, point in enumerate(points) if point is not None and (index == 0 or point != points[index - 1])
    ]


def build_shot_chains(events: list[dict[str, Any]], home_team: str, away_team: str) -> list[dict[str, Any]]:
    """Keep up to three completed, recipient-linked passes in the same live possession."""
    events = sorted(events, key=lambda row: (row.get("period") or 0, row.get("event_index") or 0))
    chains = []
    for shot_index, shot in enumerate(events):
        if shot.get("type_name") != "Shot":
            continue
        team = shot.get("team_name")
        if team not in {home_team, away_team}:
            continue
        shot_point = _point(shot.get("location_x"), shot.get("location_y"))
        if shot_point is None:
            continue
        start = shot_index
        if shot.get("shot_type_name") not in {"Penalty", "Free Kick"} and shot.get("possession") is not None:
            for index in range(shot_index - 1, -1, -1):
                event = events[index]
                if event.get("period") != shot.get("period") or event.get("possession") != shot.get("possession"):
                    break
                if _breaks_chain(event, str(team)):
                    break
                start = index
                if event.get("type_name") == "Pass" and event.get("pass_type_name") in RESTART_PASSES:
                    break

        passes = []
        next_actor = _player(shot)
        for index in range(shot_index - 1, start - 1, -1):
            event = events[index]
            if event.get("type_name") != "Pass" or event.get("team_name") != team:
                continue
            recipient = str(event.get("recipient_player_id") or event.get("recipient_player_name") or "")
            if recipient != next_actor:
                break
            if _point(event.get("location_x"), event.get("location_y")) is None:
                break
            if _point(event.get("pass_end_x"), event.get("pass_end_y")) is None:
                break
            passes.append(index)
            next_actor = _player(event)
            if len(passes) == 3:
                break
        passes.reverse()
        stages = []
        received = None
        movement_start = start
        for index in [*passes, shot_index]:
            event = events[index]
            movement = _movement(events, index, movement_start, received)
            endpoint = (
                _point(event.get("shot_end_x"), event.get("shot_end_y"), on_pitch=False)
                if index == shot_index
                else _point(event.get("pass_end_x"), event.get("pass_end_y"))
            )
            stages.append(
                {
                    "event_id": event["event_id"],
                    "player_id": _player(event),
                    "player_name": event.get("player_name") or "—",
                    "movement": movement,
                    "end": endpoint,
                    "is_shot": index == shot_index,
                    "minute": event.get("minute", 0),
                    "second": event.get("second", 0),
                }
            )
            received = endpoint
            movement_start = index + 1
        chains.append(
            {
                "shot_id": shot["event_id"],
                "period": shot.get("period", 1),
                "minute": shot.get("minute", 0),
                "second": shot.get("second", 0),
                "team_name": team,
                "home_team": home_team,
                "away_team": away_team,
                "is_home": team == home_team,
                "is_goal": shot.get("shot_outcome_name") == "Goal",
                "outcome": shot.get("shot_outcome_name"),
                "shot_type": shot.get("shot_type_name"),
                "xg": shot.get("shot_statsbomb_xg"),
                "stages": stages,
            }
        )
    return chains


def shot_chain_title(chain: dict[str, Any], language: str = "es") -> str:
    outcome = (
        ("*GOAL*" if language == "en" else "*GOL*")
        if chain["is_goal"]
        else ("Shot" if language == "en" else "Tiro a gol")
    )
    minute = int(chain.get("minute") or 0)
    second = int(chain.get("second") or 0)
    period = int(chain.get("period") or 1)
    end_minute = {1: 45, 2: 90, 3: 105, 4: 120}.get(period)
    clock = (
        f"{end_minute}+{minute - end_minute}:{second:02d}"
        if end_minute and minute >= end_minute
        else f"{minute:02d}:{second:02d}"
    )
    if period == 5:
        clock += " (Shootout)" if language == "en" else " (Tanda)"
    return f"{clock} – {chain['team_name']} – {outcome}"


def shot_chain_rows(chain: dict[str, Any], language: str = "es") -> list[dict[str, Any]]:
    english = language == "en"
    return [
        {
            "#": index + 1,
            "Minute" if english else "Minuto": f"{int(stage['minute'] or 0):02d}:{int(stage['second'] or 0):02d}",
            "Player" if english else "Jugador": stage["player_name"],
            "Action" if english else "Acción": (
                (("GOAL" if english else "GOL") if chain["is_goal"] else ("Shot" if english else "Tiro a gol"))
                if stage["is_shot"]
                else ("Pass" if english else "Pase")
            ),
        }
        for index, stage in enumerate(chain["stages"])
    ]
