from __future__ import annotations

from unittest.mock import Mock

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest

from src.ui.match_selector import MATCH_SELECTION_KEY

SELECTOR_APP = """
import streamlit as st
from src.ui.i18n import install_streamlit_i18n
from src.ui.match_selector import render_match_selector
install_streamlit_i18n()
st.radio("Language", ["es", "en"], key="narrador_language")
if st.checkbox("Show selectors", value=True):
    options = {"7534 | First match": 7534, "9001 | Second match": 9001}
    if st.checkbox("Remove second match"):
        options.pop("9001 | Second match")
    render_match_selector("Partido", options, key="main_match")
    for slot in ("comparison_a", "comparison_b", "player_a", "player_b", "scouting_a", "scouting_b"):
        with st.container():
            render_match_selector("Partido", options, key=slot)
"""


def test_new_sessions_start_empty_and_do_not_share_match_selection():
    app = AppTest.from_string(SELECTOR_APP).run()
    assert not app.exception
    assert all(selector.value is None for selector in app.selectbox)
    app.selectbox(key="main_match").set_value(9001).run()
    assert not app.exception
    assert all(selector.value == 9001 for selector in app.selectbox)
    other = AppTest.from_string(SELECTOR_APP).run()
    assert all(selector.value is None for selector in other.selectbox)


@pytest.mark.parametrize("slot", ["comparison_a", "comparison_b", "player_b", "scouting_b"])
def test_selection_and_clear_from_sections_update_every_dropdown(slot):
    app = AppTest.from_string(SELECTOR_APP).run()
    app.selectbox(key=slot).set_value(9001).run()
    assert not app.exception
    assert all(selector.value == 9001 for selector in app.selectbox)
    app.selectbox(key="main_match").set_value(7534).run()
    assert all(selector.value == 7534 for selector in app.selectbox)
    app.button(key=f"{slot}_clear").click().run()
    assert not app.exception
    assert all(selector.value is None for selector in app.selectbox)
    assert app.session_state[MATCH_SELECTION_KEY] is None


def test_match_survives_hidden_widgets_and_language_change():
    app = AppTest.from_string(SELECTOR_APP).run()
    app.selectbox(key="player_b").set_value(9001).run()
    app.checkbox[0].set_value(False).run()
    assert not app.selectbox
    assert app.session_state[MATCH_SELECTION_KEY] == 9001
    app.radio[0].set_value("en").run()
    app.checkbox[0].set_value(True).run()
    assert not app.exception
    assert all(selector.value == 9001 and selector.label == "Match" for selector in app.selectbox)
    assert all(button.label == "Clear" for button in app.button)


def test_removed_match_resets_without_selecting_the_first_option():
    app = AppTest.from_string(SELECTOR_APP).run()
    app.selectbox(key="main_match").set_value(9001).run()
    app.checkbox[1].set_value(True).run()
    assert not app.exception
    assert all(selector.value is None for selector in app.selectbox)
    assert app.session_state[MATCH_SELECTION_KEY] is None


@pytest.fixture
def match_pages(tmp_path, monkeypatch):
    from src.analytics import advanced_charts, ai_context, db, match_summary
    from src.security import storage
    from src.security.models import ROLE_GUEST

    st.cache_data.clear()
    monkeypatch.setattr(storage, "SECURITY_DB_PATH", tmp_path / "accounts.sqlite")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "")
    storage.initialize_security()
    user = storage.provision_verified_guest("matches@example.com")
    assert user["role"] == ROLE_GUEST
    matches = pd.DataFrame(
        [
            {
                "match_id": match_id,
                "match_date": "2026-01-01",
                "competition_name": competition,
                "season_name": "2026",
                "home_team_name": "Home",
                "away_team_name": "Away",
                "home_score": 1,
                "away_score": 0,
                "total_events": 20,
                "total_shots": 2,
                "total_goals": 1,
                "total_xg": 0.5,
                "total_passes": 12,
            }
            for match_id, competition in [(7534, "Cup A"), (9001, "Cup B")]
        ]
    )
    monkeypatch.setattr(db, "query_df", Mock(return_value=matches))
    # Stop before chart/report rendering while recording which match the page loads.
    detail = Mock(side_effect=db.AnalyticsDatabaseError("Test detail boundary"))
    context = Mock(side_effect=AssertionError("Context must not load without selection"))
    charts = Mock(side_effect=db.AnalyticsDatabaseError("Test chart boundary"))
    teams = Mock(return_value=[])
    players = Mock(return_value=[])
    monkeypatch.setattr(match_summary, "get_match_summary", detail)
    monkeypatch.setattr(ai_context, "build_ai_match_context", context)
    monkeypatch.setattr(advanced_charts, "build_advanced_chart_bundle", charts)
    monkeypatch.setattr(advanced_charts, "get_match_teams", teams)
    monkeypatch.setattr(advanced_charts, "get_players_for_heatmap", players)
    from src.ui import advanced_page, analysis_page, play_analysis_page

    monkeypatch.setattr(analysis_page, "query_df", db.query_df)
    monkeypatch.setattr(analysis_page, "get_match_summary", detail)
    monkeypatch.setattr(analysis_page, "build_ai_match_context", context)
    monkeypatch.setattr(advanced_page, "query_df", db.query_df)
    monkeypatch.setattr(advanced_page, "build_advanced_chart_bundle", charts)
    monkeypatch.setattr(advanced_page, "get_match_teams", teams)
    monkeypatch.setattr(advanced_page, "get_players_for_heatmap", players)
    monkeypatch.setattr(play_analysis_page, "render_shot_chain_panel", Mock())
    app = AppTest.from_file("app/streamlit_app.py", default_timeout=30)
    app.session_state["auth_user"] = user
    app.run()
    yield app, detail, context, charts, teams, players
    st.cache_data.clear()


def test_real_pages_remain_empty_and_skip_match_work_until_selected(match_pages):
    app, detail, context, charts, teams, players = match_pages
    for page, key in [
        ("02_Partidos.py", "matches_match"),
        ("03_Analisis.py", "analysis_match"),
        ("04_Graficas_Avanzadas.py", "charts_match"),
        ("07_Analisis_Jugadas.py", "plays_match"),
        ("08_Analisis_Jugadores.py", "analysis_match"),
        ("09_Narrador_AI.py", "analysis_match"),
        ("10_Narrador_AI_2.py", "analysis_match"),
    ]:
        app.switch_page(f"pages/{page}").run()
        assert not app.exception
        assert app.selectbox(key=key).value is None
    for loader in (detail, context, charts, teams, players):
        loader.assert_not_called()


def test_real_navigation_retains_selection_and_clear_stops_loading(match_pages):
    app, detail, context, charts, teams, players = match_pages
    app.switch_page("pages/02_Partidos.py").run()
    app.selectbox(key="matches_match").set_value(9001).run()
    app.switch_page("pages/03_Analisis.py").run()
    assert not app.exception
    assert app.selectbox(key="analysis_match").value == 9001
    detail.assert_called_once_with(9001)
    app.switch_page("pages/04_Graficas_Avanzadas.py").run()
    assert not app.exception
    assert app.selectbox(key="charts_match").value == 9001
    charts.assert_called_once_with(9001, team_name=None, player_id=None)
    app.selectbox(key="charts_match").set_value(7534).run()
    app.switch_page("pages/05_Mi_Usuario.py").run()
    app.switch_page("pages/02_Partidos.py").run()
    assert app.selectbox(key="matches_match").value == 7534
    app.button(key="matches_match_clear").click().run()
    for loader in (detail, context, charts, teams, players):
        loader.reset_mock()
    for page, key in [("03_Analisis.py", "analysis_match"), ("04_Graficas_Avanzadas.py", "charts_match")]:
        app.switch_page(f"pages/{page}").run()
        assert not app.exception
        assert app.selectbox(key=key).value is None
    for loader in (detail, context, charts, teams, players):
        loader.assert_not_called()


def test_filters_do_not_silently_replace_the_shared_match(match_pages):
    app, *_ = match_pages
    app.switch_page("pages/02_Partidos.py").run()
    app.selectbox(key="matches_match").set_value(9001).run()
    next(selector for selector in app.selectbox if selector.label == "Competencia").set_value("Cup A").run()
    assert not app.exception
    assert app.selectbox(key="matches_match").value == 9001
    assert app.session_state[MATCH_SELECTION_KEY] == 9001
    assert list(app.dataframe[0].value["match_id"]) == [7534]
    app.button(key="matches_match_clear").click().run()
    assert not app.exception
    assert app.selectbox(key="matches_match").value is None
    assert len(app.selectbox(key="matches_match").options) == 1
