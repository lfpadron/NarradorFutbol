"""Shared Streamlit navigation shell helpers."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Literal

from src.security.models import can_access_page
from src.ui.i18n import DEFAULT_LANGUAGE, current_language, install_streamlit_i18n, render_language_selector, t
from src.ui.page_config import soccer_page_icon

NAVIGATION_SHELL_SESSION_KEY = "_narrador_navigation_shell"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
APP_ROOT = PROJECT_ROOT / "app"

PAGE_DEFINITIONS = [
    {
        "path": "pages/00_Login.py",
        "fallback_path": APP_ROOT / "pages" / "00_Login.py",
        "label": "Iniciar sesión",
        "icon": ":material/login:",
        "default": True,
        "url_path": "Login",
    },
    {
        "path": "pages/05_Mi_Usuario.py",
        "fallback_path": APP_ROOT / "pages" / "05_Mi_Usuario.py",
        "label": "Mi usuario",
        "icon": ":material/account_circle:",
        "default": False,
        "url_path": "Mi_Usuario",
    },
    {
        "path": "pages/06_Usuarios.py",
        "fallback_path": APP_ROOT / "pages" / "06_Usuarios.py",
        "label": "Usuarios",
        "icon": ":material/group:",
        "default": False,
        "url_path": "Usuarios",
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


def visible_page_definitions(user: dict | None = None) -> list[dict[str, Any]]:
    return [
        definition
        for definition in PAGE_DEFINITIONS
        if definition["label"] == "Iniciar sesión"
        or (user and user.get("is_active") and can_access_page(user["role"], str(definition["label"])))
    ]


def build_streamlit_pages(language: str, user: dict | None = None) -> list[Any]:
    import streamlit as st

    pages = []
    for definition in visible_page_definitions(user):
        page_kwargs = {
            "title": str(t(definition["label"], language=language)),
            "icon": definition["icon"],
            "default": definition["default"],
        }
        if definition["url_path"]:
            page_kwargs["url_path"] = definition["url_path"]
        pages.append(st.Page(definition["path"], **page_kwargs))
    return pages


def render_sidebar_navigation(language: str, pages: list[Any] | None = None, user: dict | None = None) -> None:
    import streamlit as st

    query_params = {"lang": language} if language != DEFAULT_LANGUAGE else None
    with st.sidebar:
        st.markdown("**Narrador de Fútbol**")
        st.caption("Astrogato Labs")
        for index, definition in enumerate(visible_page_definitions(user)):
            if user and definition["label"] == "Iniciar sesión":
                continue
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


def ensure_page_shell(page_title: str, layout: Literal["wide", "centered"] = "wide") -> None:
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
    from src.security.storage import initialize_security
    from src.security.streamlit_auth import current_user

    initialize_security()
    render_sidebar_navigation(language, user=current_user())
    install_streamlit_i18n()
