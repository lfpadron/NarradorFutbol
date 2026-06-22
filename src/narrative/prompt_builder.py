"""Prompt construction for AI match narratives."""

from __future__ import annotations

import json
from typing import Any

from src.ingestion.utils import to_jsonable
from src.narrative.config import SUPPORTED_TONES, validate_tone


TONE_INSTRUCTIONS = {
    "cronica_emocionante": "Tono de crónica deportiva emocionante, con ritmo y claridad.",
    "analisis_tecnico": "Tono analítico y táctico, priorizando patrones, dominio y eficacia.",
    "resumen_ejecutivo": "Tono breve, directo y orientado a conclusiones accionables.",
    "scouting": "Tono de reporte de scouting, destacando perfiles, impacto y señales observables.",
    "television": "Tono de narración televisiva, ágil y expresiva, sin perder precisión.",
}


def build_match_narrative_prompt(context: dict[str, Any], tone: str = "cronica_emocionante") -> str:
    tone = validate_tone(tone)
    context_json = json.dumps(to_jsonable(context), ensure_ascii=False, indent=2)
    tone_label = SUPPORTED_TONES[tone]
    tone_instruction = TONE_INSTRUCTIONS[tone]

    return f"""
Eres un narrador y analista de fútbol. Genera una narración en Markdown a partir del contexto curado.

Tono solicitado: {tone_label}
Instrucción de tono: {tone_instruction}

Estructura obligatoria:

# Resumen ejecutivo

# Crónica del partido

# Claves tácticas

# Jugadores destacados

# Momentos clave

# Lectura final

Reglas obligatorias:

- No inventes goles, tarjetas, jugadores ni marcador.
- Usa solo la información del contexto.
- Si un dato no está disponible, no lo menciones.
- Diferencia hechos de interpretación.
- Mantén tono emocionante, pero fiel.
- No digas “según los datos” en cada párrafo.
- No exageres si el xG o los tiros no lo sustentan.
- Menciona explícitamente el marcador.
- Si un equipo dominó pero perdió, explícalo.
- Si validation.status != PASS, advierte que el análisis puede tener limitaciones.
- Prioriza fidelidad factual sobre floritura narrativa.

Contexto curado JSON:

```json
{context_json}
```
""".strip()

