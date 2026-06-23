"""PDF rendering for final match reports."""

from __future__ import annotations

import contextlib
import io
import re
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

from src.config import PROJECT_ROOT


def render_pdf_report(html: str, output_path: str) -> dict[str, Any]:
    path = Path(output_path)
    if not html.strip():
        return {
            "status": "failed",
            "path": path.as_posix(),
            "error_message": "HTML vacio; no se puede generar PDF.",
            "warning_message": None,
            "backend": None,
        }

    weasyprint_output = io.StringIO()
    try:
        with contextlib.redirect_stdout(weasyprint_output), contextlib.redirect_stderr(weasyprint_output):
            from weasyprint import HTML

            path.parent.mkdir(parents=True, exist_ok=True)
            HTML(string=html, base_url=str(PROJECT_ROOT)).write_pdf(str(path))
        return {
            "status": "generated",
            "path": path.as_posix(),
            "error_message": None,
            "warning_message": None,
            "backend": "weasyprint",
        }
    except Exception as weasyprint_exc:
        fallback_result = _render_reportlab_pdf(html, path)
        if fallback_result["status"] == "generated":
            fallback_result["warning_message"] = (
                "WeasyPrint no esta disponible en este entorno; "
                "se genero el PDF con el fallback ReportLab."
            )
            fallback_result["weasyprint_error_message"] = str(weasyprint_exc)
            return fallback_result

        return {
            "status": "failed",
            "path": path.as_posix(),
            "error_message": (
                f"WeasyPrint: {weasyprint_exc} | "
                f"ReportLab: {fallback_result.get('error_message')}"
            ),
            "warning_message": None,
            "backend": None,
        }


def _render_reportlab_pdf(html: str, path: Path) -> dict[str, Any]:
    try:
        from reportlab.lib import colors
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle

        path.parent.mkdir(parents=True, exist_ok=True)
        parser = _ReportHTMLParser()
        parser.feed(html)
        parser.close()
        blocks = parser.finish()

        margin = 48
        page_width, _ = letter
        content_width = page_width - (margin * 2)
        styles = getSampleStyleSheet()
        heading_1 = ParagraphStyle(
            "ReportHeading1",
            parent=styles["Title"],
            fontSize=18,
            leading=22,
            spaceAfter=14,
            textColor=colors.HexColor("#16202A"),
        )
        heading_2 = ParagraphStyle(
            "ReportHeading2",
            parent=styles["Heading2"],
            fontSize=13,
            leading=16,
            spaceBefore=12,
            spaceAfter=8,
            textColor=colors.HexColor("#0F766E"),
        )
        heading_3 = ParagraphStyle(
            "ReportHeading3",
            parent=styles["Heading3"],
            fontSize=11,
            leading=14,
            spaceBefore=8,
            spaceAfter=6,
            textColor=colors.HexColor("#243447"),
        )
        body_style = ParagraphStyle(
            "ReportBody",
            parent=styles["BodyText"],
            fontSize=9,
            leading=12,
            spaceAfter=6,
        )
        cell_style = ParagraphStyle(
            "ReportTableCell",
            parent=styles["BodyText"],
            fontSize=6.8,
            leading=8,
        )
        header_cell_style = ParagraphStyle(
            "ReportTableHeader",
            parent=cell_style,
            textColor=colors.HexColor("#0B3B37"),
            fontName="Helvetica-Bold",
        )

        story = []
        for block_type, payload in blocks:
            if block_type == "h1":
                story.append(Paragraph(escape(str(payload)), heading_1))
            elif block_type == "h2":
                story.append(Paragraph(escape(str(payload)), heading_2))
            elif block_type == "h3":
                story.append(Paragraph(escape(str(payload)), heading_3))
            elif block_type == "li":
                story.append(Paragraph(f"- {escape(str(payload))}", body_style))
            elif block_type == "table":
                table = _build_table(payload, content_width, cell_style, header_cell_style)
                if table is not None:
                    story.append(table)
                    story.append(Spacer(1, 8))
            elif payload:
                story.append(Paragraph(escape(str(payload)), body_style))

        if not story:
            story.append(Paragraph("Reporte sin contenido renderizable.", body_style))

        written_path, warning_message = _prepare_pdf_output_path(path)
        try:
            _write_reportlab_document(written_path, story, margin, letter, SimpleDocTemplate)
        except PermissionError:
            written_path = _alternate_pdf_path(path)
            _write_reportlab_document(written_path, story, margin, letter, SimpleDocTemplate)
            warning_message = (
                f"No se pudo sobrescribir {path.name}; "
                f"se genero {written_path.name}."
            )

        return {
            "status": "generated",
            "path": written_path.as_posix(),
            "error_message": None,
            "warning_message": warning_message,
            "backend": "reportlab",
        }
    except Exception as exc:
        return {
            "status": "failed",
            "path": path.as_posix(),
            "error_message": str(exc),
            "warning_message": None,
            "backend": "reportlab",
        }


def _write_reportlab_document(
    path: Path,
    story: list[Any],
    margin: int,
    page_size: tuple[float, float],
    document_class: Any,
) -> None:
    document = document_class(
        str(path),
        pagesize=page_size,
        rightMargin=margin,
        leftMargin=margin,
        topMargin=margin,
        bottomMargin=margin,
        title=path.stem,
    )
    document.build(list(story))


def _prepare_pdf_output_path(path: Path) -> tuple[Path, str | None]:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("ab"):
            pass
        return path, None
    except PermissionError:
        alternate_path = _alternate_pdf_path(path)
        return (
            alternate_path,
            f"No se pudo sobrescribir {path.name}; se genero {alternate_path.name}.",
        )


def _alternate_pdf_path(path: Path) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return path.with_name(f"{path.stem}_retry_{timestamp}{path.suffix}")


def _build_table(
    rows: list[list[str]],
    content_width: float,
    cell_style: Any,
    header_cell_style: Any,
) -> Any | None:
    from reportlab.lib import colors
    from reportlab.platypus import Paragraph, Table, TableStyle

    if not rows:
        return None

    max_columns = min(8, max(len(row) for row in rows))
    if max_columns <= 0:
        return None

    normalized_rows = []
    for row in rows:
        trimmed = list(row[:max_columns])
        if len(row) > max_columns and trimmed:
            trimmed[-1] = f"{trimmed[-1]} ..."
        trimmed.extend([""] * (max_columns - len(trimmed)))
        normalized_rows.append(trimmed)

    data = []
    for row_index, row in enumerate(normalized_rows):
        style = header_cell_style if row_index == 0 else cell_style
        data.append([Paragraph(escape(str(cell)), style) for cell in row])

    table = Table(
        data,
        colWidths=[content_width / max_columns] * max_columns,
        repeatRows=1 if len(data) > 1 else 0,
        hAlign="LEFT",
    )
    table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#EEF7F5")),
                ("GRID", (0, 0), (-1, -1), 0.35, colors.HexColor("#D9E0E7")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    return table


class _ReportHTMLParser(HTMLParser):
    _TEXT_TAGS = {"h1", "h2", "h3", "p", "li"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.blocks: list[tuple[str, Any]] = []
        self._text_tag: str | None = None
        self._text_chunks: list[str] = []
        self._table: list[list[str]] | None = None
        self._row: list[str] | None = None
        self._cell_chunks: list[str] | None = None

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in self._TEXT_TAGS and self._cell_chunks is None:
            self._flush_text_block()
            self._text_tag = tag
            self._text_chunks = []
        elif tag == "br":
            self._append_text(" ")
        elif tag == "table":
            self._flush_text_block()
            self._table = []
        elif tag == "tr" and self._table is not None:
            self._row = []
        elif tag in {"td", "th"} and self._row is not None:
            self._cell_chunks = []

    def handle_data(self, data: str) -> None:
        if self._cell_chunks is not None:
            self._cell_chunks.append(data)
        elif self._text_tag is not None:
            self._text_chunks.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in self._TEXT_TAGS and tag == self._text_tag:
            self._flush_text_block()
        elif tag in {"td", "th"} and self._cell_chunks is not None:
            if self._row is not None:
                self._row.append(_clean_text(" ".join(self._cell_chunks)))
            self._cell_chunks = None
        elif tag == "tr" and self._row is not None:
            if any(cell for cell in self._row) and self._table is not None:
                self._table.append(self._row)
            self._row = None
        elif tag == "table" and self._table is not None:
            if self._table:
                self.blocks.append(("table", self._table))
            self._table = None

    def finish(self) -> list[tuple[str, Any]]:
        self._flush_text_block()
        return self.blocks

    def _append_text(self, text: str) -> None:
        if self._cell_chunks is not None:
            self._cell_chunks.append(text)
        elif self._text_tag is not None:
            self._text_chunks.append(text)

    def _flush_text_block(self) -> None:
        if self._text_tag is None:
            return
        text = _clean_text(" ".join(self._text_chunks))
        if text:
            self.blocks.append((self._text_tag, text))
        self._text_tag = None
        self._text_chunks = []


def _clean_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()
