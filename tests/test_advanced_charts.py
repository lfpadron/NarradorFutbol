from __future__ import annotations

from src.analytics.advanced_charts import build_presence_zones, plot_broadcast_momentum, plot_event_heatmap
from src.analytics.pitch import is_valid_pitch_point, pitch_bin, zone_label
from src.ui.charts import xg_bar


def test_pitch_point_validation() -> None:
    assert is_valid_pitch_point(0, 0)
    assert is_valid_pitch_point(120, 80)
    assert not is_valid_pitch_point(-1, 40)
    assert not is_valid_pitch_point(60, 81)
    assert not is_valid_pitch_point(None, 20)


def test_pitch_bin_boundaries() -> None:
    assert pitch_bin(0, 0) == (0, 0)
    assert pitch_bin(119.9, 79.9) == (5, 3)
    assert pitch_bin(120, 80) == (5, 3)
    assert pitch_bin(200, 40) is None


def test_zone_label() -> None:
    assert zone_label(0, 0) == "defensiva | izquierda"
    assert zone_label(2, 1) == "media | centro-izquierda"
    assert zone_label(5, 3) == "ofensiva | derecha"


def test_build_presence_zones_groups_by_team_and_zone() -> None:
    events = [
        {"team_name": "Mexico", "location_x": 10, "location_y": 10},
        {"team_name": "Mexico", "location_x": 15, "location_y": 12},
        {"team_name": "Mexico", "location_x": 100, "location_y": 70},
        {"team_name": "Germany", "location_x": 100, "location_y": 70},
        {"team_name": "Germany", "location_x": None, "location_y": 70},
    ]

    zones = build_presence_zones(events)

    mexico_defensive = next(
        row for row in zones if row["team_name"] == "Mexico" and row["zone"] == "defensiva | izquierda"
    )
    mexico_offensive = next(
        row for row in zones if row["team_name"] == "Mexico" and row["zone"] == "ofensiva | derecha"
    )
    germany_offensive = next(row for row in zones if row["team_name"] == "Germany")

    assert mexico_defensive["events"] == 2
    assert mexico_defensive["share_pct"] == 66.67
    assert mexico_offensive["events"] == 1
    assert germany_offensive["events"] == 1
    assert germany_offensive["share_pct"] == 100.0


def test_event_heatmap_layers_home_and_away_colors() -> None:
    events = [
        {"team_name": "Germany", "location_x": 10, "location_y": 20},
        {"team_name": "Mexico", "location_x": 70, "location_y": 30},
    ]

    figure = plot_event_heatmap(events, home_team_name="Germany", away_team_name="Mexico")

    assert len(figure.data) == 2
    assert figure.data[0].name == "Local (Germany)"
    assert figure.data[1].name == "Visitante (Mexico)"
    assert "rgba(214,39,40" in figure.data[0].colorscale[-1][1]
    assert "rgba(31,119,180" in figure.data[1].colorscale[-1][1]


def test_broadcast_momentum_adds_goal_marker_and_shot_counts() -> None:
    momentum = [
        {"interval_start": 0, "interval_end": 5, "team_name": "Germany", "momentum_score": 4},
        {"interval_start": 0, "interval_end": 5, "team_name": "Mexico", "momentum_score": 1},
        {"interval_start": 5, "interval_end": 10, "team_name": "Germany", "momentum_score": 0},
        {"interval_start": 5, "interval_end": 10, "team_name": "Mexico", "momentum_score": 3},
    ]
    shots = [
        {
            "minute": 5,
            "second": 30,
            "team_name": "Mexico",
            "player_name": "Hirving Lozano",
            "shot_outcome_name": "Goal",
        },
        {
            "minute": 7,
            "second": 0,
            "team_name": "Germany",
            "player_name": "Toni Kroos",
            "shot_outcome_name": "Saved",
        },
    ]

    figure = plot_broadcast_momentum(momentum, "Germany", "Mexico", shots=shots)
    traces_by_name = {trace.name: trace for trace in figure.data}

    assert list(traces_by_name["Tiros a gol local"].text) == ["0", "1"]
    assert list(traces_by_name["Tiros a gol visitante"].text) == ["0", "1"]
    goal_trace = next(trace for trace in figure.data if trace.mode == "markers+text")
    assert list(goal_trace.text) == ["H. Lozano"]
    assert goal_trace.marker.symbol == "star"


def test_xg_bar_has_xg_title() -> None:
    figure = xg_bar([{"team_name": "Germany", "xg": 1.4}, {"team_name": "Mexico", "xg": 0.8}])

    assert figure.layout.title.text == "xG"
