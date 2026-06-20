"""Basic Plotly charts for the Streamlit app."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def shot_count_bar(team_stats: list[dict[str, Any]]) -> go.Figure:
    frame = pd.DataFrame(team_stats)
    if frame.empty:
        return _empty_figure("Sin tiros")
    return px.bar(frame, x="team_name", y="shots", labels={"team_name": "Equipo", "shots": "Tiros"})


def xg_bar(team_stats: list[dict[str, Any]]) -> go.Figure:
    frame = pd.DataFrame(team_stats)
    if frame.empty:
        return _empty_figure("Sin xG")
    return px.bar(frame, x="team_name", y="xg", labels={"team_name": "Equipo", "xg": "xG"})


def momentum_line(momentum_rows: list[dict[str, Any]]) -> go.Figure:
    frame = pd.DataFrame(momentum_rows)
    if frame.empty:
        return _empty_figure("Sin momentum")
    frame["interval_label"] = frame["interval_start"].astype(str) + "-" + frame["interval_end"].astype(str)
    return px.line(
        frame,
        x="interval_start",
        y="momentum_score",
        color="team_name",
        markers=True,
        labels={
            "interval_start": "Minuto",
            "momentum_score": "Momentum",
            "team_name": "Equipo",
        },
    )


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, xaxis={"visible": False}, yaxis={"visible": False})
    return figure
