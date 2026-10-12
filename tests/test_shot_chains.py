from __future__ import annotations

from copy import deepcopy
from io import BytesIO

from PIL import Image
import pytest
from streamlit.testing.v1 import AppTest

from src.analytics.shot_chains import build_shot_chains, shot_chain_title
from src.reports.shot_chain_export import shot_chain_pdf, shot_chain_video
from src.ui import shot_chain_panel
from src.ui.shot_chain_charts import (
    animation_state,
    build_animation_timeline,
    oriented_point,
    render_shot_chain_png,
)


def event(index, kind, player, x=60, y=40, **kwargs):
    return {
        "event_id": str(index),
        "event_index": index,
        "period": 1,
        "minute": index // 2,
        "second": 0,
        "possession": 1,
        "type_name": kind,
        "team_name": "Home",
        "player_id": player,
        "player_name": f"Player {player}",
        "location_x": x,
        "location_y": y,
        **kwargs,
    }


@pytest.fixture
def buildup():
    rows = []
    for player in range(1, 5):
        index = (player - 1) * 3 + 1
        x = player * 15
        rows.extend(
            [
                event(index, "Ball Receipt*", player, x),
                event(index + 1, "Carry", player, x, carry_end_x=x + 8, carry_end_y=40),
                event(
                    index + 2,
                    "Pass",
                    player,
                    x + 8,
                    recipient_player_id=player + 1,
                    recipient_player_name=f"Player {player+1}",
                    pass_end_x=x + 15,
                    pass_end_y=40,
                ),
            ]
        )
    rows.extend(
        [
            event(13, "Ball Receipt*", 5, 75),
            event(14, "Carry", 5, 75, carry_end_x=108, carry_end_y=39),
            event(
                15,
                "Shot",
                5,
                108,
                39,
                shot_outcome_name="Goal",
                shot_type_name="Open Play",
                shot_end_x=120,
                shot_end_y=40,
            ),
        ]
    )
    return rows


def test_last_three_passes_keep_receptions_carries_and_shooter(buildup):
    chain = build_shot_chains(buildup, "Home", "Away")[0]
    assert [stage["player_id"] for stage in chain["stages"]] == ["2", "3", "4", "5"]
    assert [stage["event_id"] for stage in chain["stages"]] == ["6", "9", "12", "15"]
    assert chain["stages"][0]["movement"] == [[30.0, 40.0], [38.0, 40.0]]
    assert chain["stages"][-1]["movement"] == [[75.0, 40.0], [108.0, 39.0]]
    assert chain["stages"][-1]["is_shot"]


@pytest.mark.parametrize("shot_type", ["Penalty", "Free Kick"])
def test_direct_set_piece_does_not_borrow_previous_passes(buildup, shot_type):
    buildup[-1]["shot_type_name"] = shot_type
    chain = build_shot_chains(buildup, "Home", "Away")[0]
    assert len(chain["stages"]) == 1
    assert chain["stages"][0]["movement"] == [[108.0, 39.0]]


@pytest.mark.parametrize(
    "kind,extra",
    [
        ("Foul Won", {}),
        ("Foul Committed", {}),
        ("Offside", {}),
        ("Interception", {"team_name": "Away"}),
        ("Pass", {"pass_outcome_name": "Incomplete"}),
        ("Dispossessed", {}),
        ("Miscontrol", {}),
        ("Ball Recovery", {"out": True}),
        ("Shot", {"shot_outcome_name": "Saved"}),
    ],
)
def test_dead_balls_turnovers_and_rebounds_break_chain(buildup, kind, extra):
    # Boundary immediately before the final passer receives the ball.
    buildup.append(event(9.5, kind, 7, **extra))
    chain = build_shot_chains(buildup, "Home", "Away")[-1]
    assert [stage["event_id"] for stage in chain["stages"]] == ["12", "15"]


@pytest.mark.parametrize("restart", ["Corner", "Free Kick", "Throw-in", "Goal Kick", "Kick Off"])
def test_restart_pass_begins_a_new_chain(buildup, restart):
    buildup[11]["pass_type_name"] = restart
    chain = build_shot_chains(buildup, "Home", "Away")[0]
    assert [stage["event_id"] for stage in chain["stages"]] == ["12", "15"]
    assert chain["stages"][0]["movement"] == [[68.0, 40.0]]


@pytest.mark.parametrize("field", ["possession", "period"])
def test_chain_never_crosses_possession_or_period(buildup, field):
    for row in buildup[9:]:
        row[field] = 2
    chain = build_shot_chains(buildup, "Home", "Away")[0]
    assert [stage["event_id"] for stage in chain["stages"]] == ["12", "15"]


def test_pressure_and_advantage_do_not_break_connected_passes(buildup):
    buildup.append(event(9.5, "Pressure", 8, team_name="Away"))
    buildup.append(event(10.5, "Foul Won", 4, raw_event_json={"foul_won": {"advantage": True}}))
    chain = build_shot_chains(buildup, "Home", "Away")[0]
    assert len(chain["stages"]) == 4


def test_disconnected_or_missing_coordinates_do_not_invent_passes(buildup):
    buildup[11]["recipient_player_id"] = 99
    assert len(build_shot_chains(buildup, "Home", "Away")[0]["stages"]) == 1
    buildup[11]["recipient_player_id"] = 5
    buildup[11]["pass_end_x"] = None
    assert len(build_shot_chains(buildup, "Home", "Away")[0]["stages"]) == 1
    buildup[-1]["location_x"] = float("nan")
    assert build_shot_chains(buildup, "Home", "Away") == []


def test_shots_are_chronological_including_stoppage_time(buildup):
    second = event(1, "Shot", 1, 110, period=2, possession=2, minute=45, second=20)
    buildup[-1].update(minute=47, second=15)
    chains = build_shot_chains([second, *reversed(buildup)], "Home", "Away")
    assert chains[0]["period"] == 1
    assert shot_chain_title(chains[0]).startswith("45+2:15 – Home – *GOL*")
    assert "Shot" in shot_chain_title(chains[1], "en")


@pytest.mark.parametrize("team", ["Home", "Away"])
def test_animation_receives_moves_passes_then_finishes_inside_goal(buildup, team):
    for row in buildup:
        row["team_name"] = team
    chain = build_shot_chains(buildup, "Home", "Away")[0]
    timeline = build_animation_timeline(chain)
    state = animation_state(chain, timeline, 0)
    assert list(state["players"]) == ["2"]
    assert state["ball"] == chain["stages"][0]["movement"][0]
    for phase in timeline:
        if phase["kind"] == "pass":
            before = animation_state(chain, timeline, phase["start"] + phase["duration"] - 1e-7)
            after = animation_state(chain, timeline, phase["start"] + phase["duration"])
            assert before["ball"] == pytest.approx(after["ball"])
    final = animation_state(chain, timeline, 100)
    assert final["goal"]
    x, y = oriented_point(final["ball"], chain["is_home"])
    assert (120 < x < 124) if team == "Home" else (-4 < x < 0)
    assert 36 < y < 44
    assert final["ball"] == animation_state(chain, timeline, 101)["ball"]


@pytest.mark.parametrize("outcome", ["Saved", "Blocked", "Off T", "Wayward"])
def test_non_goal_animation_passes_the_goal_without_staying_in_net(buildup, outcome):
    buildup[-1]["shot_outcome_name"] = outcome
    chain = build_shot_chains(buildup, "Home", "Away")[0]
    state = animation_state(chain, build_animation_timeline(chain), 100)
    assert not state["goal"]
    assert state["ball"][0] > 124
    assert not 36 < state["ball"][1] < 44


def test_png_and_pdf_exports_are_nonempty(buildup):
    chain = build_shot_chains(buildup, "Home", "Away")[0]
    png = render_shot_chain_png(chain)
    with Image.open(BytesIO(png)) as image:
        assert image.width > image.height
    assert shot_chain_pdf(chain, png).startswith(b"%PDF")


def test_video_reports_missing_encoder(monkeypatch, buildup):
    monkeypatch.setattr("src.reports.shot_chain_export.shutil.which", lambda name: None)
    chain = build_shot_chains(buildup, "Home", "Away")[0]
    with pytest.raises(RuntimeError, match="FFmpeg"):
        shot_chain_video(chain)


def _panel_app():
    import streamlit as st
    from src.ui.i18n import install_streamlit_i18n
    from src.ui.shot_chain_panel import render_shot_chain_panel

    install_streamlit_i18n()
    animated = st.toggle("Animated")
    render_shot_chain_panel(1, "Home", "Away", animated=animated)


@pytest.mark.parametrize("language", ["es", "en"])
def test_panel_selection_is_preserved_when_switching_to_animation(monkeypatch, buildup, language):
    from src.ui.i18n import LANGUAGE_SESSION_KEY

    chains = build_shot_chains(buildup, "Home", "Away")
    other = deepcopy(chains[0])
    other.update(shot_id="second-shot", is_goal=False, minute=20)
    chains.append(other)
    monkeypatch.setattr(shot_chain_panel, "_load_chains", lambda *args: chains)
    image_data = BytesIO()
    Image.new("RGB", (20, 10), "green").save(image_data, format="PNG")
    monkeypatch.setattr(shot_chain_panel, "_chart_png", lambda *args: image_data.getvalue())
    monkeypatch.setattr(shot_chain_panel, "shot_chain_pdf", lambda *args: b"%PDF")
    videos = []
    monkeypatch.setattr(shot_chain_panel, "_video", lambda chain, lang: videos.append(chain["shot_id"]) or b"video")
    app = AppTest.from_function(_panel_app)
    app.session_state[LANGUAGE_SESSION_KEY] = language
    app.run()
    assert not app.exception
    assert len(app.selectbox[0].options) == 2
    assert "minuto" in app.selectbox[0].label if language == "es" else "minute" in app.selectbox[0].label
    assert not videos
    app.selectbox[0].set_value("second-shot").run()
    app.toggle[0].set_value(True).run()
    assert not app.exception
    assert app.selectbox[0].value == "second-shot"
    assert videos == ["second-shot"]
