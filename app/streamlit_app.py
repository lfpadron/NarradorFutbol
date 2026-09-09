from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.i18n import current_language, install_streamlit_i18n, render_language_selector, t
from src.ui.navigation import NAVIGATION_SHELL_SESSION_KEY, build_streamlit_pages, render_sidebar_navigation
from src.ui.page_config import soccer_page_icon

language = current_language()
st.set_page_config(
    page_title=str(t("Narrador Inteligente de Futbol", language=language)),
    page_icon=soccer_page_icon(),
    layout="wide",
)
pages = build_streamlit_pages(language)
page = st.navigation(pages, position="hidden")
st.session_state[NAVIGATION_SHELL_SESSION_KEY] = True
render_language_selector()
render_sidebar_navigation(language, pages)
install_streamlit_i18n()
page.run()
