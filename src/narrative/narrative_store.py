"""Persistence helpers for generated narratives."""

from __future__ import annotations

import json
import re
from typing import Any

from src.config import ANALYTICS_EXPORTS_DIR
from src.ingestion.utils import to_jsonable


def save_narrative(result: dict[str, Any]) -> tuple[str, str]:
    ANALYTICS_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    match_id = result["match_id"]
    tone = _safe_token(str(result["tone"]))
    md_path = ANALYTICS_EXPORTS_DIR / f"narrative.match-{match_id}.{tone}.md"
    json_path = ANALYTICS_EXPORTS_DIR / f"narrative.match-{match_id}.{tone}.json"

    md_path.write_text(str(result.get("narrative_markdown") or ""), encoding="utf-8")
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(result), file, ensure_ascii=False, indent=2)
        file.write("\n")
    return md_path.as_posix(), json_path.as_posix()


def _safe_token(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())
    return clean.strip("-") or "narrativa"

