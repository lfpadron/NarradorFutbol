"""Language guardrails for professional scouting reports."""

from __future__ import annotations

import re


PROBLEMATIC_PATTERNS: tuple[tuple[str, str], ...] = (
    (r"\bdestruy[oó]\b", "expresión agresiva: destruyó"),
    (r"\bdestroz[oó]\b", "expresión agresiva: destrozó"),
    (r"\bhumill[oó]\b", "expresión humillante: humilló"),
    (r"\bmasacr[oó]\b", "metáfora violenta innecesaria: masacró"),
    (r"\baniquil[oó]\b", "metáfora violenta innecesaria: aniquiló"),
    (r"\baplast[oó]\b", "expresión sensacionalista: aplastó"),
    (r"\bfue un desastre\b", "juicio absoluto poco profesional: fue un desastre"),
    (r"\bpat[eé]tico\b", "lenguaje insultante: patético"),
    (r"\brid[ií]culo\b", "lenguaje despectivo: ridículo"),
    (r"\bin[uú]til\b", "lenguaje insultante: inútil"),
    (r"\bmediocre\b", "lenguaje despectivo: mediocre"),
    (r"\bbasura\b", "lenguaje vulgar: basura"),
    (r"\best[uú]pido\b", "lenguaje insultante: estúpido"),
    (r"\bidiota\b", "lenguaje insultante: idiota"),
    (r"\bimb[eé]cil\b", "lenguaje insultante: imbécil"),
    (r"\bpendej[oa]s?\b", "grosería común detectada"),
    (r"\bcabr[oó]n(?:es)?\b", "vocabulario vulgar detectado"),
    (r"\bchingad[ao]s?\b", "grosería común detectada"),
    (r"\bching[oó]\b", "grosería común detectada"),
    (r"\bverguiza\b", "vocabulario gráfico o vulgar detectado"),
    (r"\bverg[uü]enza\b", "juicio humillante potencial"),
)


SANITIZE_REPLACEMENTS: tuple[tuple[str, str], ...] = (
    (r"\bdestruy[oó]\b", "superó claramente"),
    (r"\bdestroz[oó]\b", "superó claramente"),
    (r"\bhumill[oó]\b", "dominó"),
    (r"\bmasacr[oó]\b", "superó con claridad"),
    (r"\baniquil[oó]\b", "neutralizó con claridad"),
    (r"\baplast[oó]\b", "dominó con claridad"),
    (r"\bfue un desastre\b", "tuvo dificultades"),
    (r"\bpat[eé]tico\b", "muy limitado en este tramo"),
    (r"\brid[ií]culo\b", "poco efectivo"),
    (r"\bin[uú]til\b", "poco influyente"),
    (r"\bmediocre\b", "discreto"),
    (r"\bbasura\b", "rendimiento insuficiente"),
    (r"\best[uú]pido\b", "impreciso"),
    (r"\bidiota\b", "impreciso"),
    (r"\bimb[eé]cil\b", "impreciso"),
    (r"\bpendej[oa]s?\b", "impreciso"),
    (r"\bcabr[oó]n(?:es)?\b", "exigente"),
    (r"\bchingad[ao]s?\b", "comprometido"),
    (r"\bching[oó]\b", "afectó"),
    (r"\bverguiza\b", "diferencia amplia"),
    (r"\bverg[uü]enza\b", "área de cautela"),
)


def validate_scouting_language(text: str) -> list[str]:
    """Return warnings for wording that is not suitable for professional scouting."""

    warnings: list[str] = []
    if not text:
        return warnings

    for pattern, message in PROBLEMATIC_PATTERNS:
        if re.search(pattern, text, flags=re.IGNORECASE):
            warnings.append(message)
    return warnings


def sanitize_scouting_language(text: str) -> str:
    """Replace problematic wording with professional alternatives."""

    clean = text or ""
    for pattern, replacement in SANITIZE_REPLACEMENTS:
        clean = re.sub(pattern, replacement, clean, flags=re.IGNORECASE)
    return clean
