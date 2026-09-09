"""Basic Plotly charts for the Streamlit app."""

from __future__ import annotations
from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from src.ui.i18n import t

HOME_COLOR = "#d62728"
HOME_LIGHT = "#f3a5a5"
AWAY_COLOR = "#1f77b4"
AWAY_LIGHT = "#9fc5f8"
ON_TARGET_OUTCOMES = {"Goal", "Saved", "Saved to Post"}


def shot_count_bar(team_stats: list[dict[str, Any]]) -> go.Figure:
    frame = pd.DataFrame(team_stats)
    if frame.empty:
        return _empty_figure("Sin tiros")
    return px.bar(frame, x="team_name", y="shots", labels={"team_name": t("Equipo"), "shots": t("Tiros")})


def shots_on_target_bar(shots: list[dict[str, Any]], home_team: str, away_team: str) -> go.Figure:
    frame = pd.DataFrame(shots)
    teams = _ordered_teams(
        frame["team_name"].dropna().unique().tolist() if not frame.empty else [], home_team, away_team
    )
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
            name=t("Goles"),
            marker={"color": strong_colors},
            text=[_bar_text(value) for value in goals],
            textposition="inside",
            insidetextanchor="middle",
            textfont={"color": "white", "size": 13},
            hovertemplate=f"%{{x}}<br>{t('Goles')}: %{{y}}<extra></extra>",
        )
    )
    figure.add_trace(
        go.Bar(
            x=labels,
            y=on_target_without_goal,
            name=t("Tiros a gol sin gol"),
            marker={"color": light_colors},
            text=[_bar_text(value) for value in on_target_without_goal],
            textposition="inside",
            insidetextanchor="middle",
            textfont={"color": "#10243a", "size": 13},
            hovertemplate=f"%{{x}}<br>{t('Tiros a gol sin gol')}: %{{y}}<extra></extra>",
        )
    )
    figure.update_layout(
        title=t("Tiros a gol"),
        barmode="stack",
        xaxis_title=t("Equipo"),
        yaxis_title=t("Eventos"),
        template="plotly_white",
        legend_title_text=t("Tipo"),
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
    figure = px.bar(frame, x="team_name", y="xg", labels={"team_name": t("Equipo"), "xg": "xG"})
    if home_team or away_team:
        figure.update_traces(marker_color=[_team_color(team, home_team, away_team) for team in frame["team_name"]])
    figure.update_layout(title="xG")
    return figure


def xg_difference_timeline(
    shots: list[dict[str, Any]],
    home_team: str,
    away_team: str,
    interval_minutes: int = 5,
) -> list[dict[str, Any]]:
    frame = pd.DataFrame(shots)
    if interval_minutes <= 0:
        interval_minutes = 5

    if frame.empty:
        return _empty_xg_difference_rows(interval_minutes)

    minute_values = frame["minute"] if "minute" in frame.columns else pd.Series(0, index=frame.index)
    xg_values = frame["shot_statsbomb_xg"] if "shot_statsbomb_xg" in frame.columns else pd.Series(0, index=frame.index)
    frame["minute"] = pd.to_numeric(minute_values, errors="coerce").fillna(0).clip(lower=0)
    frame["xg"] = pd.to_numeric(xg_values, errors="coerce").fillna(0)
    if "team_name" not in frame.columns:
        frame["team_name"] = None
    observed_end = (int(frame["minute"].max()) // interval_minutes + 1) * interval_minutes
    end_minute = max(90, observed_end)
    interval_starts = list(range(0, end_minute, interval_minutes))

    frame = frame[frame["team_name"].isin([home_team, away_team])].copy()
    if not frame.empty:
        frame["interval_start"] = (frame["minute"] // interval_minutes * interval_minutes).astype(int)
        grouped = frame.groupby(["interval_start", "team_name"], as_index=False)["xg"].sum()
    else:
        grouped = pd.DataFrame(columns=["interval_start", "team_name", "xg"])

    rows: list[dict[str, Any]] = []
    cumulative = 0.0
    for start in interval_starts:
        interval = grouped[grouped["interval_start"] == start]
        home_xg = _team_interval_xg(interval, home_team)
        away_xg = _team_interval_xg(interval, away_team)
        xg_diff = away_xg - home_xg
        cumulative += xg_diff
        rows.append(
            {
                "interval_start": start,
                "interval_end": start + interval_minutes,
                "home_xg": round(home_xg, 4),
                "away_xg": round(away_xg, 4),
                "xg_diff": round(xg_diff, 4),
                "cumulative_xg_diff": round(cumulative, 4),
            }
        )
    return rows


def xg_difference_line(
    timeline_rows: list[dict[str, Any]],
    home_team: str,
    away_team: str,
    shots: list[dict[str, Any]] | None = None,
    home_score: int | None = None,
    away_score: int | None = None,
) -> go.Figure:
    frame = pd.DataFrame(timeline_rows)
    if frame.empty:
        return _empty_figure("Diferencial acumulado de xG")

    start = pd.DataFrame(
        [
            {
                "interval_start": 0,
                "interval_end": 0,
                "home_xg": 0,
                "away_xg": 0,
                "xg_diff": 0,
                "cumulative_xg_diff": 0,
            }
        ]
    )
    frame = pd.concat([start, frame], ignore_index=True)
    end_minute = float(frame["interval_end"].max())
    score_x = end_minute + 2
    goal_offset = _goal_axis_offset(frame["cumulative_xg_diff"])

    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=frame["interval_end"],
            y=frame["cumulative_xg_diff"],
            mode="lines+markers",
            line={"color": "#0D6B5F", "width": 3},
            marker={"size": 7, "color": "#0D6B5F"},
            customdata=frame[["interval_start", "interval_end", "home_xg", "away_xg", "xg_diff"]],
            hovertemplate=(
                f"{t('Intervalo')} %{{customdata[0]}}-%{{customdata[1]}} min<br>"
                f"{t('xG local')} ({home_team}): "
                "%{customdata[2]:.2f}<br>"
                f"{t('xG visitante')} ({away_team}): "
                "%{customdata[3]:.2f}<br>"
                f"{t('Diferencia del intervalo')}: %{{customdata[4]:.2f}}<br>"
                f"{t('Diferencial acumulado')}: %{{y:.2f}}<extra></extra>"
            ),
            name=t("Visitante - local"),
        )
    )
    figure.add_hline(y=0, line_dash="dash", line_color="#6C7683")
    _add_goal_markers(figure, shots or [], home_team, away_team, goal_offset)
    _add_final_score_markers(
        figure,
        score_x,
        goal_offset,
        home_team,
        away_team,
        home_score,
        away_score,
        shots or [],
    )
    figure.update_layout(
        title=t("Diferencial acumulado de xG"),
        xaxis_title=t("Minuto"),
        yaxis_title=f"{t('xG acumulado')}: {away_team} - {home_team}",
        hovermode="x unified",
        template="plotly_white",
        margin={"l": 45, "r": 70, "t": 60, "b": 60},
        xaxis={"range": [0, end_minute + 7]},
    )
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
            "interval_start": t("Minuto"),
            "momentum_score": "Momentum",
            "team_name": t("Equipo"),
            "interval_label": t("Intervalo"),
            "shots": t("Tiros"),
            "xg": "xG",
            "final_third_entries": t("Entradas al tercio final"),
            "attacking_events": t("Eventos ofensivos"),
        },
    )
    figure.update_layout(
        title=t("Momentum por intervalos"),
        hovermode="x unified",
        template="plotly_white",
        yaxis_title=t("Momentum score"),
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
    figure.update_layout(title=t(title), xaxis={"visible": False}, yaxis={"visible": False})
    return figure


def _team_color(team_name: Any, home_team: str | None, away_team: str | None, light: bool = False) -> str:
    if team_name == home_team:
        return HOME_LIGHT if light else HOME_COLOR
    if team_name == away_team:
        return AWAY_LIGHT if light else AWAY_COLOR
    return "#a9d6b8" if light else "#2ca02c"


def _team_label(team_name: Any, home_team: str | None, away_team: str | None) -> str:
    if team_name == home_team:
        return f"{t('Local')} ({team_name})"
    if team_name == away_team:
        return f"{t('Visitante')} ({team_name})"
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


def _add_goal_markers(
    figure: go.Figure,
    shots: list[dict[str, Any]],
    home_team: str,
    away_team: str,
    goal_offset: float,
) -> None:
    goals = _goal_events(shots, home_team, away_team)
    for role, y_value, color, name, textposition in (
        ("away", goal_offset, AWAY_COLOR, f"{t('Goles')} {t('visitante')} ({away_team})", "top center"),
        ("home", -goal_offset, HOME_COLOR, f"{t('Goles')} {t('local')} ({home_team})", "bottom center"),
    ):
        role_goals = [goal for goal in goals if goal["role"] == role]
        if not role_goals:
            continue
        figure.add_trace(
            go.Scatter(
                x=[goal["time_value"] for goal in role_goals],
                y=[y_value for _ in role_goals],
                mode="markers",
                name=name,
                marker={
                    "symbol": "star",
                    "size": 15,
                    "color": color,
                    "line": {"color": "white", "width": 2},
                },
                customdata=[[goal["player_name"], goal["team_name"], goal["minute_label"]] for goal in role_goals],
                hovertemplate=(
                    f"<b>{t('Gol')}</b><br>"
                    f"{t('Jugador')}: %{{customdata[0]}}<br>"
                    f"{t('Equipo')}: %{{customdata[1]}}<br>"
                    f"{t('Minuto')}: %{{customdata[2]}}<extra></extra>"
                ),
                textposition=textposition,
            )
        )


def _add_final_score_markers(
    figure: go.Figure,
    score_x: float,
    goal_offset: float,
    home_team: str,
    away_team: str,
    home_score: int | None,
    away_score: int | None,
    shots: list[dict[str, Any]],
) -> None:
    goals = _goal_events(shots, home_team, away_team)
    resolved_home_score = home_score if home_score is not None else sum(1 for goal in goals if goal["role"] == "home")
    resolved_away_score = away_score if away_score is not None else sum(1 for goal in goals if goal["role"] == "away")
    for y_value, color, text, hover_team in (
        (goal_offset, AWAY_COLOR, f"{t('Visitante')} {resolved_away_score}", away_team),
        (-goal_offset, HOME_COLOR, f"{t('Local')} {resolved_home_score}", home_team),
    ):
        figure.add_trace(
            go.Scatter(
                x=[score_x],
                y=[y_value],
                mode="markers+text",
                name=text,
                marker={
                    "symbol": "star",
                    "size": 16,
                    "color": color,
                    "line": {"color": "white", "width": 2},
                },
                text=[text],
                textposition="middle right",
                hovertemplate=f"{hover_team}<br>{text}<extra></extra>",
                showlegend=False,
            )
        )


def _goal_events(shots: list[dict[str, Any]], home_team: str, away_team: str) -> list[dict[str, Any]]:
    goals: list[dict[str, Any]] = []
    for shot in shots:
        if shot.get("shot_outcome_name") != "Goal":
            continue
        team_name = str(shot.get("team_name") or "")
        if team_name not in {home_team, away_team}:
            continue
        minute = _numeric_value(shot.get("minute"))
        second = _numeric_value(shot.get("second"))
        goals.append(
            {
                "role": "away" if team_name == away_team else "home",
                "team_name": team_name,
                "player_name": str(shot.get("player_name") or "N/D"),
                "time_value": minute + second / 60,
                "minute_label": f"{int(minute)}:{int(second):02d}",
            }
        )
    return sorted(goals, key=lambda goal: float(goal["time_value"]))


def _goal_axis_offset(values: pd.Series) -> float:
    max_abs = max(abs(float(values.min())), abs(float(values.max())), 0.5)
    return round(max(0.08, max_abs * 0.12), 4)


def _numeric_value(value: Any) -> float:
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _empty_xg_difference_rows(interval_minutes: int) -> list[dict[str, Any]]:
    rows = []
    for start in range(0, 90, interval_minutes):
        rows.append(
            {
                "interval_start": start,
                "interval_end": start + interval_minutes,
                "home_xg": 0.0,
                "away_xg": 0.0,
                "xg_diff": 0.0,
                "cumulative_xg_diff": 0.0,
            }
        )
    return rows


def _team_interval_xg(interval: pd.DataFrame, team_name: str) -> float:
    if interval.empty:
        return 0.0
    return float(interval.loc[interval["team_name"] == team_name, "xg"].sum())
