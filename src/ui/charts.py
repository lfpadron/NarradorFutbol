"""Basic Plotly charts for the Streamlit app."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

HOME_COLOR = "#d62728"
HOME_LIGHT = "#f3a5a5"
AWAY_COLOR = "#1f77b4"
AWAY_LIGHT = "#9fc5f8"
ON_TARGET_OUTCOMES = {"Goal", "Saved", "Saved to Post"}


def shot_count_bar(team_stats: list[dict[str, Any]]) -> go.Figure:
    frame = pd.DataFrame(team_stats)
    if frame.empty:
        return _empty_figure("Sin tiros")
    return px.bar(frame, x="team_name", y="shots", labels={"team_name": "Equipo", "shots": "Tiros"})


def shots_on_target_bar(shots: list[dict[str, Any]], home_team: str, away_team: str) -> go.Figure:
    frame = pd.DataFrame(shots)
    teams = _ordered_teams(frame["team_name"].dropna().unique().tolist() if not frame.empty else [], home_team, away_team)
    if frame.empty or "shot_outcome_name" not in frame.columns or not teams:
        return _empty_figure("Sin tiros a gol")

    frame["is_goal"] = frame["shot_outcome_name"].eq("Goal")
    frame["is_on_target"] = frame["shot_outcome_name"].isin(ON_TARGET_OUTCOMES)
    on_target = frame[frame["is_on_target"]]
    if on_target.empty:
        return _empty_figure("Sin tiros a gol")

    labels: list[str] = []
    goals: list[int] = []
    on_target_without_goal: list[int] = []
    strong_colors: list[str] = []
    light_colors: list[str] = []
    for team_name in teams:
        subset = on_target[on_target["team_name"] == team_name]
        goal_count = int(subset["is_goal"].sum())
        no_goal_count = int(len(subset) - goal_count)
        labels.append(_team_label(team_name, home_team, away_team))
        goals.append(goal_count)
        on_target_without_goal.append(no_goal_count)
        strong_colors.append(_team_color(team_name, home_team, away_team, light=False))
        light_colors.append(_team_color(team_name, home_team, away_team, light=True))

    figure = go.Figure()
    figure.add_trace(
        go.Bar(
            x=labels,
            y=goals,
            name="Goles",
            marker={"color": strong_colors},
            text=[_bar_text(value) for value in goals],
            textposition="inside",
            insidetextanchor="middle",
            textfont={"color": "white", "size": 13},
            hovertemplate="%{x}<br>Goles: %{y}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            x=labels,
            y=on_target_without_goal,
            name="Tiros a gol sin gol",
            marker={"color": light_colors},
            text=[_bar_text(value) for value in on_target_without_goal],
            textposition="inside",
            insidetextanchor="middle",
            textfont={"color": "#10243a", "size": 13},
            hovertemplate="%{x}<br>Tiros a gol sin gol: %{y}<extra></extra>",
        )
    )
    figure.update_layout(
        title="Tiros a gol",
        barmode="stack",
        xaxis_title="Equipo",
        yaxis_title="Eventos",
        template="plotly_white",
        legend_title_text="Tipo",
        uniformtext_minsize=10,
        uniformtext_mode="show",
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.22,
            "xanchor": "center",
            "x": 0.5,
        },
        margin={"l": 35, "r": 25, "t": 60, "b": 90},
    )
    return figure


def xg_bar(team_stats: list[dict[str, Any]], home_team: str | None = None, away_team: str | None = None) -> go.Figure:
    frame = pd.DataFrame(team_stats)
    if frame.empty:
        return _empty_figure("Sin xG")
    figure = px.bar(frame, x="team_name", y="xg", labels={"team_name": "Equipo", "xg": "xG"})
    if home_team or away_team:
        figure.update_traces(marker_color=[_team_color(team, home_team, away_team) for team in frame["team_name"]])
    figure.update_layout(title="xG")
    return figure


def momentum_line(
    momentum_rows: list[dict[str, Any]],
    home_team: str | None = None,
    away_team: str | None = None,
) -> go.Figure:
    frame = pd.DataFrame(momentum_rows)
    if frame.empty:
        return _empty_figure("Sin momentum")
    frame["interval_label"] = frame["interval_start"].astype(str) + "-" + frame["interval_end"].astype(str)
    figure = px.line(
        frame,
        x="interval_start",
        y="momentum_score",
        color="team_name",
        color_discrete_map={
            str(home_team): HOME_COLOR,
            str(away_team): AWAY_COLOR,
        },
        markers=True,
        hover_data={
            "interval_label": True,
            "shots": True,
            "xg": ":.2f",
            "final_third_entries": True,
            "attacking_events": True,
        },
        labels={
            "interval_start": "Minuto",
            "momentum_score": "Momentum",
            "team_name": "Equipo",
            "interval_label": "Intervalo",
            "shots": "Tiros",
            "xg": "xG",
            "final_third_entries": "Entradas al tercio final",
            "attacking_events": "Eventos ofensivos",
        },
    )
    figure.update_layout(
        title="Momentum por intervalos",
        hovermode="x unified",
        template="plotly_white",
        yaxis_title="Momentum score",
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.22,
            "xanchor": "center",
            "x": 0.5,
        },
        margin={"l": 35, "r": 25, "t": 60, "b": 90},
    )
    return figure


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, xaxis={"visible": False}, yaxis={"visible": False})
    return figure


def _team_color(team_name: Any, home_team: str | None, away_team: str | None, light: bool = False) -> str:
    if team_name == home_team:
        return HOME_LIGHT if light else HOME_COLOR
    if team_name == away_team:
        return AWAY_LIGHT if light else AWAY_COLOR
    return "#a9d6b8" if light else "#2ca02c"


def _team_label(team_name: Any, home_team: str | None, away_team: str | None) -> str:
    if team_name == home_team:
        return f"Local ({team_name})"
    if team_name == away_team:
        return f"Visitante ({team_name})"
    return str(team_name)


def _ordered_teams(teams: list[Any], home_team: str | None, away_team: str | None) -> list[Any]:
    ordered: list[Any] = []
    for team in (home_team, away_team):
        if team and team in teams and team not in ordered:
            ordered.append(team)
    ordered.extend(team for team in teams if team not in ordered)
    return ordered


def _bar_text(value: int) -> str:
    return str(value) if value > 0 else ""
