"""Normalize raw StatsBomb competitions into competition and season rows."""

from __future__ import annotations

from pathlib import Path

from src.config import COMPETITIONS_FILE
from src.transform.utils import as_bool, as_int, as_str, load_records


def normalize_competitions(path: Path = COMPETITIONS_FILE) -> dict[str, list[dict[str, object]]]:
    competition_rows: dict[int, dict[str, object]] = {}
    season_rows: dict[tuple[int, int], dict[str, object]] = {}

    if not path.exists():
        return {"competition": [], "season": []}

    for record in load_records(path):
        competition_id = as_int(record.get("competition_id"))
        season_id = as_int(record.get("season_id"))
        if competition_id is None:
            continue

        competition_rows[competition_id] = {
            "competition_id": competition_id,
            "competition_name": as_str(record.get("competition_name")),
            "country_name": as_str(record.get("country_name")),
            "competition_gender": as_str(record.get("competition_gender")),
            "competition_youth": as_bool(record.get("competition_youth")),
            "competition_international": as_bool(record.get("competition_international")),
        }

        if season_id is not None:
            season_rows[(competition_id, season_id)] = {
                "season_id": season_id,
                "season_name": as_str(record.get("season_name")),
                "competition_id": competition_id,
            }

    return {
        "competition": list(competition_rows.values()),
        "season": list(season_rows.values()),
    }
