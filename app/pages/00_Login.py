from __future__ import annotations

# ruff: noqa: E402

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.security.streamlit_auth import render_login_page
from src.ui.footer import render_footer
from src.ui.navigation import ensure_page_shell

ensure_page_shell("Iniciar sesión")
render_login_page()
render_footer()
