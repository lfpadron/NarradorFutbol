from __future__ import annotations

# Streamlit executes page scripts outside the installed package.
# ruff: noqa: E402

import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.ui.analysis_page import render_analysis_page

render_analysis_page("Análisis de jugadores")
