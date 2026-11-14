"""Self-contained player-card downloads with the existing closing credits."""

from __future__ import annotations

import base64
from html import escape
from io import BytesIO
from typing import Any

from src.analytics.player_cards import card_notes
from src.reports.branding import add_docx_footer, add_report_footer_to_html, reportlab_closing_block


def cards_title(cards: list[dict[str, Any]], language: str = "es") -> str:
    heading = "Player cards" if language == "en" else "Tarjetas de jugadores"
    return f"{heading} — " + " / ".join(str(card["player_name"]) for card in cards)


def player_cards_html(cards: list[dict[str, Any]], png: bytes, language: str = "es") -> bytes:
    title = escape(cards_title(cards, language))
    artwork = base64.b64encode(png).decode("ascii")
    width = 944 if len(cards) == 2 else 476
    html = f"""<!doctype html>
<html lang="{'en' if language == 'en' else 'es'}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1"><title>{title}</title>
<style>
body {{margin:0;background:#111827;font-family:Arial,sans-serif;color:#0f172a}}
main {{max-width:980px;margin:0 auto;padding:24px;background:#fff}}
h1 {{font-size:22px;margin:0 0 18px}} .cards {{display:block;width:100%;max-width:{width}px;height:auto;margin:auto}}
.notes {{font-size:11px;line-height:1.5;color:#475569;margin:16px 0 0}}
@media print {{body {{background:white}} main {{padding:0}} .cards {{max-height:190mm;object-fit:contain}}}}
</style></head><body><main><h1>{title}</h1>
<img class="cards" src="data:image/png;base64,{artwork}" alt="{title}">
<p class="notes">{escape(card_notes(language))}</p></main></body></html>"""
    return add_report_footer_to_html(html).encode("utf-8")


def player_cards_docx(cards: list[dict[str, Any]], png: bytes, language: str = "es") -> bytes:
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn
    from docx.shared import Inches, Pt, RGBColor

    document = Document()
    section = document.sections[0]
    section.page_width, section.page_height = Inches(8.27), Inches(11.69)
    section.left_margin = section.right_margin = Inches(0.55)
    section.top_margin = section.bottom_margin = Inches(0.45)
    style = document.styles["Normal"]
    style.font.name, style.font.size = "Arial", Pt(9)
    title_style = document.styles["Title"]
    title_style.font.color.rgb = RGBColor(0, 0, 0)
    for border in title_style.element.iter(qn("w:pBdr")):
        border.getparent().remove(border)
    title = document.add_paragraph(style="Title")
    title.paragraph_format.space_after = Pt(10)
    title.paragraph_format.keep_with_next = True
    run = title.add_run(cards_title(cards, language))
    run.font.name, run.font.size = "Arial", Pt(15)
    run.font.color.rgb = RGBColor(0, 0, 0)
    paragraph = document.add_paragraph()
    paragraph.alignment = WD_ALIGN_PARAGRAPH.CENTER
    paragraph.paragraph_format.space_after = Pt(6)
    # One shared image preserves the side-by-side layout in Word and every PDF reader.
    width = 7.05 if len(cards) == 2 else 3.65
    picture = paragraph.add_run().add_picture(BytesIO(png), width=Inches(width))
    picture._inline.docPr.set("descr", cards_title(cards, language))
    notes = document.add_paragraph(card_notes(language))
    notes.paragraph_format.space_after = Pt(0)
    notes.paragraph_format.line_spacing = 1.1
    for run in notes.runs:
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor.from_string("475569")
    add_docx_footer(document)
    output = BytesIO()
    document.save(output)
    return output.getvalue()


def player_cards_pdf(cards: list[dict[str, Any]], png: bytes, language: str = "es") -> bytes:
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle
    from reportlab.platypus import Image, Paragraph, SimpleDocTemplate, Spacer

    output = BytesIO()
    document = SimpleDocTemplate(
        output,
        pagesize=A4,
        leftMargin=32,
        rightMargin=32,
        topMargin=28,
        bottomMargin=28,
        title=cards_title(cards, language),
        author="Narrador Fútbol",
    )
    content_width = document.width - 12
    picture = Image(BytesIO(png))
    scale = min(content_width / picture.imageWidth, 420 / picture.imageHeight)
    picture.drawWidth, picture.drawHeight = picture.imageWidth * scale, picture.imageHeight * scale
    title_style = ParagraphStyle("CardTitle", fontName="Helvetica-Bold", fontSize=15, leading=19, spaceAfter=12)
    note_style = ParagraphStyle("CardNotes", fontName="Helvetica", fontSize=8, leading=11, textColor="#475569")
    document.build(
        [
            Paragraph(escape(cards_title(cards, language)), title_style),
            picture,
            Spacer(1, 10),
            Paragraph(escape(card_notes(language)), note_style),
            Spacer(1, 6),
            reportlab_closing_block(content_width),
        ]
    )
    return output.getvalue()
