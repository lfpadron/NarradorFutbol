"""Prompt builder for specialized narratives."""

from __future__ import annotations

import json
from typing import Any

from src.ingestion.utils import to_jsonable
from src.narrative_v2.style_profiles import get_style_profile
from src.ui.i18n import ai_language_name, is_english, style_display_name, translate_text

COMMON_RULES = [
    "No inventar marcador, goles, jugadores, tarjetas ni eventos.",
    "Usar solo el contexto analitico entregado.",
    "Diferenciar hechos e interpretacion.",
    "Si falta un dato, no mencionarlo.",
    "Si validation.status no es PASS, advertir limitaciones.",
    "Mantener trazabilidad conceptual sin repetir 'segun los datos' en cada parrafo.",
    "No modificar el marcador.",
    "No inventar nombres de jugadores.",
    "Entregar la salida en Markdown.",
]

COMMON_RULES_EN = [
    "Do not invent the scoreline, goals, players, cards, or events.",
    "Use only the analytical context provided.",
    "Separate facts from interpretation.",
    "If a data point is missing, do not mention it.",
    "If validation.status is not PASS, warn about limitations.",
    "Keep conceptual traceability without repeating 'according to the data' in every paragraph.",
    "Do not modify the scoreline.",
    "Do not invent player names.",
    "Return the output in Markdown.",
]


def build_specialized_prompt(context: dict[str, Any], style_id: str, language: str = "es") -> str:
    profile = get_style_profile(style_id)
    context_json = json.dumps(to_jsonable(context), ensure_ascii=False, indent=2)
    expected_sections = "\n".join(
        f"- {translate_text(section, language=language)}" for section in profile["expected_sections"]
    )
    must_include = "\n".join(f"- {translate_text(item, language=language)}" for item in profile["must_include"])
    avoid = "\n".join(f"- {translate_text(item, language=language)}" for item in profile["avoid"])
    quality = "\n".join(f"- {translate_text(item, language=language)}" for item in profile["quality_criteria"])
    rules = "\n".join(f"- {rule}" for rule in (COMMON_RULES_EN if is_english(language) else COMMON_RULES))

    if is_english(language):
        return f"""You are Narrador AI v2, a football analyst and narrator.

Generate a specialized narrative for this profile.
Required language: {ai_language_name(language)}
- Style: {style_display_name(style_id, profile["name"], language=language)}
- Audience: {translate_text(profile["audience"], language=language)}
- Objective: {translate_text(profile["objective"], language=language)}
- Tone: {translate_text(profile["tone"], language=language)}
- Expected length: {translate_text(profile["expected_length"], language=language)}

Expected sections:
{expected_sections}

Must include:
{must_include}

Must avoid:
{avoid}

Quality criteria:
{quality}

Common rules:
{rules}

Reduced analytical context:
```json
{context_json}
```

Return only Markdown ready to read or publish.
"""

    return f"""Eres Narrador AI v2, un analista y narrador de futbol.

Idioma obligatorio: {ai_language_name(language)}
Genera una narrativa especializada para este perfil:
- Estilo: {profile["name"]}
- Audiencia: {profile["audience"]}
- Objetivo: {profile["objective"]}
- Tono: {profile["tone"]}
- Longitud esperada: {profile["expected_length"]}

Secciones esperadas:
{expected_sections}

Debe incluir:
{must_include}

Debe evitar:
{avoid}

Criterios de calidad:
{quality}

Reglas comunes:
{rules}

Contexto analitico reducido:
```json
{context_json}
```

Devuelve solo Markdown listo para leerse o publicarse.
"""
