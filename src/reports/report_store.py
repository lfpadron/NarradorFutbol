"""Persist final match reports."""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.config import REPORTS_DIR, project_relative
from src.ingestion.utils import to_jsonable
from src.reports.docx_report import render_docx_report
from src.reports.pdf_report import render_pdf_report


def save_report(
    report: dict[str, Any],
    markdown_text: str,
    html_text: str,
    include_pdf: bool = False,
    include_docx: bool = False,
) -> dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    match_id = report["match_id"]
    tone = _safe_token(str(report["tone"]))
    exported_at, export_suffix, paths = _build_export_paths(match_id, tone)
    md_path = paths["markdown"]
    html_path = paths["html"]
    json_path = paths["json"]
    pdf_path = paths["pdf"]
    docx_path = paths["docx"]

    md_path.write_text(markdown_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(report), file, ensure_ascii=False, indent=2)
        file.write("\n")

    result: dict[str, Any] = {
        "markdown": _public_path(md_path),
        "html": _public_path(html_path),
        "json": _public_path(json_path),
        "pdf": None,
        "docx": None,
        "exported_at": exported_at.isoformat(timespec="seconds"),
        "exported_at_utc": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"),
        "export_suffix": export_suffix,
        "pdf_status": "not_requested",
        "docx_status": "not_requested",
        "pdf_error_message": None,
        "pdf_warning_message": None,
        "docx_error_message": None,
        "pdf_result": {
            "status": "not_requested",
            "path": _public_path(pdf_path),
            "error_message": None,
            "warning_message": None,
        },
        "docx_result": {
            "status": "not_requested",
            "path": _public_path(docx_path),
            "error_message": None,
        },
    }

    if include_pdf:
        pdf_result = render_pdf_report(html_text, pdf_path.as_posix())
        pdf_result["path"] = _public_path(pdf_result.get("path") or pdf_path)
        result["pdf_result"] = pdf_result
        result["pdf_status"] = pdf_result["status"]
        result["pdf_error_message"] = pdf_result.get("error_message")
        result["pdf_warning_message"] = pdf_result.get("warning_message")
        if pdf_result["status"] == "generated":
            result["pdf"] = pdf_result["path"]

    if include_docx:
        docx_result = render_docx_report(report, docx_path.as_posix())
        docx_result["path"] = _public_path(docx_result.get("path") or docx_path)
        result["docx_result"] = docx_result
        result["docx_status"] = docx_result["status"]
        result["docx_error_message"] = docx_result.get("error_message")
        if docx_result["status"] == "generated":
            result["docx"] = docx_result["path"]

    return result


def _safe_token(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())
    return clean.strip("-") or "reporte"


def _build_export_paths(match_id: int, tone: str) -> tuple[datetime, str, dict[str, Path]]:
    exported_at = datetime.now()
    while True:
        export_suffix = exported_at.strftime("%Y%m%d_%H%M%S")
        base_name = f"report.match-{match_id}.{tone}_{export_suffix}"
        paths = {
            "markdown": REPORTS_DIR / f"{base_name}.md",
            "html": REPORTS_DIR / f"{base_name}.html",
            "json": REPORTS_DIR / f"{base_name}.json",
            "pdf": REPORTS_DIR / f"{base_name}.pdf",
            "docx": REPORTS_DIR / f"{base_name}.docx",
        }
        if not any(path.exists() for path in paths.values()):
            return exported_at, export_suffix, paths
        exported_at += timedelta(seconds=1)


def _public_path(path_value: str | Path) -> str:
    path = path_value if isinstance(path_value, Path) else Path(str(path_value))
    if not path.is_absolute():
        return path.as_posix()
    return project_relative(path)
