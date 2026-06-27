"""DuckDB-backed report generation history."""

from __future__ import annotations

import os
from typing import Any
from uuid import uuid4

import duckdb

from src.config import REPORT_HISTORY_DB_PATH
from src.ingestion.utils import to_jsonable

REPORT_HISTORY_DB = REPORT_HISTORY_DB_PATH


SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS report_history (
    report_id VARCHAR PRIMARY KEY,
    match_id BIGINT,
    tone VARCHAR,
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
    warnings_count BIGINT,
    quality_overall_score BIGINT,
    error_message VARCHAR
)
"""


def record_report_generation(record: dict[str, Any]) -> None:
    REPORT_HISTORY_DB.parent.mkdir(parents=True, exist_ok=True)
    clean = _normalize_record(record)
    with duckdb.connect(str(REPORT_HISTORY_DB)) as connection:
        connection.execute(SCHEMA_SQL)
        connection.execute(
            """
            INSERT OR REPLACE INTO report_history VALUES (
                ?, ?, ?, CAST(? AS TIMESTAMP), ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
            """,
            [
                clean["report_id"],
                clean["match_id"],
                clean["tone"],
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
                clean["warnings_count"],
                clean["quality_overall_score"],
                clean["error_message"],
            ],
        )


def list_report_history(limit: int = 50) -> list[dict[str, Any]]:
    return _query_history(
        """
        SELECT *
        FROM report_history
        ORDER BY generated_at DESC
        LIMIT ?
        """,
        [limit],
    )


def get_report_history_for_match(match_id: int) -> list[dict[str, Any]]:
    return _query_history(
        """
        SELECT *
        FROM report_history
        WHERE match_id = ?
        ORDER BY generated_at DESC
        """,
        [match_id],
    )


def build_history_record(
    report: dict[str, Any],
    save_result: dict[str, Any],
    use_api: bool,
) -> dict[str, Any]:
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
        "report_id": str(uuid4()),
        "match_id": report.get("match_id"),
        "tone": report.get("tone"),
        "generated_at": (
            save_result.get("exported_at_utc") or save_result.get("exported_at") or report.get("generated_at")
        ),
        "generated_by": get_generated_by(),
        "use_api": use_api,
        "model": report.get("narrative", {}).get("model"),
        "status": status,
        "markdown_path": save_result.get("markdown"),
        "html_path": save_result.get("html"),
        "json_path": save_result.get("json"),
        "pdf_path": save_result.get("pdf"),
        "docx_path": save_result.get("docx"),
        "pdf_status": pdf_status,
        "docx_status": docx_status,
        "warnings_count": len(report.get("warnings", [])),
        "quality_overall_score": report.get("quality", {}).get("overall_score"),
        "error_message": " | ".join(errors) if errors else None,
    }


def get_generated_by() -> str:
    value = os.getenv("NARRADOR_USER_EMAIL", "").strip()
    return value or "local_user"


def _normalize_record(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "report_id": record.get("report_id") or str(uuid4()),
        "match_id": int(record.get("match_id")),
        "tone": record.get("tone"),
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
        "warnings_count": int(record.get("warnings_count") or 0),
        "quality_overall_score": (
            int(record["quality_overall_score"]) if record.get("quality_overall_score") is not None else None
        ),
        "error_message": record.get("error_message"),
    }


def _query_history(sql: str, params: list[Any]) -> list[dict[str, Any]]:
    if not REPORT_HISTORY_DB.exists():
        return []
    with duckdb.connect(str(REPORT_HISTORY_DB), read_only=True) as connection:
        frame = connection.execute(sql, params).fetchdf()
    clean = frame.astype(object).where(frame.notnull(), None)
    return [to_jsonable(row) for row in clean.to_dict(orient="records")]
