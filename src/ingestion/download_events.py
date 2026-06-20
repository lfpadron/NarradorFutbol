"""Download StatsBomb events for a match."""

from __future__ import annotations

from pathlib import Path

from src.config import RAW_EVENTS_DIR
from src.ingestion.utils import (
    DownloadResult,
    count_records,
    read_json,
    statsbomb_call,
    write_json,
)


def events_file_path(match_id: int) -> Path:
    return RAW_EVENTS_DIR / f"events.match-{match_id}.json"


def download_events(match_id: int, force: bool = False) -> DownloadResult:
    path = events_file_path(match_id)

    if path.exists() and not force:
        data = read_json(path)
        return DownloadResult(
            status="skipped_existing",
            path=path,
            data=data,
            rows=count_records(data),
        )

    data = statsbomb_call("events", match_id=match_id)
    rows = count_records(data)
    write_json(path, data)
    return DownloadResult(
        status="downloaded",
        path=path,
        data=data,
        rows=rows,
    )
