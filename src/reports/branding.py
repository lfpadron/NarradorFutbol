"""Shared report branding for generated PDF and DOCX artifacts."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.config import PROJECT_ROOT

FOOTER_TEXT = "UNA MISIÓN DE DEMOSTRACIÓN DE:"
FOOTER_URL = "https://astrogatolabs.com.mx/"
FOOTER_LOGO_PATH = PROJECT_ROOT / "app" / "assets" / "astrogato_labs_logo_footer.png"


@lru_cache(maxsize=1)
def footer_logo_data_uri() -> str:
    if not FOOTER_LOGO_PATH.exists():
        return ""
    encoded = base64.b64encode(FOOTER_LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def footer_logo_path() -> Path | None:
    return FOOTER_LOGO_PATH if FOOTER_LOGO_PATH.exists() else None


def add_docx_footer(document: Any) -> None:
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT, WD_CELL_VERTICAL_ALIGNMENT
    from docx.shared import Inches, Pt, RGBColor

    logo_path = footer_logo_path()
    for section in document.sections:
        section.footer_distance = Inches(0.2)
        paragraph = section.footer.paragraphs[0] if section.footer.paragraphs else section.footer.add_paragraph()
        paragraph.text = ""
        table = section.footer.add_table(rows=1, cols=3, width=Inches(7.0))
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        for cell in table.rows[0].cells:
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
        left, center, _ = table.rows[0].cells
        left_paragraph = left.paragraphs[0]
        left_paragraph.alignment = WD_ALIGN_PARAGRAPH.LEFT
        text_run = left_paragraph.add_run(FOOTER_TEXT)
        text_run.font.name = "Arial"
        text_run.font.size = Pt(7)
        text_run.font.bold = True
        text_run.font.color.rgb = RGBColor(71, 85, 105)
        center_paragraph = center.paragraphs[0]
        center_paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
        if logo_path is not None:
            _add_docx_hyperlinked_picture(center_paragraph, logo_path, Inches(1.45))


def add_report_footer_to_html(html: str) -> str:
    logo_uri = footer_logo_data_uri()
    logo_markup = (
        f'<a href="{FOOTER_URL}" class="astrogato-report-footer__link">'
        f'<img src="{logo_uri}" alt="Astrogato Labs" class="astrogato-report-footer__logo">'
        "</a>"
        if logo_uri
        else ""
    )
    style = """
<style>
  @page {
    margin-bottom: 76px;
    @bottom-center {
      content: element(astrogato-report-footer);
    }
  }
  .astrogato-report-footer {
    position: running(astrogato-report-footer);
    color: #475569;
    font-family: "Segoe UI", Arial, sans-serif;
    font-size: 7.5px;
    font-weight: 700;
    letter-spacing: 0.08em;
  }
  .astrogato-report-footer__inner {
    display: table;
    table-layout: fixed;
    width: 100%;
  }
  .astrogato-report-footer__text {
    display: table-cell;
    text-align: left;
    vertical-align: middle;
    white-space: nowrap;
  }
  .astrogato-report-footer__link {
    display: table-cell;
    text-align: center;
    vertical-align: middle;
  }
  .astrogato-report-footer__spacer {
    display: table-cell;
  }
  .astrogato-report-footer__logo {
    width: 132px;
    max-height: 34px;
    object-fit: contain;
    vertical-align: middle;
  }
  @media screen {
    .astrogato-report-footer {
      margin-top: 28px;
      padding-top: 12px;
      border-top: 1px solid #d9e0e7;
    }
  }
</style>
"""
    footer = f"""
<footer class="astrogato-report-footer">
  <div class="astrogato-report-footer__inner">
    <span class="astrogato-report-footer__text">{FOOTER_TEXT}</span>
    {logo_markup}
    <span class="astrogato-report-footer__spacer" aria-hidden="true"></span>
  </div>
</footer>
"""
    if "</head>" in html:
        html = html.replace("</head>", f"{style}\n</head>", 1)
    else:
        html = f"{style}\n{html}"
    if "</body>" in html:
        return html.replace("</body>", f"{footer}\n</body>", 1)
    return f"{html}\n{footer}"


def draw_reportlab_footer(canvas: Any, document: Any) -> None:
    from reportlab.lib import colors
    from reportlab.lib.units import inch
    from reportlab.lib.utils import ImageReader

    page_width, _ = document.pagesize
    font_name = "Helvetica-Bold"
    font_size = 7
    logo_width = 1.45 * inch
    y = 0.34 * inch

    canvas.saveState()
    canvas.setFillColor(colors.HexColor("#475569"))
    canvas.setFont(font_name, font_size)
    canvas.drawString(document.leftMargin, y - (font_size / 2.8), FOOTER_TEXT)
    logo_path = footer_logo_path()
    if logo_path is not None:
        image = ImageReader(str(logo_path))
        image_width, image_height = image.getSize()
        logo_height = logo_width * (image_height / image_width)
        x = (page_width - logo_width) / 2
        logo_y = y - logo_height / 2
        canvas.drawImage(
            image,
            x,
            logo_y,
            width=logo_width,
            height=logo_height,
            mask="auto",
        )
        canvas.linkURL(FOOTER_URL, (x, logo_y, x + logo_width, logo_y + logo_height), relative=0)
    canvas.restoreState()


def _add_docx_hyperlinked_picture(paragraph: Any, logo_path: Path, width: Any) -> None:
    from docx.opc.constants import RELATIONSHIP_TYPE
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    relationship_id = paragraph.part.relate_to(FOOTER_URL, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship_id)
    run = paragraph.add_run()
    run.add_picture(str(logo_path), width=width)
    hyperlink.append(run._r)
    paragraph._p.append(hyperlink)
