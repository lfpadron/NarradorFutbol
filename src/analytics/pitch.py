"""Pitch helpers shared by advanced analytics charts."""

from __future__ import annotations

from typing import Any

import plotly.graph_objects as go

PITCH_LENGTH = 120.0
PITCH_WIDTH = 80.0


def is_valid_pitch_point(x_value: Any, y_value: Any) -> bool:
    try:
        x = float(x_value)
        y = float(y_value)
    except (TypeError, ValueError):
        return False
    return 0 <= x <= PITCH_LENGTH and 0 <= y <= PITCH_WIDTH


def pitch_bin(
    x_value: Any,
    y_value: Any,
    x_bins: int = 6,
    y_bins: int = 4,
) -> tuple[int, int] | None:
    if not is_valid_pitch_point(x_value, y_value):
        return None
    x = min(float(x_value), PITCH_LENGTH - 0.0001)
    y = min(float(y_value), PITCH_WIDTH - 0.0001)
    x_bin = int(x / PITCH_LENGTH * x_bins)
    y_bin = int(y / PITCH_WIDTH * y_bins)
    return x_bin, y_bin


def zone_label(x_bin: int, y_bin: int, x_bins: int = 6, y_bins: int = 4) -> str:
    thirds = ("defensiva", "media", "ofensiva")
    lanes = ("izquierda", "centro-izquierda", "centro-derecha", "derecha")
    third_index = min(2, int(x_bin / max(x_bins, 1) * 3))
    lane_index = min(y_bins - 1, max(0, y_bin))
    lane = lanes[lane_index] if y_bins == 4 else f"carril {lane_index + 1}"
    return f"{thirds[third_index]} | {lane}"


def build_pitch_figure(title: str) -> go.Figure:
    figure = go.Figure()
    _add_pitch_shapes(figure)
    figure.update_layout(
        title=title,
        template="plotly_white",
        height=620,
        margin={"l": 20, "r": 20, "t": 55, "b": 20},
        legend_title_text="Equipo",
        plot_bgcolor="#eef5f1",
        paper_bgcolor="white",
    )
    figure.update_xaxes(range=[0, PITCH_LENGTH], visible=False, fixedrange=True)
    figure.update_yaxes(range=[PITCH_WIDTH, 0], visible=False, fixedrange=True, scaleanchor="x", scaleratio=1)
    return figure


def annotate_empty(figure: go.Figure, message: str) -> go.Figure:
    figure.add_annotation(
        text=message,
        x=PITCH_LENGTH / 2,
        y=PITCH_WIDTH / 2,
        showarrow=False,
        font={"size": 16, "color": "#344"},
        bgcolor="rgba(255,255,255,0.78)",
    )
    return figure


def _add_pitch_shapes(figure: go.Figure) -> None:
    line = {"color": "#506b5b", "width": 2}
    shapes = [
        _rect(0, 0, 120, 80, line),
        _line(60, 0, 60, 80, line),
        _rect(0, 18, 18, 62, line),
        _rect(102, 18, 120, 62, line),
        _rect(0, 30, 6, 50, line),
        _rect(114, 30, 120, 50, line),
        _circle(50, 30, 70, 50, line),
        _circle(11.3, 38.7, 12.7, 41.3, line),
        _circle(107.3, 38.7, 108.7, 41.3, line),
        _circle(59.1, 39.1, 60.9, 40.9, line),
    ]
    figure.update_layout(shapes=shapes)


def _rect(x0: float, y0: float, x1: float, y1: float, line: dict[str, Any]) -> dict[str, Any]:
    return {"type": "rect", "x0": x0, "y0": y0, "x1": x1, "y1": y1, "line": line}


def _line(x0: float, y0: float, x1: float, y1: float, line: dict[str, Any]) -> dict[str, Any]:
    return {"type": "line", "x0": x0, "y0": y0, "x1": x1, "y1": y1, "line": line}


def _circle(x0: float, y0: float, x1: float, y1: float, line: dict[str, Any]) -> dict[str, Any]:
    return {"type": "circle", "x0": x0, "y0": y0, "x1": x1, "y1": y1, "line": line}
