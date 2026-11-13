from __future__ import annotations

from unittest.mock import Mock

import pandas as pd
import pytest
import streamlit as st
from streamlit.runtime.pages_manager import PagesManager
from streamlit.runtime.scriptrunner import get_script_run_ctx
from streamlit.testing.v1 import AppTest

from src.security import storage
from src.ui import advanced_page, analysis_page, i18n, play_analysis_page
from src.ui.i18n import t
from src.ui.match_selector import MATCH_SELECTION_KEY


@pytest.fixture
def navigation_app(tmp_path, monkeypatch):
    # AppTest resets the navigation mode on every run, unlike a real session.
    # Keep the entrypoint in charge of st.navigation rather than legacy pages/ routing.
    initialize_pages = PagesManager.__init__

    def initialize_navigation(*args, **kwargs):
        initialize_pages(*args, **kwargs)
        PagesManager.uses_pages_directory = False

    monkeypatch.setattr(PagesManager, "__init__", initialize_navigation)
    st.cache_data.clear()
    monkeypatch.setattr(storage, "SECURITY_DB_PATH", tmp_path / "security.sqlite")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "")
    storage.initialize_security()
    user = storage.provision_verified_guest("navigation@example.com")
    summary = {
        "match_id": 7534,
        "match_date": "2026-01-01",
        "home_team_name": "Home",
        "away_team_name": "Away",
        "home_score": 0,
        "away_score": 0,
    }
    matches = pd.DataFrame([summary])
    monkeypatch.setattr(analysis_page, "load_match_options", Mock(return_value=matches))
    monkeypatch.setattr(advanced_page, "load_matches", Mock(return_value=matches))
    monkeypatch.setattr(play_analysis_page, "load_matches", Mock(return_value=matches))
    detail = {
        "summary": summary,
        "team_stats": [],
        "shots": [],
        "shot_summary": {},
        "pass_summary": {},
        "progressive_passes": [],
        "pressures": [],
        "key_moments": [],
        "momentum": [],
    }
    monkeypatch.setattr(analysis_page, "load_detail", Mock(return_value=detail))
    monkeypatch.setattr(analysis_page, "load_context", Mock(return_value={"validation": {"status": "PASS"}}))
    monkeypatch.setattr(analysis_page, "load_players_for_match", Mock(return_value=[]))
    monkeypatch.setattr(analysis_page, "list_players_for_match", Mock(return_value=[]))
    monkeypatch.setattr(analysis_page, "list_report_history", Mock(return_value=[]))
    monkeypatch.setattr(analysis_page, "has_openai_api_key", Mock(return_value=False))
    monkeypatch.setattr(advanced_page, "load_bundle", Mock(return_value={}))
    monkeypatch.setattr(advanced_page, "get_match_teams", Mock(return_value=[]))
    monkeypatch.setattr(advanced_page, "get_players_for_heatmap", Mock(return_value=[]))
    monkeypatch.setattr(play_analysis_page, "render_shot_chain_panel", Mock())
    app = AppTest.from_file("app/streamlit_app.py", default_timeout=30)
    app.session_state["auth_user"] = user
    app.session_state["narrador_language"] = "es"
    # AppTest serializes translated selectbox labels outside the script thread.
    current_language = i18n.current_language
    monkeypatch.setattr(
        i18n,
        "current_language",
        lambda: (
            current_language() if get_script_run_ctx(suppress_warning=True) else app.session_state["narrador_language"]
        ),
    )
    yield app
    st.cache_data.clear()


@pytest.mark.parametrize("language", ["es", "en"])
def test_sidebar_sections_are_text_and_pages_are_clickable(navigation_app, language):
    app = navigation_app
    app.session_state["narrador_language"] = language
    app.run()
    assert not app.exception
    sections = ["Administración de usuarios", "Administración de datos", "Análisis de datos", "Narradores AI"]
    captions = [caption.value for caption in app.sidebar.caption]
    assert [caption for caption in captions if caption in {t(s, language) for s in sections}] == [
        t(section, language) for section in sections
    ]
    buttons = [button.label for button in app.sidebar.button]
    assert not set(buttons) & {t(section, language) for section in sections}
    links = [button.label for button in app.sidebar.button if str(button.key).startswith("sidebar_nav_")]
    assert links == [
        t(label, language)
        for label in (
            "Mi usuario",
            "Partidos",
            "Análisis de partidos",
            "Análisis avanzado",
            "Análisis de jugadas",
            "Análisis de jugadores",
            "Narrador AI",
            "Narrador AI 2",
        )
    ]


@pytest.mark.parametrize("language", ["es", "en"])
def test_pages_keep_their_panels_and_shared_match_when_navigating(navigation_app, language):
    app = navigation_app
    app.session_state["narrador_language"] = language
    app.session_state[MATCH_SELECTION_KEY] = 7534
    app.run()
    pages = [
        (
            "03_Analisis.py",
            "Análisis de partidos",
            "analysis_match",
            [
                "Resumen",
                "Tiros y xG",
                "Pases",
                "Presión",
                "Momentum",
                "Análisis avanzado",
                "Benchmark",
                "Comparador de partidos",
                "Momentos clave",
                "Datos",
                "xG visitante-local",
            ],
        ),
        (
            "04_Graficas_Avanzadas.py",
            "Análisis avanzado",
            "charts_match",
            ["Calor", "Tiros", "Pases", "Red de pases", "Recuperación/pérdidas", "Momentum", "Zonas", "Datos"],
        ),
        (
            "07_Analisis_Jugadas.py",
            "Análisis de jugadas",
            "plays_match",
            ["Pases para tiro a gol", "Animación de tiros"],
        ),
        (
            "08_Analisis_Jugadores.py",
            "Análisis de jugadores",
            "analysis_match",
            ["Comparador de jugadores", "Scouting AI v2"],
        ),
        ("09_Narrador_AI.py", "Narrador AI", "analysis_match", []),
        ("10_Narrador_AI_2.py", "Narrador AI 2", "analysis_match", []),
    ]
    for filename, title, selector_key, tabs in pages:
        app.button(key=f"sidebar_nav_{title}_{language}").click().run()
        assert not app.exception, title
        assert app.title[0].value == t(title, language)
        assert app.selectbox(key=selector_key).value == 7534
        assert app.session_state[MATCH_SELECTION_KEY] == 7534
        if tabs:
            container = app.get("tab_container")[0]
            assert [tab.label for tab in container.children.values()] == [t(tab, language) for tab in tabs]
        else:
            assert not app.tabs
            action = "Generar narración" if title == "Narrador AI" else "Generar narrativa v2"
            assert t(action, language) in [button.label for button in app.main.button]
        # Keep AppTest's next run on the destination selected through the real sidebar.
        app.switch_page(f"pages/{filename}")
    play_analysis_page.render_shot_chain_panel.assert_called_once_with(7534, "Home", "Away", animated=False)


@pytest.mark.parametrize("language", ["es", "en"])
def test_play_animation_keeps_lazy_rendering_and_language(navigation_app, language):
    app = navigation_app
    app.session_state["narrador_language"] = language
    app.session_state[MATCH_SELECTION_KEY] = 7534
    app.run()
    app.switch_page("pages/07_Analisis_Jugadas.py").run()
    play_analysis_page.render_shot_chain_panel.reset_mock()
    app.session_state["play_analysis_tabs"] = t("Animación de tiros", language)
    app.run()
    assert not app.exception
    play_analysis_page.render_shot_chain_panel.assert_called_once_with(7534, "Home", "Away", animated=True)


def test_language_change_keeps_current_page_and_match(navigation_app):
    app = navigation_app
    app.session_state[MATCH_SELECTION_KEY] = 7534
    app.run()
    app.switch_page("pages/08_Analisis_Jugadores.py").run()
    app.button(key="language_selector_en").click().run()
    assert not app.exception
    assert app.title[0].value == "Player analysis"
    assert [tab.label for tab in app.tabs] == ["Player comparison", "Scouting AI v2"]
    assert app.selectbox(key="analysis_match").value == 7534
