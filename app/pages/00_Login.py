from __future__ import annotations

import sys
from pathlib import Path

import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.security.streamlit_auth import render_login_page
from src.ui.footer import render_footer

st.set_page_config(page_title="Login", layout="centered")
st.title("Login")
render_login_page()
render_footer()
