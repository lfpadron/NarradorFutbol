"""Download StatsBomb competitions."""

from __future__ import annotations

from src.config import COMPETITIONS_FILE
from src.ingestion.utils import DownloadResult, read_json, statsbomb_call, write_json


def download_competitions(force: bool = False) -> DownloadResult:
    if COMPETITIONS_FILE.exists() and not force:
        data = read_json(COMPETITIONS_FILE)
        return DownloadResult(
            status="skipped_existing",
            path=COMPETITIONS_FILE,
            data=data,
            rows=len(data) if isinstance(data, list) else None,
        )

    data = statsbomb_call("competitions")
    write_json(COMPETITIONS_FILE, data)
    rows = len(data) if isinstance(data, list) else None
    return DownloadResult(
        status="downloaded",
        path=COMPETITIONS_FILE,
        data=data,
        rows=rows,
    )
