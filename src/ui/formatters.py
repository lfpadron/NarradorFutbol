"""Small display formatters for Streamlit views."""

from __future__ import annotations

from typing import Any


def safe_display(value: Any, default: str = "-") -> Any:
    if value is None:
        return default
    if value == "":
        return default
    return value


def format_float(value: Any, decimals: int = 2) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "-"


def format_pct(value: Any) -> str:
    if value is None:
        return "-"
    try:
        return f"{float(value):.2f}%"
    except (TypeError, ValueError):
        return "-"


def format_score(home_team: Any, home_score: Any, away_score: Any, away_team: Any) -> str:
    return (
        f"{safe_display(home_team)} "
        f"{safe_display(home_score)}-{safe_display(away_score)} "
        f"{safe_display(away_team)}"
    )
