"""Football pitch visualizations for Streamlit."""

from __future__ import annotations

import math
from typing import Any

import pandas as pd
import plotly.graph_objects as go

PITCH_LENGTH = 120
PITCH_WIDTH = 80
HOME_COLOR = "#d62728"
AWAY_COLOR = "#1f77b4"


def plot_shot_map(
    shots: list[dict[str, Any]],
    home_team: str,
    away_team: str,
    label_mode: str = "none",
) -> go.Figure:
    figure = _pitch_figure("Mapa de tiros")
    valid = [shot for shot in shots if _valid_point(shot.get("location_x"), shot.get("location_y"))]
    if not valid:
        return _annotate_empty(figure, "Sin tiros con coordenadas validas")

    frame = pd.DataFrame(valid)
    frame["xg"] = pd.to_numeric(frame.get("shot_statsbomb_xg"), errors="coerce").fillna(0)
    frame["marker_size"] = frame["xg"].map(lambda value: 9 + math.sqrt(max(float(value), 0)) * 28)
    frame["is_goal"] = frame["shot_outcome_name"].eq("Goal")
    frame["display_x"] = frame.apply(lambda row: _shot_display_x(row, away_team), axis=1)
    frame["display_y"] = pd.to_numeric(frame["location_y"], errors="coerce")
    frame["team_role"] = frame["team_name"].map(lambda team: _team_role(team, home_team, away_team))
    frame["team_color"] = frame["team_name"].map(lambda team: _team_color(team, home_team, away_team))
    frame["label_text"] = frame.apply(lambda row: _shot_label(row, label_mode), axis=1)

    for team_name in _ordered_teams(frame["team_name"].dropna().unique().tolist(), home_team, away_team):
        team_subset = frame[frame["team_name"] == team_name]
        if team_subset.empty:
            continue
        role = _team_role(team_name, home_team, away_team)
        team_label = _team_role_label(role, team_name)
        for is_goal, symbol, event_label in ((False, "circle", "Tiro fallado"), (True, "star", "Gol")):
            subset = team_subset[team_subset["is_goal"] == is_goal]
            if subset.empty:
                continue
            text_values = subset["label_text"]
            show_text = text_values.astype(bool).any()
            figure.add_trace(
                go.Scatter(
                    x=subset["display_x"],
                    y=subset["display_y"],
                    mode="markers+text" if show_text else "markers",
                    text=text_values if show_text else None,
                    textposition="top center",
                    textfont={"size": 10, "color": "#10243a"},
                    name=f"{team_label} - {event_label}",
                    marker={
                        "size": subset["marker_size"],
                        "color": subset["team_color"],
                        "symbol": symbol,
                        "line": {"color": "white" if is_goal else "#10243a", "width": 2},
                        "opacity": 0.88,
                    },
                    customdata=subset[
                        [
                            "team_name",
                            "player_name",
                            "minute",
                            "second",
                            "shot_statsbomb_xg",
                            "shot_outcome_name",
                        ]
                    ],
                    hovertemplate=(
                        "<b>%{customdata[1]}</b><br>"
                        "Equipo: %{customdata[0]}<br>"
                        "Minuto: %{customdata[2]}:%{customdata[3]:02d}<br>"
                        "xG: %{customdata[4]:.2f}<br>"
                        "Resultado: %{customdata[5]}<extra></extra>"
                    ),
                )
            )
    _legend_below(figure)
    return figure


def plot_cumulative_xg(
    shots: list[dict[str, Any]],
    home_team: str | None = None,
    away_team: str | None = None,
) -> go.Figure:
    figure = go.Figure()
    valid = [shot for shot in shots if shot.get("team_name") is not None]
    if not valid:
        figure.update_layout(title="xG acumulado")
        return _annotate_empty(figure, "Sin tiros para calcular xG")

    frame = pd.DataFrame(valid)
    frame["minute"] = pd.to_numeric(frame["minute"], errors="coerce").fillna(0)
    frame["second"] = pd.to_numeric(frame["second"], errors="coerce").fillna(0)
    frame["time_value"] = frame["minute"] + frame["second"] / 60
    frame["xg"] = pd.to_numeric(frame.get("shot_statsbomb_xg"), errors="coerce").fillna(0)
    frame = frame.sort_values(["team_name", "time_value"])
    frame["cumulative_xg"] = frame.groupby("team_name")["xg"].cumsum()

    for team_name in _ordered_teams(frame["team_name"].dropna().unique().tolist(), home_team, away_team):
        subset = frame[frame["team_name"] == team_name]
        start = pd.DataFrame(
            [{"time_value": 0, "cumulative_xg": 0, "team_name": team_name, "player_name": "", "shot_outcome_name": ""}]
        )
        line = pd.concat([start, subset], ignore_index=True)
        color = _team_color(team_name, home_team, away_team)
        figure.add_trace(
            go.Scatter(
                x=line["time_value"],
                y=line["cumulative_xg"],
                mode="lines",
                line_shape="hv",
                line={"color": color, "width": 3},
                name=str(team_name),
                hovertemplate="Minuto %{x:.1f}<br>xG acumulado %{y:.2f}<extra></extra>",
            )
        )
        missed = subset[~subset["shot_outcome_name"].eq("Goal")]
        if not missed.empty:
            figure.add_trace(
                go.Scatter(
                    x=missed["time_value"],
                    y=missed["cumulative_xg"],
                    mode="markers",
                    name=f"Tiros fallados {team_name}",
                    marker={"symbol": "circle", "size": 9, "color": color, "line": {"width": 1.5, "color": "white"}},
                    customdata=missed[["player_name", "xg", "shot_outcome_name"]],
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "xG %{customdata[1]:.2f}<br>"
                        "Resultado: %{customdata[2]}<extra></extra>"
                    ),
                )
            )
        goals = subset[subset["shot_outcome_name"].eq("Goal")]
        if not goals.empty:
            figure.add_trace(
                go.Scatter(
                    x=goals["time_value"],
                    y=goals["cumulative_xg"],
                    mode="markers",
                    name=f"Goles {team_name}",
                    marker={"symbol": "star", "size": 15, "color": color, "line": {"width": 2, "color": "white"}},
                    customdata=goals[["player_name", "xg", "shot_outcome_name"]],
                    hovertemplate=(
                        "<b>%{customdata[0]}</b><br>"
                        "xG %{customdata[1]:.2f}<br>"
                        "Resultado: %{customdata[2]}<extra></extra>"
                    ),
                )
            )

    figure.update_layout(
        title="xG acumulado",
        xaxis_title="Minuto",
        yaxis_title="xG acumulado",
        hovermode="x unified",
        legend_title_text="Equipo",
        template="plotly_white",
    )
    _legend_below(figure)
    return figure


def plot_progressive_passes(
    progressive_passes: list[dict[str, Any]],
    selected_team: str | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> go.Figure:
    figure = _pitch_figure("Pases")
    rows = [
        row
        for row in progressive_passes
        if (selected_team is None or row.get("team_name") == selected_team)
        and _valid_point(row.get("location_x"), row.get("location_y"))
        and _valid_point(row.get("pass_end_x"), row.get("pass_end_y"))
    ]
    if not rows:
        return _annotate_empty(figure, "Sin pases progresivos con coordenadas")

    frame = pd.DataFrame(rows)
    frame["start_x"] = frame.apply(lambda row: _oriented_x(row.get("location_x"), row.get("team_name"), away_team), axis=1)
    frame["end_x"] = frame.apply(lambda row: _oriented_x(row.get("pass_end_x"), row.get("team_name"), away_team), axis=1)
    frame["start_y"] = pd.to_numeric(frame["location_y"], errors="coerce")
    frame["end_y"] = pd.to_numeric(frame["pass_end_y"], errors="coerce")
    if "pass_shot_assist" in frame.columns:
        frame["is_shot_assist"] = frame["pass_shot_assist"].fillna(False).astype(bool)
    else:
        frame["is_shot_assist"] = False
    for team_name in _ordered_teams(frame["team_name"].dropna().unique().tolist(), home_team, away_team):
        subset = frame[frame["team_name"] == team_name]
        color = _team_color(team_name, home_team, away_team)
        team_label = _team_role_label(_team_role(team_name, home_team, away_team), team_name)
        for is_shot_assist, dash, label in (
            (True, "solid", "Pase de asistencia"),
            (False, "dot", "Otros pases"),
        ):
            line_subset = subset[subset["is_shot_assist"] == is_shot_assist]
            if line_subset.empty:
                continue
            x_values: list[float | None] = []
            y_values: list[float | None] = []
            for row in line_subset.itertuples(index=False):
                x_values.extend([row.start_x, row.end_x, None])
                y_values.extend([row.start_y, row.end_y, None])
            figure.add_trace(
                go.Scatter(
                    x=x_values,
                    y=y_values,
                    mode="lines",
                    name=f"{team_label} - {label}",
                    line={"color": color, "width": 2.2 if is_shot_assist else 1.45, "dash": dash},
                    opacity=0.72 if is_shot_assist else 0.36,
                    hoverinfo="skip",
                )
            )
        figure.add_trace(
            go.Scatter(
                x=subset["start_x"],
                y=subset["start_y"],
                mode="markers",
                name=f"Origen {team_label}",
                marker={"size": 6, "color": color, "opacity": 0.55},
                customdata=subset[["player_name", "recipient_player_name", "minute", "second", "progressive_distance"]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b> a %{customdata[1]}<br>"
                    "Minuto %{customdata[2]}:%{customdata[3]:02d}<br>"
                    "Progresion %{customdata[4]:.1f}<extra></extra>"
                ),
            )
        )
    _legend_below(figure)
    return figure


def plot_pressure_map(
    pressures: list[dict[str, Any]],
    selected_team: str | None = None,
    home_team: str | None = None,
    away_team: str | None = None,
) -> go.Figure:
    figure = _pitch_figure("Mapa de presiones")
    rows = [
        row
        for row in pressures
        if (selected_team is None or row.get("team_name") == selected_team)
        and _valid_point(row.get("location_x"), row.get("location_y"))
    ]
    if not rows:
        return _annotate_empty(figure, "Sin presiones con coordenadas")

    frame = pd.DataFrame(rows)
    frame["counterpress_label"] = frame["counterpress"].map(lambda value: "Sí" if value else "No")
    frame["display_x"] = frame.apply(lambda row: _oriented_x(row.get("location_x"), row.get("team_name"), away_team), axis=1)
    frame["display_y"] = pd.to_numeric(frame["location_y"], errors="coerce")
    for team_name in _ordered_teams(frame["team_name"].dropna().unique().tolist(), home_team, away_team):
        subset = frame[frame["team_name"] == team_name]
        figure.add_trace(
            go.Scatter(
                x=subset["display_x"],
                y=subset["display_y"],
                mode="markers",
                name=_team_role_label(_team_role(team_name, home_team, away_team), team_name),
                marker={"size": 7, "color": _team_color(team_name, home_team, away_team), "opacity": 0.58},
                customdata=subset[["player_name", "minute", "second", "counterpress_label"]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Minuto %{customdata[1]}:%{customdata[2]:02d}<br>"
                    "Counterpress: %{customdata[3]}<extra></extra>"
                ),
            )
        )
    _legend_below(figure)
    return figure


def plot_pass_network(pass_network: dict[str, Any]) -> go.Figure:
    team_name = pass_network.get("team_name") or "Equipo"
    figure = _pitch_figure(f"Red de pases - {team_name}")
    nodes = [node for node in pass_network.get("nodes", []) if _valid_point(node.get("avg_x"), node.get("avg_y"))]
    if not nodes:
        return _annotate_empty(figure, "Sin nodos de pase con coordenadas")

    node_by_id = {node["player_id"]: node for node in nodes if node.get("player_id") is not None}
    max_weight = max((edge.get("weight") or 1 for edge in pass_network.get("edges", [])), default=1)

    for edge in pass_network.get("edges", []):
        source = node_by_id.get(edge.get("source_player_id"))
        target = node_by_id.get(edge.get("target_player_id"))
        if source is None or target is None:
            continue
        width = 1 + 5 * (float(edge.get("weight") or 1) / max_weight)
        figure.add_trace(
            go.Scatter(
                x=[source["avg_x"], target["avg_x"]],
                y=[source["avg_y"], target["avg_y"]],
                mode="lines",
                line={"width": width, "color": "rgba(44, 100, 150, 0.42)"},
                hoverinfo="text",
                text=f"{edge.get('source_player_name')} → {edge.get('target_player_name')}: {edge.get('weight')}",
                showlegend=False,
            )
        )

    node_frame = pd.DataFrame(nodes)
    node_frame["short_name"] = node_frame["player_name"].map(_short_name)
    node_frame["touches"] = pd.to_numeric(node_frame.get("touches"), errors="coerce").fillna(1)
    figure.add_trace(
        go.Scatter(
            x=node_frame["avg_x"],
            y=node_frame["avg_y"],
            mode="markers+text",
            name=str(team_name),
            text=node_frame["short_name"],
            textposition="top center",
            marker={
                "size": node_frame["touches"].map(lambda value: 9 + math.sqrt(float(value)) * 1.5),
                "color": "#226f54",
                "line": {"color": "white", "width": 1.5},
                "opacity": 0.92,
            },
            customdata=node_frame[["player_name", "touches"]],
            hovertemplate="<b>%{customdata[0]}</b><br>Eventos: %{customdata[1]}<extra></extra>",
        )
    )
    return figure


def _pitch_figure(title: str) -> go.Figure:
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


def _annotate_empty(figure: go.Figure, message: str) -> go.Figure:
    figure.add_annotation(
        text=message,
        x=60,
        y=40,
        showarrow=False,
        font={"size": 16, "color": "#344"},
        bgcolor="rgba(255,255,255,0.78)",
    )
    return figure


def _valid_point(x_value: Any, y_value: Any) -> bool:
    try:
        x = float(x_value)
        y = float(y_value)
    except (TypeError, ValueError):
        return False
    return 0 <= x <= PITCH_LENGTH and 0 <= y <= PITCH_WIDTH


def _team_color(team_name: Any, home_team: str | None, away_team: str | None) -> str:
    if team_name == home_team:
        return HOME_COLOR
    if team_name == away_team:
        return AWAY_COLOR
    return "#2ca02c"


def _team_role(team_name: Any, home_team: str | None, away_team: str | None) -> str:
    if team_name == home_team:
        return "home"
    if team_name == away_team:
        return "away"
    return "other"


def _team_role_label(role: str, team_name: Any) -> str:
    if role == "home":
        return f"Local ({team_name})"
    if role == "away":
        return f"Visitante ({team_name})"
    return str(team_name)


def _ordered_teams(teams: list[Any], home_team: str | None, away_team: str | None) -> list[Any]:
    ordered: list[Any] = []
    for team in (home_team, away_team):
        if team and team in teams and team not in ordered:
            ordered.append(team)
    ordered.extend(team for team in teams if team not in ordered)
    return ordered


def _shot_display_x(row: Any, away_team: str) -> float:
    return _oriented_x(row["location_x"], row.get("team_name"), away_team)


def _oriented_x(x_value: Any, team_name: Any, away_team: str | None) -> float:
    x = float(x_value)
    if team_name == away_team:
        return PITCH_LENGTH - x
    return x


def _shot_label(row: Any, label_mode: str) -> str:
    if label_mode == "goals" and not bool(row.get("is_goal")):
        return ""
    if label_mode not in {"goals", "shots"}:
        return ""
    return _short_name(row.get("player_name"))


def _color_by_team(teams: list[Any]) -> dict[Any, str]:
    palette = ["#1f77b4", "#c43c5e", "#226f54", "#9467bd", "#bc7c1a"]
    return {team: palette[index % len(palette)] for index, team in enumerate(teams)}


def _legend_below(figure: go.Figure) -> None:
    figure.update_layout(
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.08,
            "xanchor": "center",
            "x": 0.5,
        },
        margin={"l": 20, "r": 20, "t": 55, "b": 95},
    )


def _short_name(name: Any) -> str:
    if not name:
        return ""
    parts = str(name).split()
    if len(parts) == 1:
        return parts[0][:12]
    return f"{parts[0][0]}. {parts[-1]}"[:16]
