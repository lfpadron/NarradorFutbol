"""Shared footer for Streamlit pages."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st

FOOTER_TEXT = "Construido por Luis Fernando Padrón"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGO_PATH = PROJECT_ROOT / "app" / "assets" / "astrogato_footer_logo.png"


@lru_cache(maxsize=1)
def _logo_data_uri() -> str:
    if not LOGO_PATH.exists():
        return ""
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_footer() -> None:
    logo_uri = _logo_data_uri()
    logo = (
        f'<img src="{logo_uri}" alt="Astrogato Labs" class="astrogato-footer__logo" />'
        if logo_uri
        else '<span class="astrogato-footer__logo-placeholder"></span>'
    )
    st.markdown(
        f"""
        <style>
            .astrogato-footer {{
                display: grid;
                grid-template-columns: 72px 1fr 72px;
                align-items: center;
                gap: 16px;
                margin-top: 48px;
                padding: 16px 0 8px;
                border-top: 1px solid rgba(148, 163, 184, 0.35);
                color: #475569;
            }}
            .astrogato-footer__brand {{
                display: flex;
                justify-content: flex-start;
                align-items: center;
            }}
            .astrogato-footer__logo,
            .astrogato-footer__logo-placeholder {{
                width: 56px;
                height: 56px;
                border-radius: 50%;
                object-fit: cover;
                display: block;
            }}
            .astrogato-footer__text {{
                text-align: center;
                font-size: 0.95rem;
                font-weight: 650;
                line-height: 1.35;
            }}
            @media (max-width: 640px) {{
                .astrogato-footer {{
                    grid-template-columns: 48px 1fr 48px;
                    gap: 10px;
                    margin-top: 36px;
                }}
                .astrogato-footer__logo,
                .astrogato-footer__logo-placeholder {{
                    width: 42px;
                    height: 42px;
                }}
                .astrogato-footer__text {{
                    font-size: 0.85rem;
                }}
            }}
        </style>
        <footer class="astrogato-footer">
            <div class="astrogato-footer__brand">{logo}</div>
            <div class="astrogato-footer__text">{FOOTER_TEXT}</div>
            <div aria-hidden="true"></div>
        </footer>
        """,
        unsafe_allow_html=True,
    )
