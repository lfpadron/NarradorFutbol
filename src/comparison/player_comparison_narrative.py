"""Narrative generation for player comparisons."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI, OpenAIError

from src.comparison.player_comparison import compare_players
from src.ingestion.utils import to_jsonable
from src.narrative.config import get_openai_api_key, get_openai_model


def generate_player_comparison_narrative(
    match_id_a: int,
    player_id_a: int,
    match_id_b: int,
    player_id_b: int,
    use_api: bool = False,
) -> dict[str, Any]:
    comparison = compare_players(match_id_a, player_id_a, match_id_b, player_id_b)
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
            "player_id_a": player_id_a,
            "match_id_b": match_id_b,
            "player_id_b": player_id_b,
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
        "player_a": comparison.get("player_a"),
        "player_b": comparison.get("player_b"),
        "match_a": comparison.get("match_a"),
        "match_b": comparison.get("match_b"),
        "summary_comparison": comparison.get("summary_comparison"),
        "attacking_comparison": comparison.get("attacking_comparison"),
        "passing_comparison": comparison.get("passing_comparison"),
        "defensive_comparison": comparison.get("defensive_comparison"),
        "impact_comparison": comparison.get("impact_comparison"),
        "key_moments_comparison": comparison.get("key_moments_comparison"),
        "warnings": comparison.get("warnings"),
    }
    return f"""Eres un analista de fútbol preparando una comparación de jugadores para scouting.

Reglas:
- No inventes goles, asistencias, equipos ni partido.
- No digas que un jugador fue mejor si los datos no lo sustentan.
- Si los roles son distintos, advierte que la comparación debe leerse con cuidado.
- Distingue volumen, eficiencia e impacto.
- Usa español de México con acentos correctos.
- Usa Markdown con estas secciones exactas:

# Comparación de jugadores

## Resumen ejecutivo

## Jugador A

## Jugador B

## Comparación ofensiva

## Comparación en creación

## Comparación defensiva

## Impacto en el partido

## Conclusión

Datos:
{json.dumps(compact, ensure_ascii=False, indent=2)}
"""


def _fallback_narrative(comparison: dict[str, Any]) -> str:
    player_a = comparison.get("player_a", {})
    player_b = comparison.get("player_b", {})
    match_a = comparison.get("match_a", {})
    match_b = comparison.get("match_b", {})
    summary = comparison.get("summary_comparison", {})
    attacking = comparison.get("attacking_comparison", {})
    passing = comparison.get("passing_comparison", {})
    defensive = comparison.get("defensive_comparison", {})
    impact = comparison.get("impact_comparison", {})

    role_warning = summary.get("role_warning")
    role_text = f" {role_warning}" if role_warning else ""

    return f"""# Comparación de jugadores

## Resumen ejecutivo

Jugador A: **{player_a.get('player_name', 'N/D')}** ({player_a.get('team_name', 'N/D')}) en {match_a.get('scoreline', 'N/D')}. Jugador B: **{player_b.get('player_name', 'N/D')}** ({player_b.get('team_name', 'N/D')}) en {match_b.get('scoreline', 'N/D')}.{role_text}

## Jugador A

Registró {player_a.get('events', 'N/D')} eventos, {player_a.get('shots', 'N/D')} tiros, {player_a.get('goals', 'N/D')} goles, {player_a.get('xg', 'N/D')} xG, {player_a.get('assists', 'N/D')} asistencias y {player_a.get('key_passes', 'N/D')} pases clave. Su impact_score disponible es {player_a.get('impact_score', 'N/D')}.

## Jugador B

Registró {player_b.get('events', 'N/D')} eventos, {player_b.get('shots', 'N/D')} tiros, {player_b.get('goals', 'N/D')} goles, {player_b.get('xg', 'N/D')} xG, {player_b.get('assists', 'N/D')} asistencias y {player_b.get('key_passes', 'N/D')} pases clave. Su impact_score disponible es {player_b.get('impact_score', 'N/D')}.

## Comparación ofensiva

- Tiros: A {attacking.get('shots', {}).get('player_a', 'N/D')} vs B {attacking.get('shots', {}).get('player_b', 'N/D')}.
- Goles: A {attacking.get('goals', {}).get('player_a', 'N/D')} vs B {attacking.get('goals', {}).get('player_b', 'N/D')}.
- xG: A {attacking.get('xg', {}).get('player_a', 'N/D')} vs B {attacking.get('xg', {}).get('player_b', 'N/D')}.
- Carries: A {attacking.get('carries', {}).get('player_a', 'N/D')} vs B {attacking.get('carries', {}).get('player_b', 'N/D')}.

## Comparación en creación

- Pases: A {passing.get('passes', {}).get('player_a', 'N/D')} vs B {passing.get('passes', {}).get('player_b', 'N/D')}.
- Precisión de pase: A {passing.get('pass_accuracy_pct', {}).get('player_a', 'N/D')}% vs B {passing.get('pass_accuracy_pct', {}).get('player_b', 'N/D')}%.
- Asistencias: A {passing.get('assists', {}).get('player_a', 'N/D')} vs B {passing.get('assists', {}).get('player_b', 'N/D')}.
- Pases clave: A {passing.get('key_passes', {}).get('player_a', 'N/D')} vs B {passing.get('key_passes', {}).get('player_b', 'N/D')}.
- Pases progresivos: A {passing.get('progressive_passes', {}).get('player_a', 'N/D')} vs B {passing.get('progressive_passes', {}).get('player_b', 'N/D')}.

## Comparación defensiva

- Presiones: A {defensive.get('pressures', {}).get('player_a', 'N/D')} vs B {defensive.get('pressures', {}).get('player_b', 'N/D')}.
- Duelos: A {defensive.get('duels', {}).get('player_a', 'N/D')} vs B {defensive.get('duels', {}).get('player_b', 'N/D')}.
- Faltas cometidas: A {defensive.get('fouls_committed', {}).get('player_a', 'N/D')} vs B {defensive.get('fouls_committed', {}).get('player_b', 'N/D')}.
- Faltas recibidas: A {defensive.get('fouls_won', {}).get('player_a', 'N/D')} vs B {defensive.get('fouls_won', {}).get('player_b', 'N/D')}.

## Impacto en el partido

El impacto debe leerse separando volumen e incidencia directa. Jugador A tuvo impact_score {impact.get('impact_score', {}).get('player_a', 'N/D')} y {impact.get('key_moments_count', {}).get('player_a', 'N/D')} momentos clave. Jugador B tuvo impact_score {impact.get('impact_score', {}).get('player_b', 'N/D')} y {impact.get('key_moments_count', {}).get('player_b', 'N/D')} momentos clave.

## Conclusión

Esta comparación es estadística y contextual. Sirve para observar perfiles, no para declarar superioridad absoluta: el rol, el partido y el equipo condicionan la lectura.
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
