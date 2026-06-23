"""Persist final match reports."""

from __future__ import annotations

import json
import re
from typing import Any

from src.config import DATA_DIR
from src.ingestion.utils import to_jsonable


REPORTS_DIR = DATA_DIR / "reports"


def save_report(report: dict[str, Any], markdown_text: str, html_text: str) -> dict[str, str]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    match_id = report["match_id"]
    tone = _safe_token(str(report["tone"]))
    base_name = f"report.match-{match_id}.{tone}"
    md_path = REPORTS_DIR / f"{base_name}.md"
    html_path = REPORTS_DIR / f"{base_name}.html"
    json_path = REPORTS_DIR / f"{base_name}.json"

    md_path.write_text(markdown_text, encoding="utf-8")
    html_path.write_text(html_text, encoding="utf-8")
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(report), file, ensure_ascii=False, indent=2)
        file.write("\n")

    return {
        "markdown": md_path.as_posix(),
        "html": html_path.as_posix(),
        "json": json_path.as_posix(),
    }


def _safe_token(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())
    return clean.strip("-") or "reporte"

