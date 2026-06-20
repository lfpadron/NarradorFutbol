"""Normalize StatsBomb lineup JSON files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config import RAW_LINEUPS_DIR
from src.transform.utils import (
    LINEUP_FILE_RE,
    as_bool,
    as_int,
    as_str,
    load_records,
    match_id_from_path,
    nested_get,
)


def normalize_lineups_for_match(match_id: int, raw_lineups_dir: Path = RAW_LINEUPS_DIR) -> dict[str, list[dict[str, Any]]]:
    path = raw_lineups_dir / f"lineups.match-{match_id}.json"
    if not path.exists():
        return {"lineup": [], "team": [], "player": []}
    return normalize_lineups_file(path)


def normalize_lineups_file(path: Path) -> dict[str, list[dict[str, Any]]]:
    match_id = match_id_from_path(path, LINEUP_FILE_RE)
    lineup_rows: list[dict[str, Any]] = []
    team_rows: list[dict[str, Any]] = []
    player_rows: list[dict[str, Any]] = []

    for team_record in load_records(path):
        team_id = as_int(team_record.get("team_id"))
        team_name = as_str(team_record.get("team_name"))
        team_rows.append({"team_id": team_id, "team_name": team_name, "country_name": None})

        for player in team_record.get("lineup") or []:
            if not isinstance(player, dict):
                continue
            player_id = as_int(player.get("player_id"))
            player_name = as_str(player.get("player_name"))
            position = _primary_position(player.get("positions"))

            lineup_rows.append(
                {
                    "match_id": match_id,
                    "team_id": team_id,
                    "team_name": team_name,
                    "player_id": player_id,
                    "player_name": player_name,
                    "jersey_number": as_int(player.get("jersey_number")),
                    "position_name": as_str(position.get("position") or position.get("position_name")),
                    "starter": _starter_from_positions(player.get("positions")),
                }
            )
            player_rows.append(
                {
                    "player_id": player_id,
                    "player_name": player_name,
                    "nickname": as_str(player.get("player_nickname") or player.get("nickname")),
                    "country_name": as_str(nested_get(player, "country", "name")),
                }
            )

    return {"lineup": lineup_rows, "team": team_rows, "player": player_rows}


def _primary_position(positions: Any) -> dict[str, Any]:
    if not isinstance(positions, list) or not positions:
        return {}
    starters = [
        position
        for position in positions
        if isinstance(position, dict)
        and (
            position.get("start_reason") == "Starting XI"
            or position.get("from") == "00:00"
            or as_bool(position.get("starter")) is True
        )
    ]
    if starters:
        return starters[0]
    return positions[0] if isinstance(positions[0], dict) else {}


def _starter_from_positions(positions: Any) -> bool | None:
    if not isinstance(positions, list) or not positions:
        return None
    for position in positions:
        if not isinstance(position, dict):
            continue
        if position.get("start_reason") == "Starting XI" or position.get("from") == "00:00":
            return True
    return False
