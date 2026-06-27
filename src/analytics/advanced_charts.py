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


def plot_event_heatmap(events: list[dict[str, Any]], title: str = "Mapa de calor de eventos") -> go.Figure:
    figure = build_pitch_figure(title)
    rows = [row for row in events if is_valid_pitch_point(row.get("location_x"), row.get("location_y"))]
    if not rows:
        return annotate_empty(figure, "Sin eventos con coordenadas para mapa de calor")

    frame = pd.DataFrame(rows)
    figure.add_trace(
        go.Histogram2d(
            x=frame["location_x"],
            y=frame["location_y"],
            nbinsx=24,
            nbinsy=16,
            colorscale="YlGnBu",
            opacity=0.78,
            showscale=True,
            colorbar={"title": "Eventos"},
            hovertemplate="x: %{x}<br>y: %{y}<br>eventos: %{z}<extra></extra>",
        )
    )
    return figure


def plot_shots_advanced(shots: list[dict[str, Any]]) -> go.Figure:
    figure = build_pitch_figure("Mapa de tiros avanzado")
    rows = [row for row in shots if is_valid_pitch_point(row.get("location_x"), row.get("location_y"))]
    if not rows:
        return annotate_empty(figure, "Sin tiros con coordenadas")

    frame = pd.DataFrame(rows)
    frame["xg"] = pd.to_numeric(frame.get("shot_statsbomb_xg"), errors="coerce").fillna(0)
    frame["is_goal"] = frame["shot_outcome_name"].eq("Goal")
    for is_goal, symbol, label, color in (
        (False, "circle", "Tiro", "#22577a"),
        (True, "star", "Gol", "#c43c5e"),
    ):
        subset = frame[frame["is_goal"] == is_goal]
        if subset.empty:
            continue
        figure.add_trace(
            go.Scatter(
                x=subset["location_x"],
                y=subset["location_y"],
                mode="markers",
                name=label,
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
    return figure


def plot_pass_map(passes: list[dict[str, Any]], max_arrows: int = 350) -> go.Figure:
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
    for team_name, subset in frame.groupby("team_name", dropna=False):
        color = "#226f54" if str(team_name) != "Sin equipo" else "#6b7280"
        figure.add_trace(
            go.Scatter(
                x=subset["location_x"],
                y=subset["location_y"],
                mode="markers",
                name=str(team_name),
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
                x=row.pass_end_x,
                y=row.pass_end_y,
                ax=row.location_x,
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
    return figure


def plot_recoveries_losses(rows: list[dict[str, Any]]) -> go.Figure:
    figure = build_pitch_figure("Recuperaciones y pérdidas")
    valid_rows = [row for row in rows if is_valid_pitch_point(row.get("location_x"), row.get("location_y"))]
    if not valid_rows:
        return annotate_empty(figure, "Sin recuperaciones o pérdidas con coordenadas")

    frame = pd.DataFrame(valid_rows)
    config = {
        "recuperación": {"symbol": "circle", "color": "#148f77", "label": "Recuperaciones"},
        "pérdida": {"symbol": "x", "color": "#c43c5e", "label": "Pérdidas"},
    }
    for group, subset in frame.groupby("event_group"):
        style = config.get(group, {"symbol": "circle-open", "color": "#6b7280", "label": str(group)})
        figure.add_trace(
            go.Scatter(
                x=subset["location_x"],
                y=subset["location_y"],
                mode="markers",
                name=style["label"],
                marker={"size": 8, "color": style["color"], "symbol": style["symbol"], "opacity": 0.75},
                customdata=subset[["team_name", "player_name", "type_name", "minute", "second"]],
                hovertemplate=(
                    "<b>%{customdata[1]}</b><br>"
                    "Equipo: %{customdata[0]}<br>"
                    "Tipo: %{customdata[2]}<br>"
                    "Minuto %{customdata[3]}:%{customdata[4]:02d}<extra></extra>"
                ),
            )
        )
    return figure


def plot_momentum(interval_rows: list[dict[str, Any]]) -> go.Figure:
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
                name=str(team_name),
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
    return figure


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
    passes = get_pass_map_rows(match_id, team_name=team_name)
    recovery_loss = get_recovery_loss_rows(match_id, team_name=team_name)
    zones = build_presence_zones(get_event_locations(match_id, team_name=team_name))
    momentum = get_momentum_by_interval(match_id)
    network = get_pass_network(match_id, team_name) if team_name else None
    return {
        "events": events,
        "shots": shots,
        "passes": passes,
        "recovery_loss": recovery_loss,
        "zones": zones,
        "momentum": momentum,
        "pass_network": network,
    }
