"""Normalize StatsBomb event JSON files into event fact tables."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config import RAW_EVENTS_DIR
from src.transform.utils import (
    EVENT_FILE_RE,
    as_bool,
    as_float,
    as_int,
    as_str,
    distance,
    json_text,
    load_records,
    match_id_from_path,
    object_id,
    object_name,
    point,
    point3,
)


def normalize_events_for_match(match_id: int, raw_events_dir: Path = RAW_EVENTS_DIR) -> dict[str, list[dict[str, Any]]]:
    path = raw_events_dir / f"events.match-{match_id}.json"
    if not path.exists():
        raise FileNotFoundError(f"Events file not found for match_id={match_id}: {path}")
    return normalize_events_file(path)


def normalize_events_file(path: Path) -> dict[str, list[dict[str, Any]]]:
    path_match_id = match_id_from_path(path, EVENT_FILE_RE)
    rows: dict[str, list[dict[str, Any]]] = {
        "event": [],
        "pass": [],
        "shot": [],
        "carry": [],
        "duel": [],
        "pressure": [],
        "foul": [],
        "goalkeeper_action": [],
        "substitution": [],
        "event_relationship": [],
        "freeze_frame": [],
        "team": [],
        "player": [],
    }

    for event in load_records(path):
        match_id = as_int(event.get("match_id")) or path_match_id
        event_id = as_str(event.get("id"))
        type_name = object_name(event.get("type"))
        location_x, location_y = point(event.get("location"))

        rows["event"].append(
            {
                "event_id": event_id,
                "match_id": match_id,
                "event_index": as_int(event.get("index")),
                "period": as_int(event.get("period")),
                "timestamp": as_str(event.get("timestamp")),
                "minute": as_int(event.get("minute")),
                "second": as_int(event.get("second")),
                "type_id": object_id(event.get("type")),
                "type_name": type_name,
                "possession": as_int(event.get("possession")),
                "possession_team_id": object_id(event.get("possession_team")),
                "possession_team_name": object_name(event.get("possession_team")),
                "team_id": object_id(event.get("team")),
                "team_name": object_name(event.get("team")),
                "player_id": object_id(event.get("player")),
                "player_name": object_name(event.get("player")),
                "position_id": object_id(event.get("position")),
                "position_name": object_name(event.get("position")),
                "play_pattern_id": object_id(event.get("play_pattern")),
                "play_pattern_name": object_name(event.get("play_pattern")),
                "duration": as_float(event.get("duration")),
                "location_x": location_x,
                "location_y": location_y,
                "under_pressure": as_bool(event.get("under_pressure")),
                "off_camera": as_bool(event.get("off_camera")),
                "out": as_bool(event.get("out")),
                "raw_event_json": json_text(event),
            }
        )

        _append_event_dimensions(event, rows)
        _append_pass(event, rows)
        _append_shot(event, rows)
        _append_carry(event, rows)
        _append_duel(event, rows)
        _append_pressure(event, rows)
        _append_foul(event, rows)
        _append_goalkeeper(event, rows)
        _append_substitution(event, rows)
        _append_relationships(event, rows)

    return rows


def _append_event_dimensions(event: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> None:
    team = event.get("team") if isinstance(event.get("team"), dict) else None
    possession_team = event.get("possession_team") if isinstance(event.get("possession_team"), dict) else None
    player = event.get("player") if isinstance(event.get("player"), dict) else None

    for team_record in (team, possession_team):
        team_id = object_id(team_record)
        if team_id is not None:
            rows["team"].append(
                {
                    "team_id": team_id,
                    "team_name": object_name(team_record),
                    "country_name": None,
                }
            )

    player_id = object_id(player)
    if player_id is not None:
        rows["player"].append(
            {
                "player_id": player_id,
                "player_name": object_name(player),
                "nickname": None,
                "country_name": None,
            }
        )


def _append_pass(event: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> None:
    pass_data = event.get("pass")
    if not isinstance(pass_data, dict):
        return
    end_x, end_y = point(pass_data.get("end_location"))
    recipient = pass_data.get("recipient") if isinstance(pass_data.get("recipient"), dict) else None
    rows["pass"].append(
        {
            "event_id": as_str(event.get("id")),
            "match_id": as_int(event.get("match_id")),
            "recipient_player_id": object_id(recipient),
            "recipient_player_name": object_name(recipient),
            "pass_length": as_float(pass_data.get("length")),
            "pass_angle": as_float(pass_data.get("angle")),
            "pass_height_id": object_id(pass_data.get("height")),
            "pass_height_name": object_name(pass_data.get("height")),
            "pass_type_id": object_id(pass_data.get("type")),
            "pass_type_name": object_name(pass_data.get("type")),
            "pass_body_part_id": object_id(pass_data.get("body_part")),
            "pass_body_part_name": object_name(pass_data.get("body_part")),
            "pass_outcome_id": object_id(pass_data.get("outcome")),
            "pass_outcome_name": object_name(pass_data.get("outcome")),
            "pass_technique_id": object_id(pass_data.get("technique")),
            "pass_technique_name": object_name(pass_data.get("technique")),
            "pass_end_x": end_x,
            "pass_end_y": end_y,
            "pass_cross": as_bool(pass_data.get("cross")),
            "pass_switch": as_bool(pass_data.get("switch")),
            "pass_shot_assist": as_bool(pass_data.get("shot_assist")),
            "pass_goal_assist": as_bool(pass_data.get("goal_assist")),
            "pass_through_ball": as_bool(pass_data.get("through_ball")),
        }
    )
    if object_id(recipient) is not None:
        rows["player"].append(
            {
                "player_id": object_id(recipient),
                "player_name": object_name(recipient),
                "nickname": None,
                "country_name": None,
            }
        )


def _append_shot(event: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> None:
    shot = event.get("shot")
    if not isinstance(shot, dict):
        return
    end_x, end_y, end_z = point3(shot.get("end_location"))
    rows["shot"].append(
        {
            "event_id": as_str(event.get("id")),
            "match_id": as_int(event.get("match_id")),
            "shot_statsbomb_xg": as_float(shot.get("statsbomb_xg")),
            "shot_outcome_id": object_id(shot.get("outcome")),
            "shot_outcome_name": object_name(shot.get("outcome")),
            "shot_body_part_id": object_id(shot.get("body_part")),
            "shot_body_part_name": object_name(shot.get("body_part")),
            "shot_technique_id": object_id(shot.get("technique")),
            "shot_technique_name": object_name(shot.get("technique")),
            "shot_type_id": object_id(shot.get("type")),
            "shot_type_name": object_name(shot.get("type")),
            "shot_end_x": end_x,
            "shot_end_y": end_y,
            "shot_end_z": end_z,
            "shot_first_time": as_bool(shot.get("first_time")),
            "shot_one_on_one": as_bool(shot.get("one_on_one")),
            "shot_key_pass_id": as_str(shot.get("key_pass_id")),
        }
    )
    for frame in shot.get("freeze_frame") or []:
        if not isinstance(frame, dict):
            continue
        player = frame.get("player") if isinstance(frame.get("player"), dict) else None
        frame_x, frame_y = point(frame.get("location"))
        rows["freeze_frame"].append(
            {
                "event_id": as_str(event.get("id")),
                "match_id": as_int(event.get("match_id")),
                "player_id": object_id(player),
                "player_name": object_name(player),
                "teammate": as_bool(frame.get("teammate")),
                "actor": as_bool(frame.get("actor")),
                "keeper": as_bool(frame.get("keeper")),
                "location_x": frame_x,
                "location_y": frame_y,
            }
        )
        if object_id(player) is not None:
            rows["player"].append(
                {
                    "player_id": object_id(player),
                    "player_name": object_name(player),
                    "nickname": None,
                    "country_name": None,
                }
            )


def _append_carry(event: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> None:
    carry = event.get("carry")
    if not isinstance(carry, dict):
        return
    end_x, end_y = point(carry.get("end_location"))
    rows["carry"].append(
        {
            "event_id": as_str(event.get("id")),
            "match_id": as_int(event.get("match_id")),
            "carry_end_x": end_x,
            "carry_end_y": end_y,
            "carry_distance": distance(event.get("location"), carry.get("end_location")),
        }
    )


def _append_duel(event: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> None:
    duel = event.get("duel")
    if not isinstance(duel, dict):
        return
    rows["duel"].append(
        {
            "event_id": as_str(event.get("id")),
            "match_id": as_int(event.get("match_id")),
            "duel_type_id": object_id(duel.get("type")),
            "duel_type_name": object_name(duel.get("type")),
            "duel_outcome_id": object_id(duel.get("outcome")),
            "duel_outcome_name": object_name(duel.get("outcome")),
        }
    )


def _append_pressure(event: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> None:
    if object_name(event.get("type")) != "Pressure" and "counterpress" not in event:
        return
    rows["pressure"].append(
        {
            "event_id": as_str(event.get("id")),
            "match_id": as_int(event.get("match_id")),
            "counterpress": as_bool(event.get("counterpress")),
        }
    )


def _append_foul(event: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> None:
    for key, foul_type in (("foul_committed", "committed"), ("foul_won", "won")):
        foul = event.get(key)
        if not isinstance(foul, dict):
            continue
        card = foul.get("card") if isinstance(foul.get("card"), dict) else None
        rows["foul"].append(
            {
                "event_id": as_str(event.get("id")),
                "match_id": as_int(event.get("match_id")),
                "foul_type": foul_type,
                "advantage": as_bool(foul.get("advantage")),
                "offensive": as_bool(foul.get("offensive")),
                "defensive": as_bool(foul.get("defensive")),
                "card_id": object_id(card),
                "card_name": object_name(card),
            }
        )


def _append_goalkeeper(event: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> None:
    goalkeeper = event.get("goalkeeper")
    if not isinstance(goalkeeper, dict):
        return
    end_x, end_y = point(goalkeeper.get("end_location"))
    rows["goalkeeper_action"].append(
        {
            "event_id": as_str(event.get("id")),
            "match_id": as_int(event.get("match_id")),
            "goalkeeper_type_id": object_id(goalkeeper.get("type")),
            "goalkeeper_type_name": object_name(goalkeeper.get("type")),
            "goalkeeper_outcome_id": object_id(goalkeeper.get("outcome")),
            "goalkeeper_outcome_name": object_name(goalkeeper.get("outcome")),
            "goalkeeper_position_id": object_id(goalkeeper.get("position")),
            "goalkeeper_position_name": object_name(goalkeeper.get("position")),
            "goalkeeper_technique_id": object_id(goalkeeper.get("technique")),
            "goalkeeper_technique_name": object_name(goalkeeper.get("technique")),
            "goalkeeper_body_part_id": object_id(goalkeeper.get("body_part")),
            "goalkeeper_body_part_name": object_name(goalkeeper.get("body_part")),
            "goalkeeper_end_x": end_x,
            "goalkeeper_end_y": end_y,
        }
    )


def _append_substitution(event: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> None:
    substitution = event.get("substitution")
    if not isinstance(substitution, dict):
        return
    replacement = substitution.get("replacement") if isinstance(substitution.get("replacement"), dict) else None
    rows["substitution"].append(
        {
            "event_id": as_str(event.get("id")),
            "match_id": as_int(event.get("match_id")),
            "replacement_player_id": object_id(replacement),
            "replacement_player_name": object_name(replacement),
            "substitution_outcome_id": object_id(substitution.get("outcome")),
            "substitution_outcome_name": object_name(substitution.get("outcome")),
        }
    )
    if object_id(replacement) is not None:
        rows["player"].append(
            {
                "player_id": object_id(replacement),
                "player_name": object_name(replacement),
                "nickname": None,
                "country_name": None,
            }
        )


def _append_relationships(event: dict[str, Any], rows: dict[str, list[dict[str, Any]]]) -> None:
    related_events = event.get("related_events")
    if not isinstance(related_events, list):
        return
    for related_event_id in related_events:
        rows["event_relationship"].append(
            {
                "source_event_id": as_str(event.get("id")),
                "related_event_id": as_str(related_event_id),
                "match_id": as_int(event.get("match_id")),
                "relationship_type": "related",
            }
        )
