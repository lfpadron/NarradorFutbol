"""Shared helpers for StatsBomb raw-to-analytics transforms."""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from typing import Any

import duckdb
import pandas as pd

from src.ingestion.utils import read_json, to_jsonable


EVENT_FILE_RE = re.compile(r"events\.match-(?P<match_id>\d+)\.json$")
LINEUP_FILE_RE = re.compile(r"lineups\.match-(?P<match_id>\d+)\.json$")
THREE_SIXTY_FILE_RE = re.compile(r"three-sixty\.match-(?P<match_id>\d+)\.json$")


def records_from_json(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, list):
        return [item for item in data if isinstance(item, dict)]
    if isinstance(data, dict):
        if data and all(isinstance(item, dict) for item in data.values()):
            return list(data.values())
        return [data]
    return []


def load_records(path: Path) -> list[dict[str, Any]]:
    return records_from_json(read_json(path))


def nested_get(data: dict[str, Any] | None, *keys: str) -> Any:
    current: Any = data
    for key in keys:
        if not isinstance(current, dict):
            return None
        current = current.get(key)
    return current


def object_id(data: dict[str, Any] | None) -> int | None:
    return as_int(nested_get(data, "id"))


def object_name(data: dict[str, Any] | None) -> str | None:
    return as_str(nested_get(data, "name"))


def as_int(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def as_float(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def as_bool(value: Any) -> bool | None:
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        lowered = value.lower()
        if lowered in {"true", "1", "yes"}:
            return True
        if lowered in {"false", "0", "no"}:
            return False
    return bool(value)


def as_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    return str(value)


def point(values: Any) -> tuple[float | None, float | None]:
    if isinstance(values, (list, tuple)) and len(values) >= 2:
        return as_float(values[0]), as_float(values[1])
    return None, None


def point3(values: Any) -> tuple[float | None, float | None, float | None]:
    if isinstance(values, (list, tuple)):
        x = as_float(values[0]) if len(values) >= 1 else None
        y = as_float(values[1]) if len(values) >= 2 else None
        z = as_float(values[2]) if len(values) >= 3 else None
        return x, y, z
    return None, None, None


def distance(start: Any, end: Any) -> float | None:
    start_x, start_y = point(start)
    end_x, end_y = point(end)
    if None in (start_x, start_y, end_x, end_y):
        return None
    return math.dist((start_x, start_y), (end_x, end_y))


def json_text(value: Any) -> str | None:
    if value is None:
        return None
    return json.dumps(to_jsonable(value), ensure_ascii=False)


def match_id_from_path(path: Path, pattern: re.Pattern[str]) -> int | None:
    match = pattern.search(path.name)
    if not match:
        return None
    return as_int(match.group("match_id"))


def quote_identifier(name: str) -> str:
    return '"' + name.replace('"', '""') + '"'


def dataframe_for_rows(rows: list[dict[str, Any]], columns: list[str]) -> pd.DataFrame:
    frame = pd.DataFrame(rows)
    for column in columns:
        if column not in frame.columns:
            frame[column] = None
    return frame[columns]


def insert_rows(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    rows: list[dict[str, Any]],
    columns: list[str],
) -> int:
    if not rows:
        return 0
    frame = dataframe_for_rows(rows, columns)
    temp_name = f"tmp_{table_name.replace('-', '_')}"
    connection.register(temp_name, frame)
    try:
        connection.execute(
            f"INSERT INTO {quote_identifier(table_name)} BY NAME "
            f"SELECT * FROM {quote_identifier(temp_name)}"
        )
    finally:
        connection.unregister(temp_name)
    return len(frame)


def replace_dimension_rows(
    connection: duckdb.DuckDBPyConnection,
    table_name: str,
    rows: list[dict[str, Any]],
    columns: list[str],
    key_columns: list[str],
) -> int:
    if not rows:
        return 0
    frame = dataframe_for_rows(dedupe_rows(rows, key_columns), columns)
    temp_name = f"tmp_{table_name.replace('-', '_')}_dim"
    target = quote_identifier(table_name)
    temp = quote_identifier(temp_name)
    predicates = " AND ".join(
        f"{target}.{quote_identifier(column)} = {temp}.{quote_identifier(column)}"
        for column in key_columns
    )
    connection.register(temp_name, frame)
    try:
        connection.execute(f"DELETE FROM {target} USING {temp} WHERE {predicates}")
        connection.execute(f"INSERT INTO {target} BY NAME SELECT * FROM {temp}")
    finally:
        connection.unregister(temp_name)
    return len(frame)


def dedupe_rows(rows: list[dict[str, Any]], key_columns: list[str]) -> list[dict[str, Any]]:
    deduped: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = tuple(row.get(column) for column in key_columns)
        if any(value is None for value in key):
            continue
        existing = deduped.get(key, {})
        merged = dict(existing)
        for column, value in row.items():
            if value is not None or column not in merged:
                merged[column] = value
        deduped[key] = merged
    return list(deduped.values())
