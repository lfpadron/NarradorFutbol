"""DuckDB-backed Scouting AI report history."""

from __future__ import annotations

import os
import time
from typing import Any
from uuid import uuid4

import duckdb

from src.config import SCOUTING_HISTORY_DB_PATH
from src.ingestion.utils import to_jsonable


SCOUTING_HISTORY_DB = SCOUTING_HISTORY_DB_PATH


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS scouting_history (
    scouting_id VARCHAR PRIMARY KEY,
    mode VARCHAR,
    match_id_a BIGINT,
    player_id_a BIGINT,
    player_name_a VARCHAR,
    match_id_b BIGINT,
    player_id_b BIGINT,
    player_name_b VARCHAR,
    generated_at TIMESTAMP,
    generated_by VARCHAR,
    use_api BOOLEAN,
    model VARCHAR,
    status VARCHAR,
    markdown_path VARCHAR,
    html_path VARCHAR,
    json_path VARCHAR,
    pdf_path VARCHAR,
    docx_path VARCHAR,
    pdf_status VARCHAR,
    docx_status VARCHAR,
    language_warnings_count BIGINT,
    error_message VARCHAR
)
"""


def record_scouting_generation(record: dict[str, Any]) -> None:
    SCOUTING_HISTORY_DB.parent.mkdir(parents=True, exist_ok=True)
    clean = _normalize_record(record)
    last_error: Exception | None = None
    for attempt in range(4):
        try:
            with duckdb.connect(str(SCOUTING_HISTORY_DB)) as connection:
                connection.execute(SCHEMA_SQL)
                connection.execute(
                    """
                    INSERT OR REPLACE INTO scouting_history VALUES (
                        ?, ?, ?, ?, ?, ?, ?, ?, CAST(? AS TIMESTAMP), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
                    )
                    """,
                    [
                        clean["scouting_id"],
                        clean["mode"],
                        clean["match_id_a"],
                        clean["player_id_a"],
                        clean["player_name_a"],
                        clean["match_id_b"],
                        clean["player_id_b"],
                        clean["player_name_b"],
                        clean["generated_at"],
                        clean["generated_by"],
                        clean["use_api"],
                        clean["model"],
                        clean["status"],
                        clean["markdown_path"],
                        clean["html_path"],
                        clean["json_path"],
                        clean["pdf_path"],
                        clean["docx_path"],
                        clean["pdf_status"],
                        clean["docx_status"],
                        clean["language_warnings_count"],
                        clean["error_message"],
                    ],
                )
            return
        except duckdb.IOException as exc:
            last_error = exc
            time.sleep(0.35 * (attempt + 1))
    if last_error is not None:
        raise last_error


def build_scouting_history_record(
    scouting_result: dict[str, Any],
    save_result: dict[str, Any],
    use_api: bool,
) -> dict[str, Any]:
    summary = scouting_result.get("context_summary", {})
    errors = []
    for key in ("pdf_result", "docx_result"):
        result = save_result.get(key, {})
        if result.get("status") == "failed" and result.get("error_message"):
            errors.append(f"{key}: {result.get('error_message')}")

    pdf_status = save_result.get("pdf_status", "not_requested")
    docx_status = save_result.get("docx_status", "not_requested")
    status = "generated"
    if pdf_status == "failed" or docx_status == "failed":
        status = "partial"

    return {
        "scouting_id": str(uuid4()),
        "mode": scouting_result.get("mode"),
        "match_id_a": scouting_result.get("match_id_a"),
        "player_id_a": scouting_result.get("player_id_a"),
        "player_name_a": summary.get("player_a"),
        "match_id_b": scouting_result.get("match_id_b"),
        "player_id_b": scouting_result.get("player_id_b"),
        "player_name_b": summary.get("player_b"),
        "generated_at": (
            save_result.get("exported_at_utc")
            or save_result.get("exported_at")
            or scouting_result.get("generated_at")
        ),
        "generated_by": get_generated_by(),
        "use_api": use_api,
        "model": scouting_result.get("model"),
        "status": status,
        "markdown_path": save_result.get("markdown"),
        "html_path": save_result.get("html"),
        "json_path": save_result.get("json"),
        "pdf_path": save_result.get("pdf"),
        "docx_path": save_result.get("docx"),
        "pdf_status": pdf_status,
        "docx_status": docx_status,
        "language_warnings_count": len(scouting_result.get("language_warnings", [])),
        "error_message": " | ".join(errors) if errors else None,
    }


def list_scouting_history(limit: int = 50, player_id: int | None = None) -> list[dict[str, Any]]:
    if player_id is None:
        return _query_history(
            """
            SELECT *
            FROM scouting_history
            ORDER BY generated_at DESC
            LIMIT ?
            """,
            [limit],
        )
    return _query_history(
        """
        SELECT *
        FROM scouting_history
        WHERE player_id_a = ? OR player_id_b = ?
        ORDER BY generated_at DESC
        LIMIT ?
        """,
        [player_id, player_id, limit],
    )


def get_generated_by() -> str:
    value = os.getenv("NARRADOR_USER_EMAIL", "").strip()
    return value or "local_user"


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "scouting_id": record.get("scouting_id") or str(uuid4()),
        "mode": record.get("mode") or "individual",
        "match_id_a": _optional_int(record.get("match_id_a")),
        "player_id_a": _optional_int(record.get("player_id_a")),
        "player_name_a": record.get("player_name_a"),
        "match_id_b": _optional_int(record.get("match_id_b")),
        "player_id_b": _optional_int(record.get("player_id_b")),
        "player_name_b": record.get("player_name_b"),
        "generated_at": record.get("generated_at"),
        "generated_by": record.get("generated_by") or get_generated_by(),
        "use_api": bool(record.get("use_api")),
        "model": record.get("model"),
        "status": record.get("status") or "generated",
        "markdown_path": record.get("markdown_path"),
        "html_path": record.get("html_path"),
        "json_path": record.get("json_path"),
        "pdf_path": record.get("pdf_path"),
        "docx_path": record.get("docx_path"),
        "pdf_status": record.get("pdf_status") or "not_requested",
        "docx_status": record.get("docx_status") or "not_requested",
        "language_warnings_count": int(record.get("language_warnings_count") or 0),
        "error_message": record.get("error_message"),
    }


def _optional_int(value: Any) -> int | None:
    if value in (None, ""):
        return None
    return int(value)


def _query_history(sql: str, params: list[Any]) -> list[dict[str, Any]]:
    if not SCOUTING_HISTORY_DB.exists():
        return []
    with duckdb.connect(str(SCOUTING_HISTORY_DB), read_only=True) as connection:
        frame = connection.execute(sql, params).fetchdf()
    clean = frame.astype(object).where(frame.notnull(), None)
    return [to_jsonable(row) for row in clean.to_dict(orient="records")]
