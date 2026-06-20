"""Download matches and build the master matches index."""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import pandas as pd

from src.config import ALL_MATCHES_CSV, ALL_MATCHES_PARQUET, RAW_MATCHES_DIR
from src.ingestion.utils import (
    DownloadResult,
    as_int,
    coerce_records,
    pick_first,
    read_json,
    statsbomb_call,
    to_jsonable,
    write_json,
)


MATCH_FILE_RE = re.compile(r"competition-(?P<competition_id>\d+)\.season-(?P<season_id>\d+)\.json$")


def match_file_path(competition_id: int, season_id: int) -> Path:
    return RAW_MATCHES_DIR / f"competition-{competition_id}.season-{season_id}.json"


def competition_pairs(competitions_data: Any) -> list[tuple[int, int]]:
    pairs: set[tuple[int, int]] = set()
    for record in coerce_records(competitions_data):
        competition_id = as_int(pick_first(record, "competition_id"))
        season_id = as_int(pick_first(record, "season_id"))
        if competition_id is not None and season_id is not None:
            pairs.add((competition_id, season_id))
    return sorted(pairs)


def download_matches(competition_id: int, season_id: int, force: bool = False) -> DownloadResult:
    path = match_file_path(competition_id, season_id)

    if path.exists() and not force:
        data = read_json(path)
        return DownloadResult(
            status="skipped_existing",
            path=path,
            data=data,
            rows=len(coerce_records(data)),
        )

    data = statsbomb_call(
        "matches",
        competition_id=competition_id,
        season_id=season_id,
    )
    write_json(path, data)
    return DownloadResult(
        status="downloaded",
        path=path,
        data=data,
        rows=len(coerce_records(data)),
    )


def _ids_from_match_path(path: Path) -> tuple[int | None, int | None]:
    match = MATCH_FILE_RE.search(path.name)
    if not match:
        return None, None
    return int(match.group("competition_id")), int(match.group("season_id"))


def _json_string(value: Any) -> str:
    return json.dumps(to_jsonable(value), ensure_ascii=False)


def _prepare_for_parquet(df: pd.DataFrame) -> pd.DataFrame:
    clean = df.copy()
    for column in clean.columns:
        if clean[column].map(lambda value: isinstance(value, (dict, list, tuple, set))).any():
            clean[column] = clean[column].map(
                lambda value: _json_string(value)
                if isinstance(value, (dict, list, tuple, set))
                else value
            )
    return clean


def build_master_matches_index() -> pd.DataFrame:
    records: list[dict[str, Any]] = []

    for path in sorted(RAW_MATCHES_DIR.glob("competition-*.season-*.json")):
        competition_id, season_id = _ids_from_match_path(path)
        data = read_json(path)
        for record in coerce_records(data):
            record = dict(record)
            record.setdefault("competition_id", competition_id)
            record.setdefault("season_id", season_id)
            record["source_file"] = path.as_posix()
            records.append(record)

    if records:
        df = pd.json_normalize(records, sep="_")
    else:
        df = pd.DataFrame(
            columns=[
                "match_id",
                "competition_id",
                "season_id",
                "match_date",
                "home_team_home_team_name",
                "away_team_away_team_name",
                "source_file",
            ]
        )

    for column in ("match_id", "competition_id", "season_id"):
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce").astype("Int64")

    sort_columns = [
        column
        for column in ("competition_id", "season_id", "match_date", "match_id")
        if column in df.columns
    ]
    if sort_columns:
        df = df.sort_values(sort_columns, kind="stable")

    df = df.reset_index(drop=True)
    output_df = _prepare_for_parquet(df)

    ALL_MATCHES_CSV.parent.mkdir(parents=True, exist_ok=True)
    output_df.to_csv(ALL_MATCHES_CSV, index=False)
    output_df.to_parquet(ALL_MATCHES_PARQUET, index=False)

    return output_df
