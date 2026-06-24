"""Compatibility facade for Scouting AI report exports."""

from __future__ import annotations

from typing import Any

from src.scouting.scouting_exporter import (
    render_scouting_html,
    render_scouting_markdown,
    save_scouting_export,
)


def save_scouting_report(
    result: dict[str, Any],
    include_html: bool = False,
    include_docx: bool = False,
    include_pdf: bool = False,
    record_history: bool = True,
    use_api: bool | None = None,
) -> dict[str, Any]:
    return save_scouting_export(
        result,
        include_html=include_html,
        include_docx=include_docx,
        include_pdf=include_pdf,
        record_history=record_history,
        use_api=use_api,
    )
