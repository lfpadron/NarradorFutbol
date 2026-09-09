"""Prompt construction for AI match narratives."""

from __future__ import annotations

import json
from typing import Any

from src.ingestion.utils import to_jsonable
from src.narrative.config import SUPPORTED_TONES, validate_tone
from src.ui.i18n import ai_language_name, is_english, tone_display_name

TONE_INSTRUCTIONS = {
    "cronica_emocionante": "Tono de crónica deportiva emocionante, con ritmo y claridad.",
    "analisis_tecnico": "Tono analítico y táctico, priorizando patrones, dominio y eficacia.",
    "resumen_ejecutivo": "Tono breve, directo y orientado a conclusiones accionables.",
    "scouting": "Tono de reporte de scouting, destacando perfiles, impacto y señales observables.",
    "television": "Tono de narración televisiva, ágil y expresiva, sin perder precisión.",
}

TONE_INSTRUCTIONS_EN = {
    "cronica_emocionante": "Exciting sports chronicle tone, with pace and clarity.",
    "analisis_tecnico": "Analytical and tactical tone, prioritizing patterns, dominance, and efficiency.",
    "resumen_ejecutivo": "Brief, direct tone focused on actionable conclusions.",
    "scouting": "Scouting report tone, highlighting profiles, impact, and observable signals.",
    "television": "Broadcast narration tone, lively and expressive without losing precision.",
}


def build_match_narrative_prompt(
    context: dict[str, Any],
    tone: str = "cronica_emocionante",
    language: str = "es",
) -> str:
    tone = validate_tone(tone)
    context_json = json.dumps(to_jsonable(context), ensure_ascii=False, indent=2)
    tone_label = tone_display_name(tone, SUPPORTED_TONES[tone], language=language)
    tone_instruction = TONE_INSTRUCTIONS_EN[tone] if is_english(language) else TONE_INSTRUCTIONS[tone]

    if is_english(language):
        return f"""
You are a football narrator and analyst. Generate a Markdown narrative from the curated context.

Required language: {ai_language_name(language)}
Requested tone: {tone_label}
Tone instruction: {tone_instruction}

Required structure:

# Executive Summary

# Match Chronicle

# Tactical Keys

# Standout Players

# Key Moments

# Final Read

Mandatory rules:

- Do not invent goals, cards, players, or the scoreline.
- Use only the information in the context.
- If a data point is unavailable, do not mention it.
- Separate facts from interpretation.
- Keep the tone engaging, but faithful.
- Do not say "according to the data" in every paragraph.
- Do not exaggerate if xG or shots do not support it.
- Explicitly mention the scoreline.
- If a team dominated but lost, explain it.
- If validation.status != PASS, warn that the analysis may have limitations.
- Prioritize factual fidelity over narrative flourish.

Curated JSON context:

```json
{context_json}
```
""".strip()

    return f"""
Eres un narrador y analista de fútbol. Genera una narración en Markdown a partir del contexto curado.

Idioma obligatorio: {ai_language_name(language)}
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
