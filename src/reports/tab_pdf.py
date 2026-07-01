"""Simple PDF exports for Streamlit analysis tabs."""

from __future__ import annotations

import re
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import Any

from src.config import REPORTS_DIR, project_relative
from src.reports.branding import draw_reportlab_footer


def save_analysis_tab_pdf(
    tab_name: str,
    match_id: int,
    title: str,
    sections: list[dict[str, Any]],
    figures: list[Any] | None = None,
) -> dict[str, Any]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    exported_at = datetime.now()
    suffix = exported_at.strftime("%Y%m%d_%H%M%S")
    path = REPORTS_DIR / f"analysis_tab.match-{match_id}.{_safe_token(tab_name)}_{suffix}.pdf"
    result = _render_pdf(path, title, sections, figures or [])
    result["exported_at"] = exported_at.isoformat(timespec="seconds")
    result["path"] = project_relative(Path(result["path"]))
    return result


def _render_pdf(path: Path, title: str, sections: list[dict[str, Any]], figures: list[Any]) -> dict[str, Any]:
    image_warnings: list[str] = []
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        styles = getSampleStyleSheet()
        title_style = ParagraphStyle(
            "TabTitle",
            parent=styles["Title"],
            fontSize=18,
            leading=22,
            textColor=colors.HexColor("#16202A"),
            spaceAfter=12,
        )
        heading_style = ParagraphStyle(
            "TabHeading",
            parent=styles["Heading2"],
            fontSize=12,
            leading=15,
            textColor=colors.HexColor("#0D6B5F"),
            spaceBefore=10,
            spaceAfter=7,
        )
        body_style = ParagraphStyle("TabBody", parent=styles["BodyText"], fontSize=8.8, leading=11)
        small_style = ParagraphStyle("TabSmall", parent=styles["BodyText"], fontSize=7, leading=8)

        story: list[Any] = [Paragraph(_escape(title), title_style)]
        for figure in figures:
            image, warning = _figure_image(figure)
            if image is None:
                if warning:
                    image_warnings.append(warning)
                continue
            story.append(image)
            story.append(Spacer(1, 8))

        for section in sections:
            heading = section.get("heading")
            if heading:
                story.append(Paragraph(_escape(str(heading)), heading_style))
            for paragraph in section.get("paragraphs", []):
                story.append(Paragraph(_escape(str(paragraph)), body_style))
            rows = section.get("rows") or []
            if rows:
                table = _table(rows, Table, TableStyle, colors, small_style)
                if table is not None:
                    story.append(table)
                    story.append(Spacer(1, 8))

        if image_warnings:
            story.append(Paragraph(_escape(" ".join(sorted(set(image_warnings)))), small_style))

        document = SimpleDocTemplate(
            str(path),
            pagesize=letter,
            rightMargin=0.55 * inch,
            leftMargin=0.55 * inch,
            topMargin=0.55 * inch,
            bottomMargin=0.75 * inch,
        )
        document.build(story, onFirstPage=draw_reportlab_footer, onLaterPages=draw_reportlab_footer)
        return {"status": "generated", "path": path.as_posix(), "error_message": None, "warnings": image_warnings}
    except Exception as exc:
        return {"status": "failed", "path": path.as_posix(), "error_message": str(exc), "warnings": image_warnings}


def _figure_image(figure: Any) -> tuple[Any | None, str | None]:
    try:
        from reportlab.lib.units import inch
        from reportlab.platypus import Image

        data = figure.to_image(format="png", width=980, height=560, scale=1)
        image = Image(BytesIO(data))
        image.drawWidth = 7.25 * inch
        image.drawHeight = 4.15 * inch
        return image, None
    except Exception as exc:
        return None, _plotly_image_warning(exc)


def _plotly_image_warning(exc: Exception) -> str:
    reason = " ".join(str(exc).split())
    lower_reason = reason.lower()
    hint = "instala kaleido y Chrome/Chromium para imagenes Plotly"
    if "chrome" in lower_reason or "chromium" in lower_reason:
        hint = "instala Chrome/Chromium en el entorno donde corre Streamlit"
    elif "kaleido" in lower_reason:
        hint = "instala kaleido en el entorno donde corre Streamlit"
    if len(reason) > 240:
        reason = f"{reason[:237]}..."
    return f"No se pudo incrustar una grafica Plotly; {hint}. Detalle: {reason}"


def _table(rows: list[dict[str, Any]], table_class: Any, style_class: Any, colors: Any, cell_style: Any) -> Any | None:
    visible_rows = rows[:28]
    if not visible_rows:
        return None
    headers = list(visible_rows[0].keys())[:8]
    data = [[_cell(header, cell_style) for header in headers]]
    for row in visible_rows:
        data.append([_cell(row.get(header), cell_style) for header in headers])
    table = table_class(data, repeatRows=1)
    table.setStyle(
        style_class(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EDF7F5")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#0B3B37")),
                ("GRID", (0, 0), (-1, -1), 0.25, colors.HexColor("#D9E0E7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("LEFTPADDING", (0, 0), (-1, -1), 3),
                ("RIGHTPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return table


def _cell(value: Any, style: Any) -> Any:
    from reportlab.platypus import Paragraph

    return Paragraph(_escape("" if value is None else str(value)), style)


def _escape(value: str) -> str:
    return value.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _safe_token(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip().lower())
    return clean.strip("-") or "tab"
