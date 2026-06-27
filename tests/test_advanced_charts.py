from __future__ import annotations

from src.analytics.advanced_charts import build_presence_zones
from src.analytics.pitch import is_valid_pitch_point, pitch_bin, zone_label


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
