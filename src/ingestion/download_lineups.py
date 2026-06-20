"""Download StatsBomb lineups for a match."""

from __future__ import annotations

from pathlib import Path

from src.config import RAW_LINEUPS_DIR
from src.ingestion.utils import DownloadResult, count_records, read_json, statsbomb_call, write_json


def lineups_file_path(match_id: int) -> Path:
    return RAW_LINEUPS_DIR / f"lineups.match-{match_id}.json"


def download_lineups(match_id: int, force: bool = False) -> DownloadResult:
    path = lineups_file_path(match_id)

    if path.exists() and not force:
        data = read_json(path)
        return DownloadResult(
            status="skipped_existing",
            path=path,
            data=data,
            rows=count_records(data),
        )

    data = statsbomb_call("lineups", match_id=match_id)
    rows = count_records(data)
    write_json(path, data)
    return DownloadResult(
        status="downloaded",
        path=path,
        data=data,
        rows=rows,
    )
