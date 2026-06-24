"""Plotly visualizations for player comparisons."""

from __future__ import annotations

from typing import Any

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go


def plot_player_radar(radar_metrics: dict[str, Any]) -> go.Figure:
    categories = list(radar_metrics.get("categories", []))
    player_a = radar_metrics.get("player_a", {})
    player_b = radar_metrics.get("player_b", {})
    if not categories:
        return _empty_figure("Radar comparativo")

    theta = categories + [categories[0]]
    values_a = list(player_a.get("values", []))
    values_b = list(player_b.get("values", []))
    values_a = values_a + [values_a[0] if values_a else 0]
    values_b = values_b + [values_b[0] if values_b else 0]

    figure = go.Figure()
    figure.add_trace(
        go.Scatterpolar(
            r=values_a,
            theta=theta,
            fill="toself",
            name=str(player_a.get("name") or "Jugador A"),
            line={"color": "#1f77b4"},
            fillcolor="rgba(31,119,180,0.18)",
        )
    )
    figure.add_trace(
        go.Scatterpolar(
            r=values_b,
            theta=theta,
            fill="toself",
            name=str(player_b.get("name") or "Jugador B"),
            line={"color": "#c43c5e"},
            fillcolor="rgba(196,60,94,0.18)",
        )
    )
    figure.update_layout(
        title="Radar comparativo",
        polar={"radialaxis": {"visible": True, "range": [0, 100]}},
        template="plotly_white",
        legend_title_text="Jugador",
        height=520,
        margin={"l": 40, "r": 40, "t": 70, "b": 35},
    )
    return figure


def plot_player_metric_bars(comparison: dict[str, Any]) -> go.Figure:
    player_a = comparison.get("player_a", {})
    player_b = comparison.get("player_b", {})
    rows = []
    for metric, label in (
        ("goals", "Goles"),
        ("shots", "Tiros"),
        ("xg", "xG"),
        ("assists", "Asistencias"),
        ("key_passes", "Pases clave"),
        ("progressive_passes", "Pases progresivos"),
        ("pressures", "Presiones"),
        ("impact_score", "Impact score"),
    ):
        rows.append({"Métrica": label, "Jugador": _player_label(player_a, "A"), "Valor": _number(player_a.get(metric))})
        rows.append({"Métrica": label, "Jugador": _player_label(player_b, "B"), "Valor": _number(player_b.get(metric))})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return _empty_figure("Métricas comparativas")
    figure = px.bar(
        frame,
        x="Métrica",
        y="Valor",
        color="Jugador",
        barmode="group",
        labels={"Valor": "Valor"},
        color_discrete_sequence=["#1f77b4", "#c43c5e"],
    )
    figure.update_layout(
        title="Métricas comparativas",
        template="plotly_white",
        height=430,
        legend_title_text="Jugador",
    )
    return figure


def plot_player_profile_groups(comparison: dict[str, Any]) -> go.Figure:
    player_a = comparison.get("player_a", {})
    player_b = comparison.get("player_b", {})
    rows = []
    groups = {
        "Ofensivo": ["shots", "goals", "xg", "carries"],
        "Creación": ["assists", "key_passes", "progressive_passes"],
        "Pase": ["passes", "successful_passes", "pass_accuracy_pct"],
        "Defensivo": ["pressures", "duels", "fouls_won"],
        "Impacto": ["impact_score", "key_moments_count", "events"],
    }
    for group, metrics in groups.items():
        rows.append({"Grupo": group, "Jugador": _player_label(player_a, "A"), "Valor": _group_score(player_a, metrics)})
        rows.append({"Grupo": group, "Jugador": _player_label(player_b, "B"), "Valor": _group_score(player_b, metrics)})
    frame = pd.DataFrame(rows)
    if frame.empty:
        return _empty_figure("Perfil por grupos")
    figure = px.bar(
        frame,
        x="Grupo",
        y="Valor",
        color="Jugador",
        barmode="group",
        color_discrete_sequence=["#1f77b4", "#c43c5e"],
    )
    figure.update_layout(
        title="Perfil por grupos",
        template="plotly_white",
        height=430,
        yaxis_title="Score normalizado por grupo",
        legend_title_text="Jugador",
    )
    return figure


def plot_player_strengths_weaknesses(radar_metrics: dict[str, Any]) -> dict[str, Any]:
    categories = list(radar_metrics.get("categories", []))
    player_a = radar_metrics.get("player_a", {})
    player_b = radar_metrics.get("player_b", {})
    values_a = list(player_a.get("values", []))
    values_b = list(player_b.get("values", []))
    result = {
        "player_a_strengths": _categories_by_threshold(categories, values_a, minimum=70),
        "player_a_weaknesses": _categories_by_threshold(categories, values_a, maximum=30),
        "player_b_strengths": _categories_by_threshold(categories, values_b, minimum=70),
        "player_b_weaknesses": _categories_by_threshold(categories, values_b, maximum=30),
        "warnings": [],
    }
    if values_a and values_b and max(values_a + values_b) <= 35:
        result["warnings"].append("Ambos jugadores tienen valores bajos en el radar; puede haber poco dato comparable.")
    if not result["player_a_strengths"]:
        result["warnings"].append("Jugador A no tiene fortalezas >= 70 en esta comparación.")
    if not result["player_b_strengths"]:
        result["warnings"].append("Jugador B no tiene fortalezas >= 70 en esta comparación.")
    return result


def _categories_by_threshold(
    categories: list[str],
    values: list[Any],
    minimum: float | None = None,
    maximum: float | None = None,
) -> list[str]:
    selected = []
    for category, value in zip(categories, values):
        number = _number(value)
        if minimum is not None and number >= minimum:
            selected.append(category)
        elif maximum is not None and number <= maximum:
            selected.append(category)
    return selected


def _group_score(player: dict[str, Any], metrics: list[str]) -> float:
    total = sum(_number(player.get(metric)) for metric in metrics)
    return round(total, 3)


def _player_label(player: dict[str, Any], fallback: str) -> str:
    name = player.get("player_name")
    if not name:
        return f"Jugador {fallback}"
    return str(name)


def _number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _empty_figure(title: str) -> go.Figure:
    figure = go.Figure()
    figure.update_layout(title=title, xaxis={"visible": False}, yaxis={"visible": False})
    return figure
