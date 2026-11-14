from __future__ import annotations

import importlib
import json
from pathlib import Path
from zipfile import ZipFile

import pytest
from lxml import etree

from src.reports.branding import CONTACT_EMAIL, FOOTER_URL, STATSBOMB_CREDIT, add_markdown_footer
from src.reports.docx_report import render_docx_report
from src.narrative_v2.narrator_v2 import render_specialized_narrative_docx
from src.scouting.scouting_exporter import render_scouting_docx


@pytest.mark.parametrize("exporter", ["report", "narrative", "scouting"])
def test_docx_closes_with_both_logos_credit_and_clickable_brand(tmp_path, exporter):
    path = tmp_path / f"{exporter}.docx"
    if exporter == "report":
        result = render_docx_report({}, str(path))
    elif exporter == "narrative":
        result = render_specialized_narrative_docx("# Prueba\n\nContenido del informe.", str(path))
    else:
        result = render_scouting_docx({}, "# Prueba\n\nContenido del informe.", str(path))
    assert result["status"] == "generated", result
    with ZipFile(path) as archive:
        document = etree.fromstring(archive.read("word/document.xml"))
        relationships = etree.fromstring(archive.read("word/_rels/document.xml.rels"))
        assert not any(name.startswith("word/footer") for name in archive.namelist())
        namespace = {**document.nsmap, "a": "http://schemas.openxmlformats.org/drawingml/2006/main"}
        body = document.find("w:body", namespace)
        tables = body.findall("w:tbl", namespace)
        credit = "".join(tables[-2].itertext())
        brand = "".join(tables[-1].itertext())
        assert STATSBOMB_CREDIT in credit
        assert CONTACT_EMAIL in brand
        assert "".join(document.itertext()).count(STATSBOMB_CREDIT) == 1
        assert len(tables[-2].xpath(".//w:drawing", namespaces=namespace)) == 1
        assert len(tables[-1].xpath(".//w:drawing", namespaces=namespace)) == 1
        links = {rel.get("Id"): rel.get("Target") for rel in relationships}
        logo_link = tables[-1].xpath(".//a:hlinkClick", namespaces=namespace)[0]
        assert links[logo_link.get(f"{{{namespace['r']}}}id")] == FOOTER_URL
        assert f"mailto:{CONTACT_EMAIL}" in links.values()
        # The last content is the brand row; only section metadata follows it.
        assert body[-2] == tables[-1]


def test_markdown_closing_is_text_only_and_idempotent():
    markdown = add_markdown_footer("# Informe\n\nContenido.")
    assert STATSBOMB_CREDIT in markdown
    assert f"[Astrogatolabs.com]({FOOTER_URL})" in markdown
    assert "![" not in markdown and "<img" not in markdown
    assert add_markdown_footer(markdown) == markdown


@pytest.mark.parametrize(
    "module_name, directory, function, payload, extra_args, kwargs",
    [
        (
            "src.reports.report_store",
            "REPORTS_DIR",
            "save_report",
            {"match_id": 1, "tone": "test"},
            ("# Informe", "<html><body>Informe</body></html>"),
            {},
        ),
        (
            "src.narrative.narrative_store",
            "ANALYTICS_EXPORTS_DIR",
            "save_narrative",
            {"match_id": 1, "tone": "test", "narrative_markdown": "# Narración"},
            (),
            {},
        ),
        ("src.narrative.review_report", "ANALYTICS_EXPORTS_DIR", "save_review_report", {"match_id": 1}, (), {}),
        (
            "src.narrative_v2.narrator_v2",
            "ANALYTICS_EXPORTS_DIR",
            "save_specialized_narrative_export",
            {"match_id": 1, "style_id": "tactico"},
            (),
            {},
        ),
        (
            "src.scouting.scouting_exporter",
            "SCOUTING_DIR",
            "save_scouting_export",
            {"match_id_a": 1, "player_id_a": 2},
            (),
            {"record_history": False},
        ),
        (
            "src.scouting.scouting_v2_report",
            "SCOUTING_DIR",
            "save_scouting_v2_report",
            {"match_id_a": 1, "player_id_a": 2},
            (),
            {},
        ),
        (
            "src.comparison.comparison_report",
            "COMPARISONS_DIR",
            "save_match_comparison",
            {"match_a": {"match_id": 1}, "match_b": {"match_id": 2}},
            (),
            {},
        ),
        (
            "src.comparison.player_comparison_report",
            "COMPARISONS_DIR",
            "save_player_comparison",
            {"player_a": {"match_id": 1, "player_id": 2}, "player_b": {"match_id": 3, "player_id": 4}},
            (),
            {},
        ),
        ("src.benchmark.benchmark_report", "BENCHMARK_RESULTS_DIR", "save_benchmark_result", {}, (), {}),
        (
            "src.benchmark.generic_report",
            "BENCHMARK_RESULTS_DIR",
            "save_generic_validation_result",
            {"match_id": 1},
            (),
            {},
        ),
    ],
)
def test_all_markdown_exports_include_closing_without_changing_json(
    tmp_path, monkeypatch, module_name, directory, function, payload, extra_args, kwargs
):
    module = importlib.import_module(module_name)
    monkeypatch.setattr(module, directory, tmp_path)
    if module_name.endswith("scouting_v2_report"):
        monkeypatch.setattr(module, "_render_radar_png", lambda result: (None, None))
    saved = getattr(module, function)(payload, *extra_args, **kwargs)
    markdown_path = Path(saved[0] if isinstance(saved, tuple) else saved["markdown"])
    json_path = Path(saved[1] if isinstance(saved, tuple) else saved["json"])
    markdown = markdown_path.read_text(encoding="utf-8")
    assert markdown.count(STATSBOMB_CREDIT) == 1
    assert f"[Astrogatolabs.com]({FOOTER_URL})" in markdown
    assert "![" not in markdown and "<img" not in markdown
    assert STATSBOMB_CREDIT not in json.dumps(json.loads(json_path.read_text(encoding="utf-8")), ensure_ascii=False)


def test_html_pdf_backend_closing_is_at_end_and_not_a_running_footer():
    from src.reports.branding import add_report_footer_to_html

    html = add_report_footer_to_html("<html><head></head><body><main><h1>Informe</h1></main></body></html>")
    assert html.count(STATSBOMB_CREDIT) == 1
    assert f'<a href="{FOOTER_URL}"><img' in html
    assert html.index("</footer>") < html.index("</main>")
    assert "position: running" not in html
    assert "break-inside: avoid" in html


def test_reportlab_closing_stays_together_on_last_page(tmp_path):
    from reportlab.lib.styles import getSampleStyleSheet
    from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer
    from src.reports.branding import reportlab_closing_block

    class RecordingDocument(SimpleDocTemplate):
        def afterFlowable(self, flowable):
            if isinstance(flowable, Paragraph):
                placements.append(("body", self.page))
            if getattr(flowable, "_cellvalues", None):
                placements.append(("closing", self.page))

    placements = []
    document = RecordingDocument(str(tmp_path / "pagination.pdf"))
    document.build(
        [
            Paragraph("Último párrafo", getSampleStyleSheet()["BodyText"]),
            Spacer(1, 620),
            reportlab_closing_block(document.width - 12),
        ]
    )
    assert placements == [("body", 1), ("closing", 2), ("closing", 2)]


def test_pdf_logos_fit_their_columns_without_distortion(tmp_path, monkeypatch):
    from reportlab.pdfgen.canvas import Canvas
    from reportlab.platypus import SimpleDocTemplate
    from PIL import Image
    from src.reports.branding import FOOTER_LOGO_PATH, STATSBOMB_LOGO_PATH, reportlab_closing_block

    sizes = []
    original = Canvas.drawImage

    def draw_image(canvas, image, x, y, width=None, height=None, *args, **kwargs):
        sizes.append((width, height))
        return original(canvas, image, x, y, width, height, *args, **kwargs)

    monkeypatch.setattr(Canvas, "drawImage", draw_image)
    document = SimpleDocTemplate(str(tmp_path / "logos.pdf"))
    document.build([reportlab_closing_block(document.width - 12)])
    assert [width for width, _ in sizes] == [90, 104]
    for (width, height), path in zip(sizes, (STATSBOMB_LOGO_PATH, FOOTER_LOGO_PATH)):
        with Image.open(path) as image:
            assert width / height == pytest.approx(image.width / image.height)
