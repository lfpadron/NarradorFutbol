"""Shared closing credits for generated PDF, DOCX and Markdown documents."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.config import PROJECT_ROOT

FOOTER_TEXT = "UNA MISIÓN DE DEMOSTRACIÓN DE:"
FOOTER_URL = "https://astrogatolabs.com/"
FOOTER_LABEL = "Astrogatolabs.com"
CONTACT_TEXT = "Para más información"
CONTACT_EMAIL = "lfpadron@astrogatolabs.com"
STATSBOMB_CREDIT = (
    "Este análisis utiliza datos de acceso libre del repositorio Hudl StatsBomb Open Data, "
    "disponibles bajo su licencia de uso público para investigación y análisis deportivo."
)
FOOTER_LOGO_PATH = PROJECT_ROOT / "app" / "assets" / "astrogato_labs_logo_footer.png"
STATSBOMB_LOGO_PATH = PROJECT_ROOT / "app" / "assets" / "hudl-statsbomb-logo-default.png"


@lru_cache(maxsize=2)
def _logo_data_uri(path: Path) -> str:
    if not path.exists():
        return ""
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def add_markdown_footer(markdown: str) -> str:
    """Add the text-only closing block at the file boundary, once."""
    footer = (
        f"---\n\n{STATSBOMB_CREDIT}\n\n"
        f"**{FOOTER_TEXT}**\n\n[{FOOTER_LABEL}]({FOOTER_URL})\n\n"
        f"{CONTACT_TEXT}: [{CONTACT_EMAIL}](mailto:{CONTACT_EMAIL})"
    )
    body = markdown.rstrip()
    if body.endswith(footer):
        return body + "\n"
    return f"{body}\n\n{footer}\n"


def add_docx_footer(document: Any) -> None:
    """Append a closing block in the body, keeping both rows on the same page."""
    from docx.enum.table import WD_CELL_VERTICAL_ALIGNMENT, WD_TABLE_ALIGNMENT
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    section = document.sections[-1]
    width = section.page_width - section.left_margin - section.right_margin
    spacer = document.add_paragraph()
    spacer.paragraph_format.space_after = Pt(8)
    spacer.paragraph_format.space_before = Pt(0)
    spacer.paragraph_format.keep_with_next = True
    spacer.paragraph_format.line_spacing = Pt(1)

    def layout_table(fractions: tuple[float, ...]) -> Any:
        table = document.add_table(rows=1, cols=len(fractions))
        table.alignment = WD_TABLE_ALIGNMENT.CENTER
        table.autofit = False
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            border = OxmlElement(f"w:{edge}")
            border.set(qn("w:val"), "nil")
            borders.append(border)
        table._tbl.tblPr.append(borders)
        table.rows[0]._tr.get_or_add_trPr().append(OxmlElement("w:cantSplit"))
        for column, cell, fraction in zip(table.columns, table.rows[0].cells, fractions):
            column.width = cell.width = int(width * fraction)
            cell.vertical_alignment = WD_CELL_VERTICAL_ALIGNMENT.CENTER
            paragraph = cell.paragraphs[0]
            paragraph.paragraph_format.space_before = Pt(6)
            paragraph.paragraph_format.space_after = Pt(6)
            paragraph.paragraph_format.line_spacing = 1.15
            paragraph.paragraph_format.keep_with_next = True
        return table

    def text_run(paragraph: Any, text: str, *, bold: bool = False, size: float = 8) -> Any:
        run = paragraph.add_run(text)
        run.font.name = "Arial"
        run.font.size = Pt(size)
        run.font.bold = bold
        run.font.color.rgb = RGBColor.from_string("475569")
        return run

    source = layout_table((0.24, 0.76))
    logo, credit = (cell.paragraphs[0] for cell in source.rows[0].cells)
    if STATSBOMB_LOGO_PATH.exists():
        logo.add_run().add_picture(str(STATSBOMB_LOGO_PATH), width=Inches(1.25))
    else:
        text_run(logo, "Hudl StatsBomb", bold=True)
    text_run(credit, STATSBOMB_CREDIT, size=8.5)

    # Separate the tables so Word does not merge their different column grids.
    gap = document.add_paragraph()
    gap.paragraph_format.space_before = Pt(0)
    gap.paragraph_format.space_after = Pt(0)
    gap.paragraph_format.line_spacing = Pt(6)
    gap.paragraph_format.keep_with_next = True

    brand = layout_table((0.30, 0.32, 0.38))
    left, center, right = (cell.paragraphs[0] for cell in brand.rows[0].cells)
    text_run(left, FOOTER_TEXT, bold=True, size=7.5)
    center.alignment = WD_ALIGN_PARAGRAPH.CENTER
    if FOOTER_LOGO_PATH.exists():
        run = center.add_run()
        picture = run.add_picture(str(FOOTER_LOGO_PATH), width=Inches(1.45))
        # DrawingML makes the image itself clickable in Word and PDF exports.
        from docx.opc.constants import RELATIONSHIP_TYPE

        link_id = center.part.relate_to(FOOTER_URL, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
        link = OxmlElement("a:hlinkClick")
        link.set(qn("r:id"), link_id)
        picture._inline.docPr.append(link)
    else:
        _link_docx_run(center, text_run(center, FOOTER_LABEL), FOOTER_URL)
    right.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    text_run(right, CONTACT_TEXT + "\n")
    _link_docx_run(right, text_run(right, CONTACT_EMAIL, size=7.5), f"mailto:{CONTACT_EMAIL}")
    for paragraph in (left, center, right):
        paragraph.paragraph_format.keep_with_next = False


def _link_docx_run(paragraph: Any, run: Any, url: str) -> None:
    from docx.opc.constants import RELATIONSHIP_TYPE
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn

    relationship_id = paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    hyperlink = OxmlElement("w:hyperlink")
    hyperlink.set(qn("r:id"), relationship_id)
    hyperlink.append(run._r)
    paragraph._p.append(hyperlink)


def add_report_footer_to_html(html: str) -> str:
    """Add a non-repeating, unbroken closing block for the HTML-to-PDF backend."""
    statsbomb_uri = _logo_data_uri(STATSBOMB_LOGO_PATH)
    logo_uri = _logo_data_uri(FOOTER_LOGO_PATH)
    statsbomb = f'<img src="{statsbomb_uri}" alt="Hudl StatsBomb">' if statsbomb_uri else "Hudl StatsBomb"
    brand = f'<img src="{logo_uri}" alt="Astrogato Labs">' if logo_uri else FOOTER_LABEL
    style = """
<style>
  .report-closing {
    break-inside: avoid;
    page-break-inside: avoid;
    margin: 24px auto 0;
    padding-top: 14px;
    border-top: 1px solid #d9e0e7;
    max-width: 960px;
    color: #475569;
    font-family: Arial, sans-serif;
    font-size: 11px;
    line-height: 1.45;
  }
  .report-closing__source, .report-closing__brand { display: table; width: 100%; table-layout: fixed; }
  .report-closing__source > div, .report-closing__brand > div {
    display: table-cell; vertical-align: middle;
  }
  .report-closing__source-logo { width: 24%; }
  .report-closing__source-logo img { width: 120px; max-width: 90%; height: auto; }
  .report-closing__brand { margin-top: 18px; font-size: 10px; }
  .report-closing__mission { width: 30%; font-weight: bold; }
  .report-closing__logo { width: 32%; text-align: center; }
  .report-closing__logo img { width: 140px; max-width: 90%; height: auto; }
  .report-closing__contact { width: 38%; text-align: right; }
  .report-closing a { color: inherit; text-decoration: none; }
</style>
"""
    footer = f"""
<footer class="report-closing">
  <div class="report-closing__source">
    <div class="report-closing__source-logo">{statsbomb}</div>
    <div>{STATSBOMB_CREDIT}</div>
  </div>
  <div class="report-closing__brand">
    <div class="report-closing__mission">{FOOTER_TEXT}</div>
    <div class="report-closing__logo"><a href="{FOOTER_URL}">{brand}</a></div>
    <div class="report-closing__contact">{CONTACT_TEXT}<br>
      <a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>
    </div>
  </div>
</footer>
"""
    if "</head>" in html:
        html = html.replace("</head>", f"{style}\n</head>", 1)
    else:
        html = f"{style}\n{html}"
    # Keep the closing block inside the report's content width/padding when present.
    if "</main>" in html:
        return html.replace("</main>", f"{footer}\n</main>", 1)
    if "</body>" in html:
        return html.replace("</body>", f"{footer}\n</body>", 1)
    return f"{html}\n{footer}"


def reportlab_closing_block(content_width: float) -> Any:
    """Build a single final block, including clickable logo and contact address."""
    from reportlab.lib import colors
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import HRFlowable, Image, KeepTogether, Paragraph, Spacer, Table, TableStyle

    class LinkedImage(Image):
        def draw(self) -> None:
            super().draw()
            self.canv.linkURL(FOOTER_URL, (0, 0, self.drawWidth, self.drawHeight), relative=1)

    style = ParagraphStyle(
        "ClosingCredit", fontName="Helvetica", fontSize=8.5, leading=12, textColor=colors.HexColor("#475569")
    )
    mission_style = ParagraphStyle("ClosingMission", parent=style, fontName="Helvetica-Bold", fontSize=7.5, leading=10)
    contact_style = ParagraphStyle("ClosingContact", parent=style, fontSize=7.5, leading=11, alignment=2)

    def logo(path: Path, width: float, *, linked: bool = False) -> Any:
        if not path.exists():
            label = f'<a href="{FOOTER_URL}">{FOOTER_LABEL}</a>' if linked else "Hudl StatsBomb"
            return Paragraph(label, style)
        image = LinkedImage(str(path)) if linked else Image(str(path))
        image_width, image_height = image.imageWidth, image.imageHeight
        image.drawWidth = width
        image.drawHeight = width * image_height / image_width
        return image

    source = Table(
        [[logo(STATSBOMB_LOGO_PATH, 90), Paragraph(STATSBOMB_CREDIT, style)]],
        colWidths=[content_width * 0.24, content_width * 0.76],
    )
    brand = Table(
        [
            [
                Paragraph(FOOTER_TEXT, mission_style),
                logo(FOOTER_LOGO_PATH, 104, linked=True),
                Paragraph(f'{CONTACT_TEXT}<br/><a href="mailto:{CONTACT_EMAIL}">{CONTACT_EMAIL}</a>', contact_style),
            ]
        ],
        colWidths=[content_width * 0.30, content_width * 0.32, content_width * 0.38],
    )
    for table in (source, brand):
        table.setStyle(
            TableStyle(
                [
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 0),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                    ("RIGHTPADDING", (-1, 0), (-1, -1), 0),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                ]
            )
        )
    brand.setStyle(TableStyle([("ALIGN", (1, 0), (1, 0), "CENTER")]))
    return KeepTogether(
        [
            Spacer(1, 18),
            HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#D9E0E7")),
            Spacer(1, 10),
            source,
            Spacer(1, 12),
            brand,
        ]
    )
