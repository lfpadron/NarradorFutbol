"""DuckDB helpers for the analytics layer."""

from __future__ import annotations

from typing import Any, Sequence

import duckdb
import pandas as pd

from src.config import ANALYTICS_DB
from src.ingestion.utils import to_jsonable


class AnalyticsDatabaseError(RuntimeError):
    """Raised when the analytics DuckDB database cannot satisfy a query."""


def get_connection() -> duckdb.DuckDBPyConnection:
    if not ANALYTICS_DB.exists():
        raise AnalyticsDatabaseError(
            "Analytics database not found. Run "
            "`uv run python -m src.transform.build_duckdb --limit 3 --force` first."
        )
    try:
        return duckdb.connect(str(ANALYTICS_DB), read_only=True)
    except duckdb.Error as exc:
        raise AnalyticsDatabaseError(f"Could not open analytics database: {exc}") from exc


def query_df(sql: str, params: Sequence[Any] | None = None) -> pd.DataFrame:
    try:
        with get_connection() as connection:
            return connection.execute(sql, params or []).fetchdf()
    except duckdb.CatalogException as exc:
        raise AnalyticsDatabaseError(
            "Analytics schema is missing a table or column. Rebuild with "
            "`uv run python -m src.transform.build_duckdb --force`. "
            f"Details: {exc}"
        ) from exc
    except duckdb.Error as exc:
        raise AnalyticsDatabaseError(f"Analytics query failed: {exc}") from exc


def query_one(sql: str, params: Sequence[Any] | None = None) -> dict[str, Any] | None:
    frame = query_df(sql, params)
    if frame.empty:
        return None
    return df_to_records(frame.head(1))[0]


def query_records(sql: str, params: Sequence[Any] | None = None) -> list[dict[str, Any]]:
    return df_to_records(query_df(sql, params))


def df_to_records(frame: pd.DataFrame) -> list[dict[str, Any]]:
    clean = frame.astype(object).where(pd.notnull(frame), None)
    return [to_jsonable(row) for row in clean.to_dict(orient="records")]
