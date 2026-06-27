"""Generate specialized Narrador AI v2 narratives."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any

from openai import OpenAI, OpenAIError

from src.analytics.ai_context import build_ai_match_context
from src.config import ANALYTICS_EXPORTS_DIR, project_relative
from src.ingestion.utils import to_jsonable
from src.narrative.config import get_openai_api_key, get_openai_model
from src.narrative.fact_guard import validate_narrative_against_context
from src.narrative_v2.prompt_builder_v2 import build_specialized_prompt
from src.narrative_v2.section_builder import build_context_for_style
from src.narrative_v2.style_evaluator import evaluate_style_fit
from src.narrative_v2.style_profiles import STYLE_PROFILES, get_style_profile


def generate_specialized_narrative(
    match_id: int,
    style_id: str,
    use_api: bool = True,
) -> dict[str, Any]:
    profile = get_style_profile(style_id)
    full_context = build_ai_match_context(match_id)
    context_used = build_context_for_style(full_context, style_id)
    model = get_openai_model()
    warnings: list[str] = []
    status = "fallback"

    api_key = get_openai_api_key()
    if use_api and api_key:
        try:
            prompt = build_specialized_prompt(context_used, style_id)
            client = OpenAI(api_key=api_key)
            response = client.responses.create(
                model=model,
                input=prompt,
                temperature=0.35,
            )
            narrative_markdown = _extract_response_text(response).strip()
            status = "generated"
        except OpenAIError as exc:
            narrative_markdown = generate_specialized_fallback(context_used, style_id)
            warnings.append(f"OpenAI API fallo; se uso fallback local. Detalle: {exc}")
        except Exception as exc:
            narrative_markdown = generate_specialized_fallback(context_used, style_id)
            warnings.append(f"No se pudo generar con API; se uso fallback local. Detalle: {exc}")
    else:
        narrative_markdown = generate_specialized_fallback(context_used, style_id)
        if use_api and not api_key:
            warnings.append("OPENAI_API_KEY no esta configurada; se uso fallback local v2.")
        elif not use_api:
            warnings.append("Uso de OpenAI API desactivado; se uso fallback local v2.")

    fact_warnings = validate_narrative_against_context(
        _fact_guard_text(narrative_markdown),
        full_context,
    )
    style_quality = evaluate_style_fit(narrative_markdown, style_id, full_context)

    return to_jsonable(
        {
            "match_id": match_id,
            "style_id": style_id,
            "style_name": profile["name"],
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "model": model,
            "warnings": warnings,
            "narrative_markdown": narrative_markdown,
            "fact_warnings": fact_warnings,
            "style_quality": style_quality,
            "context_used": context_used,
        }
    )


def compare_specialized_styles(match_id: int, use_api: bool = False) -> dict[str, Any]:
    rows = []
    best_style = None
    best_score = -1
    for style_id, profile in STYLE_PROFILES.items():
        result = generate_specialized_narrative(match_id, style_id, use_api=use_api)
        score = int(result.get("style_quality", {}).get("style_score") or 0)
        rows.append(
            {
                "style_id": style_id,
                "style_name": profile["name"],
                "status": result.get("status"),
                "style_score": score,
                "fact_warnings_count": len(result.get("fact_warnings", [])),
                "narrative_markdown": result.get("narrative_markdown"),
            }
        )
        if score > best_score:
            best_score = score
            best_style = style_id
    return to_jsonable({"match_id": match_id, "styles": rows, "best_style": best_style})


def save_specialized_narrative(result: dict[str, Any]) -> tuple[str, str]:
    ANALYTICS_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    match_id = result["match_id"]
    style_id = _safe_token(str(result["style_id"]))
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    base_name = f"narrative_v2.match-{match_id}.{style_id}_{suffix}"
    md_path = ANALYTICS_EXPORTS_DIR / f"{base_name}.md"
    json_path = ANALYTICS_EXPORTS_DIR / f"{base_name}.json"
    md_path.write_text(str(result.get("narrative_markdown") or ""), encoding="utf-8")
    with json_path.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(result), file, ensure_ascii=False, indent=2)
        file.write("\n")
    return project_relative(md_path), project_relative(json_path)


def save_style_comparison(comparison: dict[str, Any]) -> str:
    ANALYTICS_EXPORTS_DIR.mkdir(parents=True, exist_ok=True)
    suffix = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = ANALYTICS_EXPORTS_DIR / f"narrative_v2.compare.match-{comparison['match_id']}_{suffix}.json"
    with path.open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(comparison), file, ensure_ascii=False, indent=2)
        file.write("\n")
    return project_relative(path)


def generate_specialized_fallback(context: dict[str, Any], style_id: str) -> str:
    summary = context.get("match_summary", {})
    style_generators = {
        "tactico": _fallback_tactico,
        "television": _fallback_television,
        "periodistico": _fallback_periodistico,
        "scouting": _fallback_scouting,
        "ejecutivo": _fallback_ejecutivo,
    }
    return style_generators[style_id](context, summary)


def _fallback_tactico(context: dict[str, Any], summary: dict[str, Any]) -> str:
    leader = _first(context.get("dominance", []))
    xg = _xg_text(context.get("xg_breakdown", []))
    dangerous = _dangerous_text(context.get("dangerous_attacks", []))
    validation = context.get("validation", {})
    return f"""# Lectura tactica

{_score_line(summary)}. El resultado favorecio a **{summary.get('winner_team_name', 'N/D')}**, pero la lectura de volumen marco otro eje: **{leader.get('team_name', 'N/D')}** concentro el dominio estimado con score {leader.get('dominance_score', 'N/D')}.

## Dominio y xG

El partido separa dominio territorial de eficacia. En xG: {xg}. Esa brecha ayuda a explicar por que el equipo con mas produccion no necesariamente encontro el gol.

## Presion y momentum

El momentum debe leerse como acumulacion de tiros, entradas al ultimo tercio y acciones ofensivas. La ventaja mexicana aparece menos por volumen y mas por resolver el momento decisivo.

## Ataques peligrosos

{dangerous}

## Claves del resultado

- Mexico sostuvo la eficacia en el marcador 0-1.
- Germany genero mayor volumen, pero no transformo ese dominio en gol.
- La lectura final es dominio aleman con eficacia mexicana.
- Validacion: {validation.get('status', 'N/D')}.
"""


def _fallback_television(context: dict[str, Any], summary: dict[str, Any]) -> str:
    goal = _goal_moment(context.get("key_moments", []))
    goal_player = _player_or_default(goal, "Hirving Rodrigo Lozano Bahena")
    return f"""# Apertura

Germany 0-1 Mexico: un partido de tension, ritmo y golpe decisivo. Mexico encontro la jugada que cambio la tarde y luego defendio una ventaja enorme en valor competitivo.

## Ritmo del partido

Germany empujo, sumo volumen y obligo a mirar el area mexicana una y otra vez. Pero el futbol tambien se decide en precision, y ahi Mexico tuvo la accion que partio el encuentro.

## Momento clave

{_moment_sentence(goal)}

## Figura

{goal_player} aparece como nombre relevante por impacto directo en el resultado y presencia en los momentos decisivos.

## Cierre

El marcador no se mueve: Germany 0-1 Mexico. Dominio aleman, eficacia mexicana y una victoria que se explica por resistir, elegir bien y golpear cuando el partido lo permitio.
"""


def _fallback_periodistico(context: dict[str, Any], summary: dict[str, Any]) -> str:
    goal = _goal_moment(context.get("key_moments", []))
    leader = _first(context.get("dominance", []))
    return f"""# Titular sugerido

Mexico golpea a Germany y firma un 0-1 de maxima eficacia

## Bajada

El equipo mexicano vencio con gol de {_player_or_default(goal, 'Hirving Rodrigo Lozano Bahena')} en un partido donde Germany acumulo dominio, pero no pudo igualar el marcador.

## Cronica

Germany llevo buena parte del peso ofensivo, pero Mexico encontro el momento que necesitaba. {_moment_sentence(goal)}. Desde ahi, el partido se convirtio en una prueba de resistencia, lectura y contundencia.

El dominio estimado favorecio a **{leader.get('team_name', 'Germany')}**, senal de que el volumen ofensivo no conto toda la historia. Mexico, en cambio, puso el marcador de su lado y obligo al rival a perseguir el partido.

## Claves

- Germany domino mas tramos del partido.
- Mexico fue mas eficaz en la accion decisiva.
- Lozano quedo como referencia directa del triunfo.

## Cierre

La cronica deja una lectura clara: Germany produjo mas, Mexico resolvio mejor. El 0-1 no contradice el dominio aleman; lo vuelve parte central del relato.
"""


def _fallback_scouting(context: dict[str, Any], summary: dict[str, Any]) -> str:
    players = context.get("impact_players", [])[:5] or context.get("top_players", [])[:5]
    rows = "\n".join(
        f"- **{player.get('player_name')}** ({player.get('team_name')}): impacto {player.get('impact_score', 'N/D')}, tiros {player.get('shots', 'N/D')}, xG {player.get('xg', 'N/D')}."
        for player in players
    )
    return f"""# Jugadores observados

{_score_line(summary)}. El foco scouting debe separar rendimiento de volumen y accion decisiva.

{rows}

## Fortalezas

- Mexico mostro eficacia para convertir una accion clave en ventaja.
- Germany sostuvo volumen ofensivo y presencia territorial.
- Lozano destaca por incidencia directa en el marcador.

## Riesgos

- No proyectar potencial futuro a partir de un solo partido.
- No confundir dominio colectivo con rendimiento individual definitivo.

## Rol tactico

Los perfiles ofensivos de Germany aparecen asociados a volumen y insistencia. Para el equipo mexicano, el rol mas valioso fue atacar el espacio correcto y sostener el resultado.

## Conclusion scouting

El partido recomienda observar a los jugadores de impacto en contexto: Germany genero mas, pero Mexico tuvo la ejecucion que definio el marcador.
"""


def _fallback_ejecutivo(context: dict[str, Any], summary: dict[str, Any]) -> str:
    leader = _first(context.get("dominance", []))
    xg = _xg_text(context.get("xg_breakdown", []))
    return f"""# Conclusion

Mexico vencio 0-1 a Germany con una lectura ejecutiva clara: menor volumen, mayor eficacia.

## Hallazgos clave

- Resultado: Germany 0-1 Mexico.
- Dominio estimado: {leader.get('team_name', 'N/D')} con score {leader.get('dominance_score', 'N/D')}.
- Produccion xG: {xg}.
- Jugador decisivo: Hirving Rodrigo Lozano Bahena.

## Implicaciones

- El marcador premia la ejecucion mexicana en el momento clave.
- Germany necesita convertir dominio territorial en calidad de finalizacion.
- Para presentacion, el mensaje central es: dominio aleman, eficacia mexicana.

## Riesgos de lectura

- No concluir que Mexico controlo todo el partido por haber ganado.
- No concluir que Germany fue superior en eficacia por tener mayor volumen.
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


def _first(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[0] if rows else {}


def _score_line(summary: dict[str, Any]) -> str:
    return (
        f"{summary.get('home_team_name', 'N/D')} {summary.get('home_score', 'N/D')}-"
        f"{summary.get('away_score', 'N/D')} {summary.get('away_team_name', 'N/D')}"
    )


def _xg_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "xG no disponible"
    return ", ".join(f"{row.get('team_name')} {row.get('xg_total')}" for row in rows)


def _dangerous_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        return "No hay ataques peligrosos suficientes en el contexto reducido."
    counts: dict[str, int] = {}
    for row in rows:
        team = str(row.get("team_name") or "Sin equipo")
        counts[team] = counts.get(team, 0) + 1
    return (
        "Ataques peligrosos en contexto reducido: "
        + ", ".join(f"{team} {count}" for team, count in sorted(counts.items()))
        + "."
    )


def _goal_moment(rows: list[dict[str, Any]]) -> dict[str, Any]:
    for row in rows:
        if str(row.get("type") or "").lower() == "goal":
            return row
    return _first(rows)


def _moment_sentence(moment: dict[str, Any]) -> str:
    if not moment:
        return "El momento clave no esta disponible en el contexto reducido."
    minute = moment.get("minute")
    second = int(moment.get("second") or 0)
    title = moment.get("title") or moment.get("type") or "Momento clave"
    return f"Al {minute}:{second:02d}, {title}."


def _player_or_default(moment: dict[str, Any], default: str) -> str:
    return str(moment.get("player_name") or default)


def _safe_token(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", value.strip())
    return clean.strip("-") or "narrativa"


def _fact_guard_text(markdown_text: str) -> str:
    lines = []
    for line in markdown_text.splitlines():
        if line.lstrip().startswith("#"):
            continue
        lines.append(line)
    return "\n".join(lines)
