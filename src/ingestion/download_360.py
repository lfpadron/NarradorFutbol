"""Download StatsBomb 360 frames when available."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config import RAW_THREE_SIXTY_DIR
from src.ingestion.utils import (
    DownloadResult,
    fetch_open_data_json,
    has_records,
    is_not_available_error,
    read_json,
    statsbomb_call,
    write_json,
)


def three_sixty_file_path(match_id: int) -> Path:
    return RAW_THREE_SIXTY_DIR / f"three-sixty.match-{match_id}.json"


def _fetch_three_sixty(match_id: int) -> Any:
    try:
        return statsbomb_call("frames", match_id=match_id)
    except AttributeError:
        return fetch_open_data_json(f"three-sixty/{match_id}.json")


def download_three_sixty(match_id: int, force: bool = False) -> DownloadResult:
    path = three_sixty_file_path(match_id)

    if path.exists() and not force:
        data = read_json(path)
        return DownloadResult(
            status="skipped_existing",
            path=path,
            data=data,
            has_data=True,
        )

    try:
        data = _fetch_three_sixty(match_id)
    except Exception as exc:
        if is_not_available_error(exc):
            return DownloadResult(
                status="not_available",
                path=None,
                data=None,
                error_message=None,
                has_data=False,
            )
        raise

    if not has_records(data):
        return DownloadResult(
            status="not_available",
            path=None,
            data=data,
            error_message=None,
            has_data=False,
        )

    write_json(path, data)
    return DownloadResult(
        status="downloaded",
        path=path,
        data=data,
        has_data=True,
    )
