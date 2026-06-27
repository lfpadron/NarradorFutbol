"""Normalize raw StatsBomb match files."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from src.config import RAW_MATCHES_DIR
from src.transform.utils import as_int, as_str, load_records, nested_get

MATCH_FILE_RE = re.compile(r"competition-(?P<competition_id>\d+)\.season-(?P<season_id>\d+)\.json$")


def normalize_matches(raw_matches_dir: Path = RAW_MATCHES_DIR) -> dict[str, list[dict[str, Any]]]:
    match_rows: dict[int, dict[str, Any]] = {}
    team_rows: dict[int, dict[str, Any]] = {}

    for path in sorted(raw_matches_dir.glob("competition-*.season-*.json")):
        file_competition_id, file_season_id = _ids_from_path(path)
        for record in load_records(path):
            match_id = as_int(record.get("match_id"))
            if match_id is None:
                continue

            competition = record.get("competition") if isinstance(record.get("competition"), dict) else {}
            season = record.get("season") if isinstance(record.get("season"), dict) else {}
            home_team = record.get("home_team") if isinstance(record.get("home_team"), dict) else {}
            away_team = record.get("away_team") if isinstance(record.get("away_team"), dict) else {}

            home_team_id = as_int(home_team.get("home_team_id") or home_team.get("team_id") or home_team.get("id"))
            away_team_id = as_int(away_team.get("away_team_id") or away_team.get("team_id") or away_team.get("id"))
            home_team_name = as_str(
                home_team.get("home_team_name") or home_team.get("team_name") or home_team.get("name")
            )
            away_team_name = as_str(
                away_team.get("away_team_name") or away_team.get("team_name") or away_team.get("name")
            )

            match_rows[match_id] = {
                "match_id": match_id,
                "competition_id": as_int(competition.get("competition_id")) or file_competition_id,
                "season_id": as_int(season.get("season_id")) or file_season_id,
                "match_date": as_str(record.get("match_date")),
                "kick_off": as_str(record.get("kick_off")),
                "home_team_id": home_team_id,
                "home_team_name": home_team_name,
                "away_team_id": away_team_id,
                "away_team_name": away_team_name,
                "home_score": as_int(record.get("home_score")),
                "away_score": as_int(record.get("away_score")),
                "stadium_name": as_str(nested_get(record, "stadium", "name")),
                "referee_name": as_str(nested_get(record, "referee", "name")),
                "match_status": as_str(record.get("match_status")),
                "data_version": as_str(nested_get(record, "metadata", "data_version")),
            }

            if home_team_id is not None:
                team_rows[home_team_id] = {
                    "team_id": home_team_id,
                    "team_name": home_team_name,
                    "country_name": as_str(nested_get(home_team, "country", "name")),
                }
            if away_team_id is not None:
                team_rows[away_team_id] = {
                    "team_id": away_team_id,
                    "team_name": away_team_name,
                    "country_name": as_str(nested_get(away_team, "country", "name")),
                }

    return {"match": list(match_rows.values()), "team": list(team_rows.values())}


def _ids_from_path(path: Path) -> tuple[int | None, int | None]:
    match = MATCH_FILE_RE.search(path.name)
    if not match:
        return None, None
    return as_int(match.group("competition_id")), as_int(match.group("season_id"))
