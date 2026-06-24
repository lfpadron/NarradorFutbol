"""Generate comparative narratives for two transformed matches."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI, OpenAIError

from src.comparison.match_comparison import compare_matches
from src.ingestion.utils import to_jsonable
from src.narrative.config import get_openai_api_key, get_openai_model


def generate_match_comparison_narrative(
    match_id_a: int,
    match_id_b: int,
    use_api: bool = False,
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
                input=_build_prompt(comparison),
                temperature=0.3,
            )
            narrative_markdown = _extract_response_text(response).strip()
            status = "generated"
        except OpenAIError as exc:
            narrative_markdown = _fallback_narrative(comparison)
            warnings.append(f"OpenAI API falló; se usó narrativa comparativa local. Detalle: {exc}")
        except Exception as exc:
            narrative_markdown = _fallback_narrative(comparison)
            warnings.append(f"No se pudo generar con API; se usó narrativa comparativa local. Detalle: {exc}")
    else:
        narrative_markdown = _fallback_narrative(comparison)
        if use_api and not api_key:
            warnings.append("OPENAI_API_KEY no está configurada; se usó narrativa comparativa local.")
        elif not use_api:
            warnings.append("Uso de OpenAI API desactivado; se usó narrativa comparativa local.")

    return to_jsonable(
        {
            "match_id_a": match_id_a,
            "match_id_b": match_id_b,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "model": model,
            "narrative_markdown": narrative_markdown,
            "warnings": warnings,
            "comparison_summary": comparison.get("summary_comparison", {}),
        }
    )


def _build_prompt(comparison: dict[str, Any]) -> str:
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


def _fallback_narrative(comparison: dict[str, Any]) -> str:
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

