"""Heuristic style-fit evaluation for Narrador AI v2."""

from __future__ import annotations

import re
import unicodedata
from typing import Any

from src.narrative.fact_guard import validate_narrative_against_context
from src.narrative_v2.style_profiles import get_style_profile


def evaluate_style_fit(narrative: str, style_id: str, context: dict[str, Any]) -> dict[str, Any]:
    profile = get_style_profile(style_id)
    normalized = _normalize(narrative)
    words = re.findall(r"\w+", normalized)
    missing_sections = [
        section
        for section in profile["expected_sections"]
        if _normalize(section) not in normalized
    ]
    structure_score = max(0, 100 - len(missing_sections) * 16)
    audience_fit_score = _audience_fit_score(style_id, normalized)
    length_score = _length_score(len(words), profile["min_words"], profile["max_words"])
    fact_warnings = validate_narrative_against_context(_fact_guard_text(narrative), context)
    factuality_score = max(0, 100 - len(fact_warnings) * 15)
    style_score = round((structure_score + audience_fit_score + length_score + factuality_score) / 4)
    warnings = list(fact_warnings)
    if length_score < 70:
        warnings.append("La longitud se aleja del rango esperado para el estilo.")
    if missing_sections:
        warnings.append("Faltan secciones esperadas para el perfil.")

    return {
        "style_score": style_score,
        "structure_score": structure_score,
        "audience_fit_score": audience_fit_score,
        "factuality_score": factuality_score,
        "missing_expected_sections": missing_sections,
        "warnings": warnings,
    }


def _audience_fit_score(style_id: str, normalized: str) -> int:
    checks = {
        "tactico": ["dominio", "xg", "momentum", "presion", "ataques peligrosos"],
        "television": ["ritmo", "momento clave", "figura", "cierre"],
        "periodistico": ["titular", "bajada", "cronica", "claves"],
        "scouting": ["fortalezas", "riesgos", "rol tactico", "jugadores"],
        "ejecutivo": ["conclusion", "hallazgos", "implicaciones", "- "],
    }
    expected = checks[style_id]
    hits = sum(1 for item in expected if _normalize(item) in normalized)
    return round((hits / len(expected)) * 100)


def _length_score(word_count: int, minimum: int, maximum: int) -> int:
    if minimum <= word_count <= maximum:
        return 100
    if word_count < minimum:
        return max(35, round((word_count / minimum) * 100))
    overflow = word_count - maximum
    return max(45, 100 - round((overflow / maximum) * 100))


def _normalize(value: str) -> str:
    decomposed = unicodedata.normalize("NFKD", value)
    ascii_value = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    return re.sub(r"\s+", " ", ascii_value).strip().lower()


def _fact_guard_text(markdown_text: str) -> str:
    lines = []
    for line in markdown_text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)
