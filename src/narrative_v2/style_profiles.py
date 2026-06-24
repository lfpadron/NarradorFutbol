"""Style profiles for Narrador AI v2."""

from __future__ import annotations

from typing import Any


STYLE_PROFILES: dict[str, dict[str, Any]] = {
    "tactico": {
        "id": "tactico",
        "name": "Narrador tactico",
        "audience": "Entrenadores y analistas",
        "objective": "Explicar como se gano o perdio desde la estructura del partido.",
        "tone": "preciso, sobrio y analitico",
        "expected_length": "650-950 palabras",
        "min_words": 280,
        "max_words": 1100,
        "expected_sections": [
            "Lectura tactica",
            "Dominio y xG",
            "Presion y momentum",
            "Ataques peligrosos",
            "Claves del resultado",
        ],
        "must_include": ["dominio", "xG", "momentum", "presion", "ataques peligrosos"],
        "avoid": ["exageracion emocional", "frases de transmision", "conclusiones sin evidencia"],
        "quality_criteria": [
            "distingue volumen de eficacia",
            "explica fases del partido",
            "mantiene trazabilidad con metricas",
        ],
    },
    "television": {
        "id": "television",
        "name": "Narrador televisivo",
        "audience": "Transmision deportiva",
        "objective": "Narrar el partido con claridad, ritmo y emocion controlada.",
        "tone": "dinamico, claro y emocionante",
        "expected_length": "450-700 palabras",
        "min_words": 220,
        "max_words": 850,
        "expected_sections": [
            "Apertura",
            "Ritmo del partido",
            "Momento clave",
            "Figura",
            "Cierre",
        ],
        "must_include": ["momentos clave", "jugadores", "ritmo", "marcador"],
        "avoid": ["tecnicismos excesivos", "tablas", "parrafos demasiado largos"],
        "quality_criteria": [
            "se entiende en voz alta",
            "mantiene energia narrativa",
            "no sacrifica factualidad",
        ],
    },
    "periodistico": {
        "id": "periodistico",
        "name": "Narrador periodistico",
        "audience": "Lectores de nota deportiva",
        "objective": "Producir una cronica publicable del partido.",
        "tone": "periodistico, fluido y verificable",
        "expected_length": "550-850 palabras",
        "min_words": 250,
        "max_words": 1000,
        "expected_sections": [
            "Titular sugerido",
            "Bajada",
            "Cronica",
            "Claves",
            "Cierre",
        ],
        "must_include": ["titular", "bajada", "cronica", "claves"],
        "avoid": ["tablas", "lenguaje robotico", "exceso de bullets"],
        "quality_criteria": [
            "tiene enfoque editorial",
            "ordena hechos y lectura",
            "evita inventar contexto externo",
        ],
    },
    "scouting": {
        "id": "scouting",
        "name": "Narrador scouting",
        "audience": "Visores y direccion deportiva",
        "objective": "Evaluar jugadores relevantes y su impacto en el partido.",
        "tone": "observacional, concreto y orientado a decision",
        "expected_length": "500-800 palabras",
        "min_words": 240,
        "max_words": 950,
        "expected_sections": [
            "Jugadores observados",
            "Fortalezas",
            "Riesgos",
            "Rol tactico",
            "Conclusion scouting",
        ],
        "must_include": ["jugadores de impacto", "fortalezas", "riesgos", "rol tactico"],
        "avoid": ["proyecciones futuras sin evidencia", "comparaciones externas", "rumores"],
        "quality_criteria": [
            "prioriza evidencia del partido",
            "separa rendimiento de potencial",
            "nombra roles y riesgos",
        ],
    },
    "ejecutivo": {
        "id": "ejecutivo",
        "name": "Narrador ejecutivo",
        "audience": "Directivos y presentaciones",
        "objective": "Resumir hallazgos clave con implicaciones accionables.",
        "tone": "breve, claro y accionable",
        "expected_length": "220-450 palabras",
        "min_words": 120,
        "max_words": 550,
        "expected_sections": [
            "Conclusion",
            "Hallazgos clave",
            "Implicaciones",
            "Riesgos de lectura",
        ],
        "must_include": ["conclusion", "hallazgos", "implicaciones"],
        "avoid": ["parrafos largos", "detalle minuto a minuto", "jerga excesiva"],
        "quality_criteria": [
            "permite decidir rapido",
            "usa bullets cuando conviene",
            "declara limitaciones",
        ],
    },
}


def get_style_profile(style_id: str) -> dict[str, Any]:
    try:
        return STYLE_PROFILES[style_id]
    except KeyError as exc:
        supported = ", ".join(STYLE_PROFILES)
        raise ValueError(f"Unsupported style '{style_id}'. Supported styles: {supported}") from exc


def style_label_map() -> dict[str, str]:
    return {profile["name"]: style_id for style_id, profile in STYLE_PROFILES.items()}

