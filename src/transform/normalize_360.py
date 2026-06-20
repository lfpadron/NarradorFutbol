"""Normalize StatsBomb 360 visible-area JSON files."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.config import RAW_THREE_SIXTY_DIR
from src.transform.utils import THREE_SIXTY_FILE_RE, as_str, json_text, load_records, match_id_from_path


def normalize_360_for_match(match_id: int, raw_three_sixty_dir: Path = RAW_THREE_SIXTY_DIR) -> dict[str, list[dict[str, Any]]]:
    path = raw_three_sixty_dir / f"three-sixty.match-{match_id}.json"
    if not path.exists():
        return {"visible_area": []}
    return normalize_360_file(path)


def normalize_360_file(path: Path) -> dict[str, list[dict[str, Any]]]:
    match_id = match_id_from_path(path, THREE_SIXTY_FILE_RE)
    visible_area_rows: list[dict[str, Any]] = []

    for frame in load_records(path):
        event_id = as_str(frame.get("event_uuid") or frame.get("event_id") or frame.get("id"))
        visible_area = frame.get("visible_area")
        if event_id is None or visible_area is None:
            continue
        visible_area_rows.append(
            {
                "event_id": event_id,
                "match_id": match_id,
                "visible_area_json": json_text(visible_area),
            }
        )

    return {"visible_area": visible_area_rows}
