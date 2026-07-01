"""Advanced match chart data and Plotly figures."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.graph_objects as go

from src.analytics.db import query_records
from src.analytics.momentum import get_momentum_by_interval
from src.analytics.pass_analysis import get_pass_network
from src.analytics.pitch import (
    PITCH_LENGTH,
    PITCH_WIDTH,
    annotate_empty,
    build_pitch_figure,
    is_valid_pitch_point,
    pitch_bin,
    zone_label,
)

RECOVERY_TYPES = {"Ball Recovery", "Interception"}
LOSS_TYPES = {"Dispossessed", "Miscontrol", "Error"}
HOME_COLOR = "#d62728"
AWAY_COLOR = "#1f77b4"
OTHER_COLOR = "#2ca02c"
ON_TARGET_OUTCOMES = {"Goal", "Saved", "Saved to Post"}
SHOT_COUNT_HOME_COLOR = "#fb923c"
SHOT_COUNT_AWAY_COLOR = "#7dd3fc"
GOAL_MARKER_COLOR = "#facc15"


def get_match_teams(match_id: int) -> list[str]:
    rows = query_records(
        """
        SELECT team_name
        FROM (
            SELECT home_team_name AS team_name FROM "match" WHERE match_id = ?
            UNION
            SELECT away_team_name AS team_name FROM "match" WHERE match_id = ?
        )
        WHERE team_name IS NOT NULL
        ORDER BY team_name
        """,
        (match_id, match_id),
    )
    return [str(row["team_name"]) for row in rows if row.get("team_name")]


def get_players_for_heatmap(match_id: int, team_name: str | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT
            player_id,
            MAX(player_name) AS player_name,
            MAX(team_name) AS team_name,
            COUNT(*) AS events
        FROM event
        WHERE match_id = ?
          AND player_id IS NOT NULL
          AND location_x IS NOT NULL
          AND location_y IS NOT NULL
    """
    params: list[Any] = [match_id]
    if team_name:
        sql += " AND team_name = ?"
        params.append(team_name)
    sql += """
        GROUP BY player_id
        ORDER BY events DESC, player_name
    """
    return query_records(sql, params)


def get_event_locations(
    match_id: int,
    team_name: str | None = None,
    player_id: int | None = None,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            event_id,
            minute,
            second,
            team_name,
            player_name,
            type_name,
            location_x,
            location_y
        FROM event
        WHERE match_id = ?
          AND location_x IS NOT NULL
          AND location_y IS NOT NULL
    """
    params: list[Any] = [match_id]
    if team_name:
        sql += " AND team_name = ?"
        params.append(team_name)
    if player_id is not None:
        sql += " AND player_id = ?"
        params.append(player_id)
    sql += " ORDER BY minute, second, event_index"
    return query_records(sql, params)


def get_shot_map_rows(match_id: int, team_name: str | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT
            e.event_id,
            e.minute,
            e.second,
            e.team_name,
            e.player_name,
            e.location_x,
            e.location_y,
            s.shot_statsbomb_xg,
            s.shot_outcome_name,
            s.shot_body_part_name
        FROM event e
        INNER JOIN shot s ON s.event_id = e.event_id
        WHERE e.match_id = ?
    """
    params: list[Any] = [match_id]
    if team_name:
        sql += " AND e.team_name = ?"
        params.append(team_name)
    sql += " ORDER BY e.minute, e.second, e.event_index"
    return query_records(sql, params)


def get_pass_map_rows(
    match_id: int,
    team_name: str | None = None,
    only_completed: bool = True,
) -> list[dict[str, Any]]:
    sql = """
        SELECT
            e.event_id,
            e.minute,
            e.second,
            e.team_name,
            e.player_name,
            p.recipient_player_name,
            e.location_x,
            e.location_y,
            p.pass_end_x,
            p.pass_end_y,
            p.pass_outcome_name
        FROM event e
        INNER JOIN "pass" p ON p.event_id = e.event_id
        WHERE e.match_id = ?
          AND e.location_x IS NOT NULL
          AND e.location_y IS NOT NULL
          AND p.pass_end_x IS NOT NULL
          AND p.pass_end_y IS NOT NULL
    """
    params: list[Any] = [match_id]
    if team_name:
        sql += " AND e.team_name = ?"
        params.append(team_name)
    if only_completed:
        sql += " AND p.pass_outcome_name IS NULL"
    sql += " ORDER BY e.minute, e.second, e.event_index"
    return query_records(sql, params)


def get_recovery_loss_rows(match_id: int, team_name: str | None = None) -> list[dict[str, Any]]:
    sql = """
        SELECT
            event_id,
            minute,
            second,
            team_name,
            player_name,
            type_name,
            location_x,
            location_y,
            CASE
                WHEN type_name IN ('Ball Recovery', 'Interception') THEN 'recuperación'
                WHEN type_name IN ('Dispossessed', 'Miscontrol', 'Error') THEN 'pérdida'
                ELSE 'otro'
            END AS event_group
        FROM event
        WHERE match_id = ?
          AND location_x IS NOT NULL
          AND location_y IS NOT NULL
          AND type_name IN ('Ball Recovery', 'Interception', 'Dispossessed', 'Miscontrol', 'Error')
    """
    params: list[Any] = [match_id]
    if team_name:
        sql += " AND team_name = ?"
        params.append(team_name)
    sql += " ORDER BY minute, second, event_index"
    return query_records(sql, params)


def build_presence_zones(events: list[dict[str, Any]], x_bins: int = 6, y_bins: int = 4) -> list[dict[str, Any]]:
    counts: dict[tuple[str, int, int], int] = {}
    totals: dict[str, int] = {}
    for row in events:
        team_name = str(row.get("team_name") or "Sin equipo")
        zone = pitch_bin(row.get("location_x"), row.get("location_y"), x_bins=x_bins, y_bins=y_bins)
        if zone is None:
            continue
        key = (team_name, zone[0], zone[1])
        counts[key] = counts.get(key, 0) + 1
        totals[team_name] = totals.get(team_name, 0) + 1

    result = []
    for (team_name, x_bin, y_bin), events_count in sorted(counts.items()):
        total = totals.get(team_name, 0)
        result.append(
            {
                "team_name": team_name,
                "x_bin": x_bin,
                "y_bin": y_bin,
                "zone": zone_label(x_bin, y_bin, x_bins=x_bins, y_bins=y_bins),
                "events": events_count,
                "share_pct": round(100.0 * events_count / total, 2) if total else 0,
            }
        )
    return result


def plot_event_heatmap(
    events: list[dict[str, Any]],
    title: str = "Mapa de calor de eventos",
    home_team_name: str | None = None,
    away_team_name: str | None = None,
) -> go.Figure:
    figure = build_pitch_figure(title)
    rows = [row for row in events if is_valid_pitch_point(row.get("location_x"), row.get("location_y"))]
    if not rows:
        return annotate_empty(figure, "Sin eventos con coordenadas para mapa de calor")

    frame = pd.DataFrame(rows)
    teams = _ordered_teams(frame["team_name"].dropna().unique().tolist(), home_team_name, away_team_name)
    for team_name in teams:
        subset = frame[frame["team_name"] == team_name]
        if subset.empty:
            continue
        color = _team_color(team_name, home_team_name, away_team_name)
        figure.add_trace(
            go.Histogram2d(
                x=subset["location_x"],
                y=subset["location_y"],
                nbinsx=24,
                nbinsy=16,
                colorscale=_heatmap_colorscale(color),
                opacity=0.76,
                showscale=False,
                showlegend=True,
                name=_team_role_label(team_name, home_team_name, away_team_name),
                hovertemplate="x: %{x}<br>y: %{y}<br>eventos: %{z}<extra></extra>",
            )
        )
    _legend_below(figure)
    return figure


def plot_shots_advanced(
    shots: list[dict[str, Any]],
    home_team_name: str | None = None,
    away_team_name: str | None = None,
) -> go.Figure:
    figure = build_pitch_figure("Mapa de tiros avanzado")
    rows = [row for row in shots if is_valid_pitch_point(row.get("location_x"), row.get("location_y"))]
    if not rows:
        return annotate_empty(figure, "Sin tiros con coordenadas")

    frame = pd.DataFrame(rows)
    frame["xg"] = pd.to_numeric(frame.get("shot_statsbomb_xg"), errors="coerce").fillna(0)
    frame["is_goal"] = frame["shot_outcome_name"].eq("Goal")
    frame["display_x"] = frame.apply(lambda row: _oriented_x(row["location_x"], row.get("team_name"), away_team_name), axis=1)
    frame["display_y"] = pd.to_numeric(frame["location_y"], errors="coerce")
    for team_name in _ordered_teams(frame["team_name"].dropna().unique().tolist(), home_team_name, away_team_name):
        team_subset = frame[frame["team_name"] == team_name]
        if team_subset.empty:
            continue
        color = _team_color(team_name, home_team_name, away_team_name)
        team_label = _team_role_label(team_name, home_team_name, away_team_name)
        for is_goal, symbol, event_label in ((False, "circle", "Tiro"), (True, "star", "Gol")):
            subset = team_subset[team_subset["is_goal"] == is_goal]
            if subset.empty:
                continue
            figure.add_trace(
                go.Scatter(
                    x=subset["display_x"],
                    y=subset["display_y"],
                    mode="markers",
                    name=f"{team_label} - {event_label}",
                    marker={
                        "size": subset["xg"].map(lambda value: 9 + max(float(value), 0) ** 0.5 * 30),
                        "color": color,
                        "symbol": symbol,
                        "line": {"color": "white", "width": 1.5},
                        "opacity": 0.88,
                    },
                    customdata=subset[["team_name", "player_name", "minute", "second", "xg", "shot_outcome_name"]],
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


def plot_pass_map(
    passes: list[dict[str, Any]],
    max_arrows: int = 350,
    home_team_name: str | None = None,
    away_team_name: str | None = None,
) -> go.Figure:
    figure = build_pitch_figure("Mapa de pases")
    rows = [
        row
        for row in passes
        if is_valid_pitch_point(row.get("location_x"), row.get("location_y"))
        and is_valid_pitch_point(row.get("pass_end_x"), row.get("pass_end_y"))
    ]
    if not rows:
        return annotate_empty(figure, "Sin pases con coordenadas")

    frame = pd.DataFrame(rows).head(max_arrows)
    frame["start_x"] = frame.apply(lambda row: _oriented_x(row["location_x"], row.get("team_name"), away_team_name), axis=1)
    frame["end_x"] = frame.apply(lambda row: _oriented_x(row["pass_end_x"], row.get("team_name"), away_team_name), axis=1)
    for team_name in _ordered_teams(frame["team_name"].dropna().unique().tolist(), home_team_name, away_team_name):
        subset = frame[frame["team_name"] == team_name]
        color = _team_color(team_name, home_team_name, away_team_name)
        team_label = _team_role_label(team_name, home_team_name, away_team_name)
        figure.add_trace(
            go.Scatter(
                x=subset["start_x"],
                y=subset["location_y"],
                mode="markers",
                name=team_label,
                marker={"size": 5, "color": color, "opacity": 0.45},
                customdata=subset[["player_name", "recipient_player_name", "minute", "second"]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b> a %{customdata[1]}<br>"
                    "Minuto %{customdata[2]}:%{customdata[3]:02d}<extra></extra>"
                ),
            )
        )
        for row in subset.itertuples(index=False):
            figure.add_annotation(
                x=row.end_x,
                y=row.pass_end_y,
                ax=row.start_x,
                ay=row.location_y,
                xref="x",
                yref="y",
                axref="x",
                ayref="y",
                showarrow=True,
                arrowhead=3,
                arrowsize=1,
                arrowwidth=1,
                arrowcolor=color,
                opacity=0.28,
            )
    _legend_below(figure)
    return figure


def plot_recoveries_losses(
    rows: list[dict[str, Any]],
    home_team_name: str | None = None,
    away_team_name: str | None = None,
) -> go.Figure:
    figure = build_pitch_figure("Recuperaciones y pérdidas")
    valid_rows = [row for row in rows if is_valid_pitch_point(row.get("location_x"), row.get("location_y"))]
    if not valid_rows:
        return annotate_empty(figure, "Sin recuperaciones o pérdidas con coordenadas")

    frame = pd.DataFrame(valid_rows)
    frame["display_x"] = frame.apply(lambda row: _oriented_x(row["location_x"], row.get("team_name"), away_team_name), axis=1)
    frame["display_y"] = pd.to_numeric(frame["location_y"], errors="coerce")
    config = {
        "recuperación": {"symbol": "circle", "label": "Recuperaciones"},
        "pérdida": {"symbol": "x", "label": "Pérdidas"},
    }
    for team_name in _ordered_teams(frame["team_name"].dropna().unique().tolist(), home_team_name, away_team_name):
        team_subset = frame[frame["team_name"] == team_name]
        color = _team_color(team_name, home_team_name, away_team_name)
        team_label = _team_role_label(team_name, home_team_name, away_team_name)
        for group, subset in team_subset.groupby("event_group"):
            style = config.get(group, {"symbol": "circle-open", "label": str(group)})
            figure.add_trace(
                go.Scatter(
                    x=subset["display_x"],
                    y=subset["display_y"],
                    mode="markers",
                    name=f"{team_label} - {style['label']}",
                    marker={"size": 8, "color": color, "symbol": style["symbol"], "opacity": 0.75},
                    customdata=subset[["team_name", "player_name", "type_name", "minute", "second"]],
                    hovertemplate=(
                        "<b>%{customdata[1]}</b><br>"
                        "Equipo: %{customdata[0]}<br>"
                        "Tipo: %{customdata[2]}<br>"
                        "Minuto %{customdata[3]}:%{customdata[4]:02d}<extra></extra>"
                    ),
                ),
            )
    _legend_below(figure)
    return figure


def plot_momentum(
    interval_rows: list[dict[str, Any]],
    home_team_name: str | None = None,
    away_team_name: str | None = None,
) -> go.Figure:
    rows = interval_rows or []
    figure = go.Figure()
    if not rows:
        figure.update_layout(title="Momentum por intervalos", template="plotly_white")
        return annotate_empty(figure, "Sin datos para momentum")

    frame = pd.DataFrame(rows)
    frame["interval_label"] = frame["interval_start"].astype(str) + "-" + frame["interval_end"].astype(str)
    for team_name, subset in frame.groupby("team_name", dropna=False):
        figure.add_trace(
            go.Scatter(
                x=subset["interval_start"],
                y=subset["momentum_score"],
                mode="lines+markers",
                name=_team_role_label(team_name, home_team_name, away_team_name),
                line={"color": _team_color(team_name, home_team_name, away_team_name), "width": 2.5},
                marker={"color": _team_color(team_name, home_team_name, away_team_name), "size": 7},
                hovertemplate="Minuto %{x}<br>Momentum %{y:.1f}<extra></extra>",
            )
        )
    figure.update_layout(
        title="Momentum por intervalos",
        xaxis_title="Minuto inicial",
        yaxis_title="Score de momentum",
        template="plotly_white",
        hovermode="x unified",
    )
    _legend_below(figure)
    return figure


def plot_broadcast_momentum(
    interval_rows: list[dict[str, Any]],
    home_team_name: str | None = None,
    away_team_name: str | None = None,
    shots: list[dict[str, Any]] | None = None,
) -> go.Figure:
    rows = interval_rows or []
    figure = go.Figure()
    if not rows:
        figure.update_layout(title="MATCH MOMENTUM", template="plotly_dark")
        return annotate_empty(figure, "Sin datos para momentum")

    frame = pd.DataFrame(rows)
    frame["interval_start"] = pd.to_numeric(frame.get("interval_start"), errors="coerce")
    frame["interval_end"] = pd.to_numeric(frame.get("interval_end"), errors="coerce")
    frame["momentum_score"] = pd.to_numeric(frame.get("momentum_score"), errors="coerce").fillna(0)
    frame["team_name"] = frame.get("team_name", "Sin equipo").fillna("Sin equipo").astype(str)
    frame = frame.dropna(subset=["interval_start"])
    if frame.empty:
        figure.update_layout(title="MATCH MOMENTUM", template="plotly_dark")
        return annotate_empty(figure, "Sin datos para momentum")

    teams = [team for team in frame["team_name"].dropna().unique().tolist() if team]
    home_label = str(home_team_name or "").strip()
    away_label = str(away_team_name or "").strip()
    home_key = home_label if home_label in teams else (teams[0] if teams else home_label)
    away_key = away_label if away_label in teams else next((team for team in teams if team != home_key), away_label)
    home_label = home_label or home_key or "Local"
    away_label = away_label or away_key or "Visitante"

    interval_lengths = (frame["interval_end"] - frame["interval_start"]).dropna()
    interval_size = int(interval_lengths.mode().iloc[0]) if not interval_lengths.empty else 5
    interval_size = max(interval_size, 1)
    max_end = frame["interval_end"].max()
    if pd.isna(max_end):
        max_end = frame["interval_start"].max() + interval_size
    end_minute = int(max(interval_size, max_end))
    timeline = list(range(0, end_minute + 1, interval_size))
    if not timeline or timeline[-1] < end_minute:
        timeline.append(end_minute)

    grouped = (
        frame.groupby(["interval_start", "team_name"], dropna=False)["momentum_score"]
        .sum()
        .reset_index()
    )
    home_scores = (
        grouped[grouped["team_name"].eq(home_key)]
        .set_index("interval_start")["momentum_score"]
        .reindex(timeline, fill_value=0)
    )
    away_scores = (
        grouped[grouped["team_name"].eq(away_key)]
        .set_index("interval_start")["momentum_score"]
        .reindex(timeline, fill_value=0)
    )
    net_scores = home_scores - away_scores
    positive_scores = net_scores.clip(lower=0)
    negative_scores = net_scores.clip(upper=0)
    max_abs = max(float(net_scores.abs().max() or 0), 1.0)
    y_limit = max_abs * 1.35
    outer_y_limit = y_limit * 1.22
    left_gutter = max(4, end_minute * 0.08)
    hover_rows = list(zip(home_scores, away_scores, net_scores))

    figure.add_trace(
        go.Scatter(
            x=timeline,
            y=positive_scores,
            mode="lines",
            name=f"Local: {home_label}",
            line={"color": "#dc2626", "width": 2, "shape": "spline"},
            fill="tozeroy",
            fillcolor="rgba(220, 38, 38, 0.82)",
            customdata=hover_rows,
            hovertemplate=(
                "Minuto %{x}'<br>"
                f"{home_label}: %{{customdata[0]:.1f}}<br>"
                f"{away_label}: %{{customdata[1]:.1f}}<br>"
                "Diferencia: %{customdata[2]:+.1f}<extra></extra>"
            ),
        )
    )
    figure.add_trace(
        go.Scatter(
            x=timeline,
            y=negative_scores,
            mode="lines",
            name=f"Visitante: {away_label}",
            line={"color": "#2563eb", "width": 2, "shape": "spline"},
            fill="tozeroy",
            fillcolor="rgba(37, 99, 235, 0.78)",
            customdata=hover_rows,
            hovertemplate=(
                "Minuto %{x}'<br>"
                f"{home_label}: %{{customdata[0]:.1f}}<br>"
                f"{away_label}: %{{customdata[1]:.1f}}<br>"
                "Diferencia: %{customdata[2]:+.1f}<extra></extra>"
            ),
        )
    )

    _add_broadcast_shot_counts(
        figure,
        shots or [],
        home_key,
        away_key,
        interval_size,
        end_minute,
        y_limit,
    )
    _add_broadcast_goal_markers(
        figure,
        shots or [],
        home_key,
        away_key,
        y_limit,
    )

    tick_end = max(45, ((end_minute + 14) // 15) * 15)
    ticks = list(range(0, tick_end + 1, 15))
    figure.add_hline(y=0, line={"color": "rgba(255,255,255,0.55)", "width": 2})
    figure.add_annotation(
        x=-left_gutter * 0.54,
        y=y_limit * 0.45,
        text=f"<b>LOCAL</b><br>{home_label}",
        showarrow=False,
        align="center",
        font={"size": 11, "color": "#ffffff"},
        bgcolor="rgba(220, 38, 38, 0.94)",
        bordercolor="rgba(255,255,255,0.75)",
        borderwidth=1,
    )
    figure.add_annotation(
        x=-left_gutter * 0.54,
        y=-y_limit * 0.45,
        text=f"<b>VISITA</b><br>{away_label}",
        showarrow=False,
        align="center",
        font={"size": 11, "color": "#ffffff"},
        bgcolor="rgba(37, 99, 235, 0.94)",
        bordercolor="rgba(255,255,255,0.75)",
        borderwidth=1,
    )
    figure.update_layout(
        title={
            "text": "<b>MATCH MOMENTUM</b>",
            "x": 0.5,
            "xanchor": "center",
            "font": {"color": "#ffffff"},
        },
        height=360,
        margin={"l": 18, "r": 24, "t": 64, "b": 95},
        plot_bgcolor="#263027",
        paper_bgcolor="#172018",
        font={"color": "#f8fafc", "family": "Arial"},
        hovermode="x unified",
        legend={
            "orientation": "h",
            "x": 0.5,
            "xanchor": "center",
            "y": -0.22,
            "yanchor": "top",
            "bgcolor": "rgba(0,0,0,0)",
            "font": {"color": "#ffffff"},
        },
        xaxis={
            "range": [-left_gutter, end_minute],
            "tickmode": "array",
            "tickvals": ticks,
            "ticktext": [f"{tick}'" for tick in ticks],
            "showgrid": True,
            "gridcolor": "rgba(255,255,255,0.14)",
            "zeroline": False,
            "title": "",
            "tickfont": {"color": "#ffffff"},
        },
        yaxis={
            "range": [-outer_y_limit, outer_y_limit],
            "showticklabels": False,
            "showgrid": False,
            "zeroline": False,
            "title": "",
        },
    )
    return figure


def _add_broadcast_shot_counts(
    figure: go.Figure,
    shots: list[dict[str, Any]],
    home_team_name: Any,
    away_team_name: Any,
    interval_size: int,
    end_minute: int,
    y_limit: float,
) -> None:
    shot_frame = _broadcast_shot_frame(shots)
    if shot_frame.empty:
        return

    interval_starts = list(range(0, max(end_minute, interval_size), interval_size))
    if not interval_starts:
        return
    x_values = [min(start + interval_size / 2, end_minute) for start in interval_starts]
    top_counts = _shots_on_target_counts(shot_frame, home_team_name, interval_size, interval_starts)
    bottom_counts = _shots_on_target_counts(shot_frame, away_team_name, interval_size, interval_starts)
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=[y_limit * 1.08] * len(x_values),
            mode="text",
            text=[str(value) for value in top_counts],
            textfont={"color": SHOT_COUNT_HOME_COLOR, "size": 12, "family": "Arial Black, Arial"},
            name="Tiros a gol local",
            hoverinfo="skip",
            showlegend=False,
        )
    )
    figure.add_trace(
        go.Scatter(
            x=x_values,
            y=[-y_limit * 1.08] * len(x_values),
            mode="text",
            text=[str(value) for value in bottom_counts],
            textfont={"color": SHOT_COUNT_AWAY_COLOR, "size": 12, "family": "Arial Black, Arial"},
            name="Tiros a gol visitante",
            hoverinfo="skip",
            showlegend=False,
        )
    )


def _add_broadcast_goal_markers(
    figure: go.Figure,
    shots: list[dict[str, Any]],
    home_team_name: Any,
    away_team_name: Any,
    y_limit: float,
) -> None:
    shot_frame = _broadcast_shot_frame(shots)
    if shot_frame.empty:
        return
    goals = shot_frame[shot_frame["shot_outcome_name"].eq("Goal")]
    if goals.empty:
        return
    for team_name, y_value, textposition in (
        (home_team_name, y_limit * 0.86, "top center"),
        (away_team_name, -y_limit * 0.86, "bottom center"),
    ):
        subset = goals[goals["team_name"].eq(team_name)]
        if subset.empty:
            continue
        figure.add_trace(
            go.Scatter(
                x=subset["time_value"],
                y=[y_value] * len(subset),
                mode="markers+text",
                text=subset["player_name"].map(_short_name),
                textposition=textposition,
                textfont={"color": "#ffffff", "size": 10},
                marker={
                    "symbol": "star",
                    "size": 16,
                    "color": GOAL_MARKER_COLOR,
                    "line": {"color": "#ffffff", "width": 1.4},
                },
                customdata=subset[["player_name", "team_name", "minute", "second"]],
                hovertemplate=(
                    "<b>%{customdata[0]}</b><br>"
                    "Equipo: %{customdata[1]}<br>"
                    "Gol al %{customdata[2]}:%{customdata[3]:02d}<extra></extra>"
                ),
                name=f"Goles {_team_role_label(team_name, home_team_name, away_team_name)}",
                showlegend=False,
            )
        )


def _broadcast_shot_frame(shots: list[dict[str, Any]]) -> pd.DataFrame:
    rows = [shot for shot in shots if shot.get("team_name") is not None]
    if not rows:
        return pd.DataFrame()
    frame = pd.DataFrame(rows)
    for column, default in (
        ("minute", 0),
        ("second", 0),
        ("shot_outcome_name", ""),
        ("player_name", ""),
    ):
        if column not in frame.columns:
            frame[column] = default
    frame["minute"] = pd.to_numeric(frame["minute"], errors="coerce").fillna(0)
    frame["second"] = pd.to_numeric(frame["second"], errors="coerce").fillna(0)
    frame["time_value"] = frame["minute"] + frame["second"] / 60
    frame["team_name"] = frame["team_name"].fillna("Sin equipo").astype(str)
    frame["shot_outcome_name"] = frame["shot_outcome_name"].fillna("").astype(str)
    frame["player_name"] = frame["player_name"].fillna("").astype(str)
    return frame


def _shots_on_target_counts(
    shot_frame: pd.DataFrame,
    team_name: Any,
    interval_size: int,
    interval_starts: list[int],
) -> list[int]:
    subset = shot_frame[
        shot_frame["team_name"].eq(str(team_name))
        & shot_frame["shot_outcome_name"].isin(ON_TARGET_OUTCOMES)
    ].copy()
    if subset.empty:
        return [0 for _ in interval_starts]
    subset["interval_start"] = (subset["minute"] // interval_size * interval_size).astype(int)
    counts = subset.groupby("interval_start").size().to_dict()
    return [int(counts.get(start, 0)) for start in interval_starts]


def _legend_below(figure: go.Figure) -> None:
    figure.update_layout(
        legend={
            "orientation": "h",
            "yanchor": "top",
            "y": -0.12,
            "xanchor": "center",
            "x": 0.5,
        },
        margin={"l": 20, "r": 20, "t": 55, "b": 95},
    )


def _team_color(team_name: Any, home_team_name: str | None, away_team_name: str | None) -> str:
    if team_name == home_team_name:
        return HOME_COLOR
    if team_name == away_team_name:
        return AWAY_COLOR
    return OTHER_COLOR


def _team_role_label(team_name: Any, home_team_name: str | None, away_team_name: str | None) -> str:
    if team_name == home_team_name:
        return f"Local ({team_name})"
    if team_name == away_team_name:
        return f"Visitante ({team_name})"
    return str(team_name)


def _ordered_teams(teams: list[Any], home_team_name: str | None, away_team_name: str | None) -> list[Any]:
    ordered: list[Any] = []
    for team in (home_team_name, away_team_name):
        if team and team in teams and team not in ordered:
            ordered.append(team)
    ordered.extend(team for team in teams if team not in ordered)
    return ordered


def _oriented_x(x_value: Any, team_name: Any, away_team_name: str | None) -> float:
    x = float(x_value)
    if team_name == away_team_name:
        return float(PITCH_LENGTH) - x
    return x


def _heatmap_colorscale(hex_color: str) -> list[list[Any]]:
    red, green, blue = _hex_to_rgb(hex_color)
    return [
        [0.0, f"rgba({red},{green},{blue},0.00)"],
        [0.28, f"rgba({red},{green},{blue},0.18)"],
        [1.0, f"rgba({red},{green},{blue},0.86)"],
    ]


def _hex_to_rgb(hex_color: str) -> tuple[int, int, int]:
    color = hex_color.lstrip("#")
    if len(color) != 6:
        return (44, 100, 150)
    return int(color[0:2], 16), int(color[2:4], 16), int(color[4:6], 16)


def _short_name(name: Any) -> str:
    if not name:
        return ""
    parts = str(name).split()
    if len(parts) == 1:
        return parts[0][:14]
    return f"{parts[0][0]}. {parts[-1]}"[:18]


def plot_presence_zones(zones: list[dict[str, Any]], selected_team: str | None = None) -> go.Figure:
    figure = build_pitch_figure("Zonas de dominio o presencia")
    rows = [row for row in zones if selected_team is None or row.get("team_name") == selected_team]
    if not rows:
        return annotate_empty(figure, "Sin zonas calculadas con coordenadas")

    for row in rows:
        x0 = row["x_bin"] * PITCH_LENGTH / 6
        x1 = (row["x_bin"] + 1) * PITCH_LENGTH / 6
        y0 = row["y_bin"] * PITCH_WIDTH / 4
        y1 = (row["y_bin"] + 1) * PITCH_WIDTH / 4
        opacity = min(0.78, 0.12 + float(row.get("share_pct") or 0) / 35)
        figure.add_shape(
            type="rect",
            x0=x0,
            x1=x1,
            y0=y0,
            y1=y1,
            line={"color": "rgba(20, 95, 80, 0.35)", "width": 1},
            fillcolor=f"rgba(20, 111, 84, {opacity})",
        )
        figure.add_annotation(
            x=(x0 + x1) / 2,
            y=(y0 + y1) / 2,
            text=f"{row.get('events')}<br>{row.get('share_pct')}%",
            showarrow=False,
            font={"size": 11, "color": "#10243a"},
            bgcolor="rgba(255,255,255,0.55)",
        )
    return figure


def build_advanced_chart_bundle(
    match_id: int, team_name: str | None = None, player_id: int | None = None
) -> dict[str, Any]:
    events = get_event_locations(match_id, team_name=team_name, player_id=player_id)
    shots = get_shot_map_rows(match_id, team_name=team_name)
    match_shots = get_shot_map_rows(match_id)
    passes = get_pass_map_rows(match_id, team_name=team_name)
    recovery_loss = get_recovery_loss_rows(match_id, team_name=team_name)
    zones = build_presence_zones(get_event_locations(match_id, team_name=team_name))
    momentum = get_momentum_by_interval(match_id)
    network = get_pass_network(match_id, team_name) if team_name else None
    return {
        "events": events,
        "shots": shots,
        "match_shots": match_shots,
        "passes": passes,
        "recovery_loss": recovery_loss,
        "zones": zones,
        "momentum": momentum,
        "pass_network": network,
    }
