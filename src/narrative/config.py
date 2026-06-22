"""Configuration helpers for narrative generation."""

from __future__ import annotations

import os


OPENAI_MODEL_DEFAULT = "gpt-4o-mini"

SUPPORTED_TONES = {
    "cronica_emocionante": "Crónica emocionante",
    "analisis_tecnico": "Análisis técnico",
    "resumen_ejecutivo": "Resumen ejecutivo",
    "scouting": "Scouting",
    "television": "Televisión",
}


def get_openai_api_key() -> str | None:
    value = os.getenv("OPENAI_API_KEY")
    return value.strip() if value and value.strip() else None


def has_openai_api_key() -> bool:
    return get_openai_api_key() is not None


def get_openai_model() -> str:
    return os.getenv("OPENAI_MODEL", OPENAI_MODEL_DEFAULT).strip() or OPENAI_MODEL_DEFAULT


def validate_tone(tone: str) -> str:
    if tone not in SUPPORTED_TONES:
        supported = ", ".join(SUPPORTED_TONES)
        raise ValueError(f"Unsupported tone '{tone}'. Supported tones: {supported}")
    return tone
