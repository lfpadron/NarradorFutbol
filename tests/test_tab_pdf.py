from __future__ import annotations

from src.reports.tab_pdf import _figure_image, _plotly_image_warning


class BrokenFigure:
    def to_image(self, **kwargs: object) -> bytes:
        raise RuntimeError("Kaleido requires Google Chrome to be installed.")


def test_plotly_image_warning_mentions_chrome_when_browser_is_missing() -> None:
    warning = _plotly_image_warning(RuntimeError("Kaleido requires Google Chrome to be installed."))

    assert "No se pudo incrustar una grafica Plotly" in warning
    assert "Chrome/Chromium" in warning
    assert "Detalle:" in warning


def test_figure_image_returns_warning_when_plotly_export_fails() -> None:
    image, warning = _figure_image(BrokenFigure())

    assert image is None
    assert warning is not None
    assert "Chrome/Chromium" in warning
