"""Generate comparative narratives for two transformed matches."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI, OpenAIError

from src.comparison.match_comparison import compare_matches
from src.ingestion.utils import to_jsonable
from src.narrative.config import get_openai_api_key, get_openai_model
from src.ui.i18n import is_english


def generate_match_comparison_narrative(
    match_id_a: int,
    match_id_b: int,
    use_api: bool = False,
    language: str = "es",
) -> dict[str, Any]:
    """Create a comparative narrative with API generation or local fallback."""

    comparison = compare_matches(match_id_a, match_id_b)
    model = get_openai_model()
    warnings: list[str] = []
    status = "fallback"

    api_key = get_openai_api_key()
    if use_api and api_key:
        try:
            client = OpenAI(api_key=api_key)
            response = client.responses.create(
                model=model,
                input=_build_prompt(comparison, language=language),
                temperature=0.3,
            )
            narrative_markdown = _extract_response_text(response).strip()
            status = "generated"
        except OpenAIError as exc:
            narrative_markdown = _fallback_narrative(comparison, language=language)
            warnings.append(
                _warning(
                    "OpenAI API falló; se usó narrativa comparativa local.",
                    "OpenAI API failed; local comparative narrative used.",
                    language,
                    exc,
                )
            )
        except Exception as exc:
            narrative_markdown = _fallback_narrative(comparison, language=language)
            warnings.append(
                _warning(
                    "No se pudo generar con API; se usó narrativa comparativa local.",
                    "Could not generate with API; local comparative narrative used.",
                    language,
                    exc,
                )
            )
    else:
        narrative_markdown = _fallback_narrative(comparison, language=language)
        if use_api and not api_key:
            warnings.append(
                "OPENAI_API_KEY is not configured; local comparative narrative used."
                if is_english(language)
                else "OPENAI_API_KEY no está configurada; se usó narrativa comparativa local."
            )
        elif not use_api:
            warnings.append(
                "OpenAI API use is disabled; local comparative narrative used."
                if is_english(language)
                else "Uso de OpenAI API desactivado; se usó narrativa comparativa local."
            )

    return to_jsonable(
        {
            "match_id_a": match_id_a,
            "match_id_b": match_id_b,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "model": model,
            "language": language,
            "narrative_markdown": narrative_markdown,
            "warnings": warnings,
            "comparison_summary": comparison.get("summary_comparison", {}),
        }
    )


def _build_prompt(comparison: dict[str, Any], language: str = "es") -> str:
    compact = {
        "match_a": comparison.get("match_a"),
        "match_b": comparison.get("match_b"),
        "summary_comparison": comparison.get("summary_comparison"),
        "shot_comparison": comparison.get("shot_comparison"),
        "xg_comparison": comparison.get("xg_comparison"),
        "pass_comparison": comparison.get("pass_comparison"),
        "possession_comparison": comparison.get("possession_comparison"),
        "dominance_comparison": comparison.get("dominance_comparison"),
        "momentum_comparison": comparison.get("momentum_comparison"),
        "dangerous_attacks_comparison": comparison.get("dangerous_attacks_comparison"),
        "impact_players_comparison": comparison.get("impact_players_comparison"),
        "key_moments_comparison": comparison.get("key_moments_comparison"),
        "warnings": comparison.get("warnings"),
    }
    if is_english(language):
        return f"""You are a football analyst. Write a comparative narrative in clear professional English.

Rules:
- Do not invent data.
- Do not mix scorelines.
- Always refer to the matches as Match A and Match B.
- If a data point is missing, omit it.
- Use Markdown with these exact sections:

# Match Comparison

## Executive Summary

## Match A

## Match B

## Key Differences

## Compared Tactical Read

## Decisive Players

## Conclusion

Data:
{json.dumps(compact, ensure_ascii=False, indent=2)}
"""
    return f"""Eres un analista de fútbol. Escribe una narrativa comparativa en español de México.

Reglas:
- No inventes datos.
- No mezcles marcadores.
- Refiérete siempre como Partido A y Partido B.
- Si falta algún dato, omítelo.
- Usa Markdown con estas secciones exactas:

# Comparación de partidos

## Resumen ejecutivo

## Partido A

## Partido B

## Diferencias clave

## Lectura táctica comparada

## Jugadores determinantes

## Conclusión

Datos:
{json.dumps(compact, ensure_ascii=False, indent=2)}
"""


def _fallback_narrative(comparison: dict[str, Any], language: str = "es") -> str:
    match_a = comparison.get("match_a", {})
    match_b = comparison.get("match_b", {})
    summary = comparison.get("summary_comparison", {})
    shots = comparison.get("shot_comparison", {})
    xg = comparison.get("xg_comparison", {})
    passes = comparison.get("pass_comparison", {})
    dominance = comparison.get("dominance_comparison", {})
    dangerous = comparison.get("dangerous_attacks_comparison", {})
    impact = comparison.get("impact_players_comparison", {})
    key_moments = comparison.get("key_moments_comparison", {})

    if is_english(language):
        return f"""# Match Comparison

## Executive Summary

Match A: **{match_a.get('scoreline', 'N/A')}**. Match B: **{match_b.get('scoreline', 'N/A')}**. The comparison shows differences in volume, efficiency, and intensity: {summary.get('more_intense_match', 'N/A')} was the match with the highest estimated intensity.

## Match A

Match A had {match_a.get('total_shots', 'N/A')} shots, total xG of {match_a.get('total_xg', 'N/A')}, {match_a.get('total_passes', 'N/A')} passes, and {match_a.get('dangerous_attacks', 'N/A')} dangerous attacks. Its intensity was labelled **{summary.get('intensity_a', {}).get('label', 'N/A')}**.

## Match B

Match B had {match_b.get('total_shots', 'N/A')} shots, total xG of {match_b.get('total_xg', 'N/A')}, {match_b.get('total_passes', 'N/A')} passes, and {match_b.get('dangerous_attacks', 'N/A')} dangerous attacks. Its intensity was labelled **{summary.get('intensity_b', {}).get('label', 'N/A')}**.

## Key Differences

- Shots: Match A {shots.get('match_a', 'N/A')} vs Match B {shots.get('match_b', 'N/A')}; B-A difference: {shots.get('difference_b_minus_a', 'N/A')}.
- xG: Match A {xg.get('match_a', 'N/A')} vs Match B {xg.get('match_b', 'N/A')}; B-A difference: {xg.get('difference_b_minus_a', 'N/A')}.
- Passes: Match A {passes.get('total_passes', {}).get('match_a', 'N/A')} vs Match B {passes.get('total_passes', {}).get('match_b', 'N/A')}; B-A difference: {passes.get('total_passes', {}).get('difference_b_minus_a', 'N/A')}.
- Dangerous attacks: Match A {dangerous.get('match_a', 'N/A')} vs Match B {dangerous.get('match_b', 'N/A')}; B-A difference: {dangerous.get('difference_b_minus_a', 'N/A')}.
- Key moments: Match A {key_moments.get('total_key_moments', {}).get('match_a', 'N/A')} vs Match B {key_moments.get('total_key_moments', {}).get('match_b', 'N/A')}.

## Compared Tactical Read

In Match A, estimated dominance favoured **{dominance.get('leader_a', {}).get('team_name', 'N/A')}** with score {dominance.get('leader_a', {}).get('dominance_score', 'N/A')}. In Match B, it favoured **{dominance.get('leader_b', {}).get('team_name', 'N/A')}** with score {dominance.get('leader_b', {}).get('dominance_score', 'N/A')}. This contrast separates territorial control, attacking production, and scoreboard efficiency.

## Decisive Players

- Match A: {impact.get('top_player_a', {}).get('player_name', 'N/A')} ({impact.get('top_player_a', {}).get('team_name', 'N/A')}), impact {impact.get('top_player_a', {}).get('impact_score', 'N/A')}.
- Match B: {impact.get('top_player_b', {}).get('player_name', 'N/A')} ({impact.get('top_player_b', {}).get('team_name', 'N/A')}), impact {impact.get('top_player_b', {}).get('impact_score', 'N/A')}.

## Conclusion

The comparison helps explain whether a match was more intense through event and shot volume, or more efficient by turning less production into advantage. Match A and Match B should be read separately: each scoreline belongs to its own competitive context.
"""

    return f"""# Comparación de partidos

## Resumen ejecutivo

Partido A: **{match_a.get('scoreline', 'N/D')}**. Partido B: **{match_b.get('scoreline', 'N/D')}**. La comparación muestra diferencias en volumen, eficacia e intensidad: {summary.get('more_intense_match', 'N/D')} fue el partido con mayor intensidad estimada.

## Partido A

Partido A tuvo {match_a.get('total_shots', 'N/D')} tiros, xG total de {match_a.get('total_xg', 'N/D')}, {match_a.get('total_passes', 'N/D')} pases y {match_a.get('dangerous_attacks', 'N/D')} ataques peligrosos. Su intensidad quedó etiquetada como **{summary.get('intensity_a', {}).get('label', 'N/D')}**.

## Partido B

Partido B tuvo {match_b.get('total_shots', 'N/D')} tiros, xG total de {match_b.get('total_xg', 'N/D')}, {match_b.get('total_passes', 'N/D')} pases y {match_b.get('dangerous_attacks', 'N/D')} ataques peligrosos. Su intensidad quedó etiquetada como **{summary.get('intensity_b', {}).get('label', 'N/D')}**.

## Diferencias clave

- Tiros: Partido A {shots.get('match_a', 'N/D')} vs Partido B {shots.get('match_b', 'N/D')}; diferencia B-A: {shots.get('difference_b_minus_a', 'N/D')}.
- xG: Partido A {xg.get('match_a', 'N/D')} vs Partido B {xg.get('match_b', 'N/D')}; diferencia B-A: {xg.get('difference_b_minus_a', 'N/D')}.
- Pases: Partido A {passes.get('total_passes', {}).get('match_a', 'N/D')} vs Partido B {passes.get('total_passes', {}).get('match_b', 'N/D')}; diferencia B-A: {passes.get('total_passes', {}).get('difference_b_minus_a', 'N/D')}.
- Ataques peligrosos: Partido A {dangerous.get('match_a', 'N/D')} vs Partido B {dangerous.get('match_b', 'N/D')}; diferencia B-A: {dangerous.get('difference_b_minus_a', 'N/D')}.
- Momentos clave: Partido A {key_moments.get('total_key_moments', {}).get('match_a', 'N/D')} vs Partido B {key_moments.get('total_key_moments', {}).get('match_b', 'N/D')}.

## Lectura táctica comparada

En Partido A, el dominio estimado favoreció a **{dominance.get('leader_a', {}).get('team_name', 'N/D')}** con score {dominance.get('leader_a', {}).get('dominance_score', 'N/D')}. En Partido B, favoreció a **{dominance.get('leader_b', {}).get('team_name', 'N/D')}** con score {dominance.get('leader_b', {}).get('dominance_score', 'N/D')}. Esta diferencia permite separar control territorial, producción ofensiva y eficacia en el marcador.

## Jugadores determinantes

- Partido A: {impact.get('top_player_a', {}).get('player_name', 'N/D')} ({impact.get('top_player_a', {}).get('team_name', 'N/D')}), impacto {impact.get('top_player_a', {}).get('impact_score', 'N/D')}.
- Partido B: {impact.get('top_player_b', {}).get('player_name', 'N/D')} ({impact.get('top_player_b', {}).get('team_name', 'N/D')}), impacto {impact.get('top_player_b', {}).get('impact_score', 'N/D')}.

## Conclusión

La lectura comparada ayuda a explicar si un partido fue más intenso por volumen de eventos y tiros, o más eficiente por convertir menos producción en ventaja. Partido A y Partido B deben leerse por separado: cada marcador pertenece a su propio contexto competitivo.
"""


def _warning(spanish: str, english: str, language: str, exc: Exception) -> str:
    message = english if is_english(language) else spanish
    detail_label = "Detail" if is_english(language) else "Detalle"
    return f"{message} {detail_label}: {exc}"


def _extract_response_text(response: Any) -> str:
    output_text = getattr(response, "output_text", None)
    if output_text:
        return str(output_text)
    output = getattr(response, "output", None)
    if output:
        chunks: list[str] = []
        for item in output:
            for content in getattr(item, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    chunks.append(str(text))
        if chunks:
            return "\n".join(chunks)
    return str(response)
