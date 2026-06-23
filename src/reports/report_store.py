"""Persist final match reports."""

from __future__ import annotations

import json
import re
from typing import Any

from src.config import DATA_DIR
from src.ingestion.utils import to_jsonable
from src.reports.docx_report import render_docx_report
from src.reports.pdf_report import render_pdf_report


REPORTS_DIR = DATA_DIR / "reports"


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
    base_name = f"report.match-{match_id}.{tone}"
    md_path = REPORTS_DIR / f"{base_name}.md"
    html_path = REPORTS_DIR / f"{base_name}.html"
    json_path = REPORTS_DIR / f"{base_name}.json"
    pdf_path = REPORTS_DIR / f"{base_name}.pdf"
    docx_path = REPORTS_DIR / f"{base_name}.docx"

    md_path.write_text(markdown_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(report), file, ensure_ascii=False, indent=2)
        file.write("\n")

    result: dict[str, Any] = {
        "markdown": md_path.as_posix(),
        "html": html_path.as_posix(),
        "json": json_path.as_posix(),
        "pdf": None,
        "docx": None,
        "pdf_status": "not_requested",
        "docx_status": "not_requested",
        "pdf_error_message": None,
        "pdf_warning_message": None,
        "docx_error_message": None,
        "pdf_result": {
            "status": "not_requested",
            "path": pdf_path.as_posix(),
            "error_message": None,
            "warning_message": None,
        },
        "docx_result": {
            "status": "not_requested",
            "path": docx_path.as_posix(),
            "error_message": None,
        },
    }

    if include_pdf:
        pdf_result = render_pdf_report(html_text, pdf_path.as_posix())
        result["pdf_result"] = pdf_result
        result["pdf_status"] = pdf_result["status"]
        result["pdf_error_message"] = pdf_result.get("error_message")
        result["pdf_warning_message"] = pdf_result.get("warning_message")
        if pdf_result["status"] == "generated":
            result["pdf"] = pdf_result["path"]

    if include_docx:
        docx_result = render_docx_report(report, docx_path.as_posix())
        result["docx_result"] = docx_result
        result["docx_status"] = docx_result["status"]
        result["docx_error_message"] = docx_result.get("error_message")
        if docx_result["status"] == "generated":
            result["docx"] = docx_result["path"]

    return result


def _safe_token(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())
    return clean.strip("-") or "reporte"
