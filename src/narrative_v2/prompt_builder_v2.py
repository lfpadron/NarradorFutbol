"""Prompt builder for specialized narratives."""

from __future__ import annotations

import json
from typing import Any

from src.ingestion.utils import to_jsonable
from src.narrative_v2.style_profiles import get_style_profile

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


def build_specialized_prompt(context: dict[str, Any], style_id: str) -> str:
    profile = get_style_profile(style_id)
    context_json = json.dumps(to_jsonable(context), ensure_ascii=False, indent=2)
    expected_sections = "\n".join(f"- {section}" for section in profile["expected_sections"])
    must_include = "\n".join(f"- {item}" for item in profile["must_include"])
    avoid = "\n".join(f"- {item}" for item in profile["avoid"])
    quality = "\n".join(f"- {item}" for item in profile["quality_criteria"])
    rules = "\n".join(f"- {rule}" for rule in COMMON_RULES)

    return f"""Eres Narrador AI v2, un analista y narrador de futbol.

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
