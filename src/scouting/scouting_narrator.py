"""Generate Scouting AI narratives from player comparison context."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from openai import OpenAI, OpenAIError

from src.ingestion.utils import to_jsonable
from src.narrative.config import get_openai_api_key, get_openai_model
from src.scouting.scouting_language_guard import sanitize_scouting_language, validate_scouting_language
from src.scouting.scouting_context import build_player_scouting_context
from src.scouting.scouting_prompt import build_scouting_prompt


def generate_scouting_narrative(
    match_id_a: int,
    player_id_a: int,
    match_id_b: int | None = None,
    player_id_b: int | None = None,
    use_api: bool = True,
) -> dict[str, Any]:
    context = build_player_scouting_context(match_id_a, player_id_a, match_id_b, player_id_b)
    mode = str(context.get("mode") or "individual")
    model = get_openai_model()
    warnings: list[str] = list(context.get("warnings", []))
    status = "fallback"

    api_key = get_openai_api_key()
    if use_api and api_key:
        try:
            client = OpenAI(api_key=api_key)
            response = client.responses.create(
                model=model,
                input=build_scouting_prompt(context, mode=mode),
                temperature=0.3,
            )
            narrative_markdown = _extract_response_text(response).strip()
            status = "generated"
        except OpenAIError as exc:
            narrative_markdown = _fallback_scouting(context)
            warnings.append(f"OpenAI API falló; se usó fallback local de scouting. Detalle: {exc}")
        except Exception as exc:
            narrative_markdown = _fallback_scouting(context)
            warnings.append(f"No se pudo generar con API; se usó fallback local de scouting. Detalle: {exc}")
    else:
        narrative_markdown = _fallback_scouting(context)
        if use_api and not api_key:
            warnings.append("OPENAI_API_KEY no está configurada; se usó scouting local.")
        elif not use_api:
            warnings.append("Uso de OpenAI API desactivado; se usó scouting local.")

    language_warnings = validate_scouting_language(narrative_markdown)
    clean_markdown = sanitize_scouting_language(narrative_markdown)
    if clean_markdown != narrative_markdown:
        language_warnings.append("Se ajustó lenguaje no profesional antes de entregar el reporte.")
    narrative_markdown = clean_markdown
    residual_language_warnings = validate_scouting_language(narrative_markdown)
    language_warnings.extend(
        warning for warning in residual_language_warnings if warning not in language_warnings
    )

    reported_model = model if status == "generated" else "local-scouting-fallback"

    return to_jsonable(
        {
            "mode": mode,
            "match_id_a": match_id_a,
            "player_id_a": player_id_a,
            "match_id_b": match_id_b,
            "player_id_b": player_id_b,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "model": reported_model,
            "use_api": bool(use_api),
            "narrative_markdown": narrative_markdown,
            "warnings": warnings,
            "language_warnings": language_warnings,
            "context_summary": context.get("context_summary", {}),
            "context": context,
        }
    )


def _fallback_scouting(context: dict[str, Any]) -> str:
    mode = context.get("mode")
    player_a = context.get("player_a", {})
    player_b = context.get("player_b") or {}
    match_a = context.get("match_a", {})
    match_b = context.get("match_b") or {}
    radar = context.get("radar_metrics", {})
    strengths = context.get("strengths_weaknesses", {})
    warnings = context.get("warnings", [])
    warning_text = _warning_sentence(warnings)

    if mode == "comparativo":
        direct_section = _comparative_section(player_a, player_b, context)
        profile = (
            f"Jugador A: **{player_a.get('player_name')}** ({player_a.get('team_name')}) en {match_a.get('scoreline')}. "
            f"Jugador B: **{player_b.get('player_name')}** ({player_b.get('team_name')}) en {match_b.get('scoreline')}."
        )
    else:
        direct_section = ""
        profile = f"**{player_a.get('player_name')}** ({player_a.get('team_name')}) en {match_a.get('scoreline')}."

    return f"""# Reporte de scouting

## Resumen ejecutivo

{profile} La lectura está basada únicamente en los eventos observados del partido. {warning_text}

## Perfil del jugador

{_profile_text(player_a, radar)}

## Fortalezas observadas

{_strengths_text(strengths, 'player_a_strengths', player_a.get('player_name'))}

## Áreas de mejora o cautela

{_weaknesses_text(strengths, 'player_a_weaknesses', player_a.get('player_name'))}

## Rol táctico sugerido

{_role_text(player_a)}
{direct_section}
## Lectura para cuerpo técnico

{_technical_staff_text(player_a, player_b if mode == 'comparativo' else None, context)}

## Conclusión

Este reporte no predice carrera ni recomienda fichajes. Resume señales observadas: volumen, eficiencia, impacto y rol dentro del partido analizado.
"""


def _comparative_section(player_a: dict[str, Any], player_b: dict[str, Any], context: dict[str, Any]) -> str:
    strengths = context.get("strengths_weaknesses", {})
    summary = (context.get("comparison") or {}).get("summary_comparison", {})
    return f"""
## Comparación directa

Jugador B: **{player_b.get('player_name')}** ({player_b.get('team_name')}) ofrece un contraste útil. Diferencias B-A: goles {summary.get('diff_goals')}, xG {summary.get('diff_xg')}, tiros {summary.get('diff_shots')}, asistencias {summary.get('diff_assists')}, pases clave {summary.get('diff_key_passes')}, presiones {summary.get('diff_pressures')} e impact_score {summary.get('diff_impact_score')}.

Fortalezas de Jugador B: {_list_text(strengths.get('player_b_strengths', []))}. Cautelas de Jugador B: {_list_text(strengths.get('player_b_weaknesses', []))}.
"""


def _profile_text(player: dict[str, Any], radar: dict[str, Any]) -> str:
    values = radar.get("player_a", {}).get("values", [])
    categories = radar.get("categories", [])
    radar_text = ", ".join(f"{category} {value}" for category, value in zip(categories, values)) or "radar no disponible"
    return (
        f"Registró {player.get('events')} eventos, {player.get('shots')} tiros, {player.get('goals')} goles, "
        f"{player.get('xg')} xG, {player.get('assists')} asistencias, {player.get('key_passes')} pases clave, "
        f"{player.get('pressures')} presiones e impact_score {player.get('impact_score')}. Radar: {radar_text}."
    )


def _strengths_text(strengths: dict[str, Any], key: str, player_name: Any) -> str:
    values = strengths.get(key, [])
    if not values:
        return f"No hay fortalezas >= 70 para {player_name}; conviene revisar el perfil desde métricas específicas."
    return f"Fortalezas de {player_name}: {_list_text(values)}."


def _weaknesses_text(strengths: dict[str, Any], key: str, player_name: Any) -> str:
    values = strengths.get(key, [])
    if not values:
        return f"No hay áreas de cautela <= 30 para {player_name} dentro del radar disponible."
    return f"Áreas de cautela para {player_name}: {_list_text(values)}."


def _role_text(player: dict[str, Any]) -> str:
    signals = []
    if _number(player.get("goals")) > 0 or _number(player.get("xg")) >= 0.25:
        signals.append("atacar zonas de definición cuando el equipo logre transición o ventaja territorial")
    if _number(player.get("key_passes")) >= 3 or _number(player.get("progressive_passes")) >= 3:
        signals.append("participar en creación y progresión")
    if _number(player.get("pressures")) >= 20:
        signals.append("aportar presión tras pérdida o presión alta")
    if not signals:
        signals.append("mantener un rol contextual según necesidades del partido")
    return "Uso táctico sugerido con base en este partido: " + "; ".join(signals) + "."


def _technical_staff_text(
    player_a: dict[str, Any],
    player_b: dict[str, Any] | None,
    context: dict[str, Any],
) -> str:
    moment_count = len((context.get("key_moments") or {}).get("player_a", []))
    base = (
        f"Para cuerpo técnico, {player_a.get('player_name')} debe evaluarse separando impacto directo "
        f"({player_a.get('goals')} goles, {player_a.get('assists')} asistencias) de volumen "
        f"({player_a.get('events')} eventos). Momentos clave asociados: {moment_count}."
    )
    if player_b:
        base += f" La comparación con {player_b.get('player_name')} no debe leerse como ranking absoluto si los roles difieren."
    return base


def _warning_sentence(warnings: list[str]) -> str:
    if not warnings:
        return ""
    return "Advertencias relevantes: " + " ".join(warnings)


def _list_text(values: list[Any]) -> str:
    return ", ".join(str(value) for value in values) if values else "sin datos"


def _number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


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
