from __future__ import annotations

import streamlit as st

from src.security.streamlit_auth import render_login_page

st.set_page_config(page_title="Login", layout="centered")
st.title("Login")
render_login_page()
