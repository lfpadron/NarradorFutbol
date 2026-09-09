"""Shared Streamlit navigation shell helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from src.ui.i18n import DEFAULT_LANGUAGE, current_language, install_streamlit_i18n, render_language_selector, t
from src.ui.page_config import soccer_page_icon

NAVIGATION_SHELL_SESSION_KEY = "_narrador_navigation_shell"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PROJECT_ROOT / "app"

PAGE_DEFINITIONS = [
    {
        "path": "pages/00_Inicio.py",
        "fallback_path": APP_ROOT / "pages" / "00_Inicio.py",
        "label": "Inicio",
        "icon": ":material/home:",
        "default": True,
        "url_path": "Inicio",
    },
    {
        "path": "pages/00_Login.py",
        "fallback_path": APP_ROOT / "pages" / "00_Login.py",
        "label": "Iniciar sesión",
        "icon": ":material/login:",
        "default": False,
        "url_path": "Login",
    },
    {
        "path": "pages/01_Ingesta.py",
        "fallback_path": APP_ROOT / "pages" / "01_Ingesta.py",
        "label": "Ingesta",
        "icon": ":material/cloud_download:",
        "default": False,
        "url_path": "Ingesta",
    },
    {
        "path": "pages/02_Partidos.py",
        "fallback_path": APP_ROOT / "pages" / "02_Partidos.py",
        "label": "Partidos",
        "icon": ":material/sports_soccer:",
        "default": False,
        "url_path": "Partidos",
    },
    {
        "path": "pages/03_Analisis.py",
        "fallback_path": APP_ROOT / "pages" / "03_Analisis.py",
        "label": "Análisis",
        "icon": ":material/analytics:",
        "default": False,
        "url_path": "Analisis",
    },
    {
        "path": "pages/04_Graficas_Avanzadas.py",
        "fallback_path": APP_ROOT / "pages" / "04_Graficas_Avanzadas.py",
        "label": "Gráficas avanzadas",
        "icon": ":material/monitoring:",
        "default": False,
        "url_path": "Graficas_Avanzadas",
    },
]


def build_streamlit_pages(language: str) -> list[Any]:
    import streamlit as st

    pages = []
    for definition in PAGE_DEFINITIONS:
        page_kwargs = {
            "title": str(t(definition["label"], language=language)),
            "icon": definition["icon"],
            "default": definition["default"],
        }
        if definition["url_path"]:
            page_kwargs["url_path"] = definition["url_path"]
        pages.append(st.Page(definition["path"], **page_kwargs))
    return pages


def render_sidebar_navigation(language: str, pages: list[Any] | None = None) -> None:
    import streamlit as st

    query_params = {"lang": language} if language != DEFAULT_LANGUAGE else None
    with st.sidebar:
        for index, definition in enumerate(PAGE_DEFINITIONS):
            label = str(t(definition["label"], language=language))
            target = pages[index] if pages else definition["fallback_path"]
            if st.button(
                label,
                key=f"sidebar_nav_{definition['label']}_{language}",
                icon=str(definition["icon"]),
                type="tertiary",
                use_container_width=True,
            ):
                st.switch_page(target, query_params=query_params)
        st.divider()


def ensure_page_shell(page_title: str, layout: str = "wide") -> None:
    import streamlit as st

    if st.session_state.get(NAVIGATION_SHELL_SESSION_KEY):
        return

    language = current_language()
    st.set_page_config(
        page_title=str(t(page_title, language=language)),
        page_icon=soccer_page_icon(),
        layout=layout,
    )
    render_language_selector()
    render_sidebar_navigation(language)
    install_streamlit_i18n()
