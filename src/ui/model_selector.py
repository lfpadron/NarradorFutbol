"""Shared model selector for the analysis AI tabs."""

from __future__ import annotations

import streamlit as st

from src.narrative.config import OPENAI_MODEL_DEFAULT, SUPPORTED_MODELS, get_openai_model


def render_model_selector(key: str) -> str:
    models = list(SUPPORTED_MODELS)
    default = get_openai_model()
    if default not in SUPPORTED_MODELS:
        default = OPENAI_MODEL_DEFAULT
    return st.selectbox(
        "Modelo de IA",
        models,
        index=models.index(default),
        format_func=SUPPORTED_MODELS.__getitem__,
        key=key,
    )
