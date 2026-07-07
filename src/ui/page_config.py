"""Shared Streamlit page configuration helpers."""

from __future__ import annotations

from functools import lru_cache
from typing import Any

from src.config import PROJECT_ROOT

SOCCER_ICON_PATH = PROJECT_ROOT / "app" / "assets" / "futbol_balon.png"


@lru_cache(maxsize=1)
def soccer_page_icon() -> Any:
    if not SOCCER_ICON_PATH.exists():
        return "⚽"
    try:
        from PIL import Image

        with Image.open(SOCCER_ICON_PATH) as image:
            return image.copy()
    except Exception:
        return "⚽"
