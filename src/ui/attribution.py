"""Shared brand assets and source credits for displayed and exported charts."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path
from typing import Any

from src.ui.i18n import t

ASSET_DIR = Path(__file__).resolve().parents[2] / "app" / "assets"
STATSBOMB_LOGO = ASSET_DIR / "hudl-statsbomb-logo-default.png"
STATSBOMB_ICON = ASSET_DIR / "hudl-statsbomb-web-icon.png"
ORBITAL_CAT = ASSET_DIR / "gato-orbital.png"
SOURCE_TEXT = "Fuente: Hudl StatsBomb"
FOOTER_CREDIT = (
    "Datos de eventos proporcionados por Hudl StatsBomb Open Data. "
    "Uso exclusivo para análisis e investigación sin fines de lucro."
)
_SOURCE_NAME = "hudl-statsbomb-source"
_SOURCE_BAND_HEIGHT = 40


@lru_cache(maxsize=3)
def asset_data_uri(path: Path) -> str:
    encoded = base64.b64encode(path.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_sidebar_branding() -> None:
    import streamlit as st

    with st.sidebar:
        st.markdown(
            f'<div style="display:flex;align-items:center;justify-content:space-between;gap:24px;margin:0 0 20px">'
            f'<img src="{asset_data_uri(ORBITAL_CAT)}" alt="Astrogato Labs" '
            'style="width:58px;height:64px;object-fit:contain" />'
            f'<img src="{asset_data_uri(STATSBOMB_ICON)}" alt="Hudl StatsBomb" '
            'style="width:48px;height:48px;object-fit:contain" />'
            "</div>",
            unsafe_allow_html=True,
        )


def add_statsbomb_attribution(figure: Any, language: str | None = None, *, height: int | None = None) -> Any:
    """Reserve a source band below the existing axes and legend, including in exports."""
    branded = any(image.name == _SOURCE_NAME for image in figure.layout.images)
    bottom = figure.layout.margin.b if figure.layout.margin.b is not None else 80
    top = figure.layout.margin.t if figure.layout.margin.t is not None else 100
    if branded:
        bottom -= _SOURCE_BAND_HEIGHT
    final_height = height or ((figure.layout.height or 450) + (0 if branded else _SOURCE_BAND_HEIGHT))
    figure.update_layout(height=final_height, margin_b=bottom + _SOURCE_BAND_HEIGHT)
    plot_height = max(1, final_height - top - bottom - _SOURCE_BAND_HEIGHT)
    source_y = -(bottom + _SOURCE_BAND_HEIGHT / 2) / plot_height
    figure.layout.images = tuple(image for image in figure.layout.images if image.name != _SOURCE_NAME)
    figure.layout.annotations = tuple(note for note in figure.layout.annotations if note.name != _SOURCE_NAME)
    figure.add_layout_image(
        name=_SOURCE_NAME,
        source=asset_data_uri(STATSBOMB_ICON),
        xref="paper",
        yref="paper",
        x=0,
        y=source_y,
        xanchor="left",
        yanchor="middle",
        sizex=1,
        sizey=22 / plot_height,
        sizing="contain",
        layer="above",
    )
    figure.add_annotation(
        name=_SOURCE_NAME,
        text=str(t(SOURCE_TEXT, language=language)),
        xref="paper",
        yref="paper",
        x=0,
        y=source_y,
        xshift=30,
        xanchor="left",
        yanchor="middle",
        showarrow=False,
        font={
            "size": 11,
            "color": figure.layout.font.color or figure.layout.template.layout.font.color or "#475569",
        },
    )
    return figure
