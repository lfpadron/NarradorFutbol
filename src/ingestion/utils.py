"""Shared ingestion helpers."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import urlopen


VALID_STATUSES = {
    "pending",
    "downloaded",
    "skipped_existing",
    "failed",
    "not_available",
    "transformed",
}

OPEN_DATA_BASE_URL = (
    "https://raw.githubusercontent.com/statsbomb/open-data/master/data"
)


@dataclass(frozen=True)
class DownloadResult:
    status: str
    path: Path | None
    data: Any = None
    rows: int | None = None
    error_message: str | None = None
    has_data: bool | None = None


def to_jsonable(value: Any) -> Any:
    """Convert common Python and pandas-ish values into JSON-safe values."""

    if value is None:
        return None

    if isinstance(value, float) and math.isnan(value):
        return None

    if isinstance(value, (str, int, bool)):
        return value

    if isinstance(value, float):
        return value

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if hasattr(value, "item"):
        try:
            return to_jsonable(value.item())
        except (TypeError, ValueError):
            pass

    if hasattr(value, "isoformat"):
        try:
            return value.isoformat()
        except (TypeError, ValueError):
            pass

    if hasattr(value, "to_dict"):
        try:
            records = value.to_dict(orient="records")
            return to_jsonable(records)
        except TypeError:
            try:
                return to_jsonable(value.to_dict())
            except TypeError:
                pass

    if isinstance(value, dict):
        return {str(key): to_jsonable(item) for key, item in value.items()}

    if isinstance(value, (list, tuple, set)):
        return [to_jsonable(item) for item in value]

    return str(value)


def write_json(path: Path, data: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(data), file, ensure_ascii=False, indent=2)
        file.write("\n")


def read_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as file:
        return json.load(file)


def coerce_records(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []

    if hasattr(data, "to_dict"):
        try:
            data = data.to_dict(orient="records")
        except TypeError:
            data = data.to_dict()

    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]

    if isinstance(data, dict):
        if "data" in data and isinstance(data["data"], list):
            return [item for item in data["data"] if isinstance(item, dict)]
        if data and all(isinstance(item, dict) for item in data.values()):
            return list(data.values())
        return [data]

    return []


def count_records(data: Any) -> int:
    if data is None:
        return 0

    if hasattr(data, "__len__") and not isinstance(data, (str, bytes, dict)):
        return len(data)

    if isinstance(data, dict):
        if data and all(isinstance(item, dict) for item in data.values()):
            return len(data)
        if data and all(isinstance(item, list) for item in data.values()):
            return sum(len(item) for item in data.values())
        return 1

    return 0


def has_records(data: Any) -> bool:
    return count_records(data) > 0


def statsbomb_call(function_name: str, *args: Any, **kwargs: Any) -> Any:
    """Call statsbombpy, preferring its dict/raw-like format when available."""

    try:
        from statsbombpy import sb
    except ImportError as exc:
        raise RuntimeError(
            "statsbombpy is not installed. Run `pip install -r requirements.txt`."
        ) from exc

    func = getattr(sb, function_name)
    try:
        return func(*args, fmt="dict", **kwargs)
    except TypeError as exc:
        message = str(exc)
        if "fmt" not in message and "unexpected keyword" not in message:
            raise
        return func(*args, **kwargs)


def fetch_open_data_json(relative_path: str) -> Any:
    url = f"{OPEN_DATA_BASE_URL}/{relative_path.lstrip('/')}"
    try:
        with urlopen(url, timeout=60) as response:
            return json.load(response)
    except HTTPError:
        raise


def is_not_available_error(error: BaseException) -> bool:
    message = str(error).lower()
    return any(
        token in message
        for token in (
            "404",
            "not found",
            "no such file",
            "not available",
            "no 360",
        )
    )


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def pick_first(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            value = mapping[key]
            if value is not None and not (isinstance(value, float) and math.isnan(value)):
                return value
    return None
