"""Shared footer for Streamlit pages."""

from __future__ import annotations

import base64
from functools import lru_cache
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

FOOTER_TEXT = "UNA MISIÓN DE DEMOSTRACIÓN DE:"
FOOTER_URL = "https://astrogatolabs.com.mx/"
PROJECT_ROOT = Path(__file__).resolve().parents[2]
LOGO_PATH = PROJECT_ROOT / "app" / "assets" / "astrogato_labs_logo_footer.png"
BALL_ICON_PATH = PROJECT_ROOT / "app" / "assets" / "futbol_balon.png"


@lru_cache(maxsize=1)
def _logo_data_uri() -> str:
    if not LOGO_PATH.exists():
        return ""
    encoded = base64.b64encode(LOGO_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@lru_cache(maxsize=1)
def _ball_data_uri() -> str:
    if not BALL_ICON_PATH.exists():
        return ""
    encoded = base64.b64encode(BALL_ICON_PATH.read_bytes()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


def render_footer() -> None:
    _render_pointer_trail()
    logo_uri = _logo_data_uri()
    logo = (
        f'<a href="{FOOTER_URL}" target="_blank" rel="noopener noreferrer" class="astrogato-footer__link">'
        f'<img src="{logo_uri}" alt="Astrogato Labs" class="astrogato-footer__logo" />'
        "</a>"
        if logo_uri
        else '<span class="astrogato-footer__logo-placeholder"></span>'
    )
    st.markdown(
        f"""
        <style>
            .astrogato-footer {{
                display: grid;
                grid-template-columns: minmax(0, 1fr) auto minmax(0, 1fr);
                align-items: center;
                gap: 24px;
                margin-top: 48px;
                padding: 18px 0 8px;
                border-top: 1px solid rgba(148, 163, 184, 0.35);
                color: #475569;
            }}
            .astrogato-footer__text {{
                display: flex;
                justify-content: flex-start;
                align-items: center;
                text-align: left;
                font-size: 0.78rem;
                font-weight: 750;
                letter-spacing: 0.08em;
                line-height: 1.35;
            }}
            .astrogato-footer__brand {{
                display: flex;
                justify-content: center;
                align-items: center;
            }}
            .astrogato-footer__link {{
                display: inline-flex;
                align-items: center;
                justify-content: center;
                text-decoration: none;
            }}
            .astrogato-footer__logo,
            .astrogato-footer__logo-placeholder {{
                width: min(320px, 44vw);
                max-height: 68px;
                object-fit: contain;
                display: block;
            }}
            @media (max-width: 640px) {{
                .astrogato-footer {{
                    grid-template-columns: 1fr;
                    justify-items: center;
                    gap: 12px;
                    margin-top: 36px;
                }}
                .astrogato-footer__text {{
                    text-align: center;
                    justify-content: center;
                    font-size: 0.7rem;
                }}
                .astrogato-footer__logo,
                .astrogato-footer__logo-placeholder {{
                    width: min(280px, 82vw);
                    max-height: 58px;
                }}
            }}
        </style>
        <footer class="astrogato-footer">
            <div class="astrogato-footer__text">{FOOTER_TEXT}</div>
            <div class="astrogato-footer__brand">{logo}</div>
            <div aria-hidden="true"></div>
        </footer>
        """,
        unsafe_allow_html=True,
    )


def _render_pointer_trail() -> None:
    ball_uri = _ball_data_uri()
    if not ball_uri:
        return

    components.html(
        f"""
        <script>
        (() => {{
            const doc = window.parent.document;
            const styleId = "narrador-football-pointer-trail-style";
            const previous = doc.__narradorFootballPointerTrailHandler;
            if (previous) {{
                doc.removeEventListener("pointermove", previous);
            }}
            if (!doc.getElementById(styleId)) {{
                const style = doc.createElement("style");
                style.id = styleId;
                style.textContent = `
                    .narrador-football-pointer-trail {{
                        position: fixed;
                        left: 0;
                        top: 0;
                        width: var(--football-size, 18px);
                        height: var(--football-size, 18px);
                        pointer-events: none;
                        z-index: 2147483647;
                        opacity: 0.82;
                        object-fit: contain;
                        transform: translate(-50%, -50%) scale(1);
                        transition: opacity 620ms ease, transform 620ms ease;
                        filter: drop-shadow(0 4px 8px rgba(15, 23, 42, 0.22));
                        will-change: transform, opacity;
                    }}
                    @media (prefers-reduced-motion: reduce) {{
                        .narrador-football-pointer-trail {{
                            display: none !important;
                        }}
                    }}
                `;
                doc.head.appendChild(style);
            }}

            const iconSrc = "{ball_uri}";
            let lastSpawn = 0;
            let rotation = 0;
            const reduceMotion = window.parent.matchMedia("(prefers-reduced-motion: reduce)");

            const spawnBall = (event) => {{
                if (reduceMotion.matches) {{
                    return;
                }}
                const now = window.performance.now();
                if (now - lastSpawn < 90) {{
                    return;
                }}
                lastSpawn = now;
                rotation += 24 + Math.random() * 36;

                const ball = doc.createElement("img");
                const size = 13 + Math.random() * 11;
                const jitterX = (Math.random() - 0.5) * 9;
                const jitterY = (Math.random() - 0.5) * 9;
                const driftX = (Math.random() - 0.5) * 18;
                const driftY = 8 + Math.random() * 18;

                ball.src = iconSrc;
                ball.alt = "";
                ball.className = "narrador-football-pointer-trail";
                ball.style.setProperty("--football-size", `${{size.toFixed(1)}}px`);
                ball.style.left = `${{event.clientX + jitterX}}px`;
                ball.style.top = `${{event.clientY + jitterY}}px`;
                ball.style.transform = `translate(-50%, -50%) rotate(${{rotation}}deg) scale(1)`;

                doc.body.appendChild(ball);
                window.requestAnimationFrame(() => {{
                    ball.style.opacity = "0";
                    ball.style.transform =
                        `translate(-50%, -50%) translate(${{driftX}}px, ${{driftY}}px) ` +
                        `rotate(${{rotation + 90}}deg) scale(0.5)`;
                }});
                window.setTimeout(() => ball.remove(), 700);
            }};

            doc.__narradorFootballPointerTrailHandler = spawnBall;
            doc.addEventListener("pointermove", spawnBall, {{ passive: true }});
        }})();
        </script>
        """,
        height=0,
        width=0,
    )
