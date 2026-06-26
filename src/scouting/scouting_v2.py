"""Scouting AI v2: tactical profiles and player archetypes."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.ingestion.utils import to_jsonable
from src.scouting.scouting_language_guard import sanitize_scouting_language, validate_scouting_language
from src.scouting.tactical_profile import build_tactical_profile


def generate_scouting_v2(
    match_id_a: int,
    player_id_a: int,
    match_id_b: int | None = None,
    player_id_b: int | None = None,
) -> dict[str, Any]:
    has_player_b = match_id_b is not None and player_id_b is not None
    profile_a = build_tactical_profile(match_id_a, player_id_a)
    profile_b = build_tactical_profile(int(match_id_b), int(player_id_b)) if has_player_b else None
    mode = "comparativo" if has_player_b else "individual"
    comparison = _compare_profiles(profile_a, profile_b) if profile_b else None
    narrative = _build_narrative(profile_a, profile_b, comparison)
    language_warnings = validate_scouting_language(narrative)
    clean_narrative = sanitize_scouting_language(narrative)
    if clean_narrative != narrative:
        language_warnings.append("Se ajustó lenguaje no profesional antes de entregar el reporte.")
    narrative = clean_narrative
    residual_language_warnings = validate_scouting_language(narrative)
    language_warnings.extend(
        warning for warning in residual_language_warnings if warning not in language_warnings
    )

    warnings = list(profile_a.get("warnings", []))
    if profile_b:
        warnings.extend(profile_b.get("warnings", []))
        if profile_a.get("position_name") and profile_b.get("position_name") and profile_a.get("position_name") != profile_b.get("position_name"):
            warnings.append(
                f"Roles observados distintos: {profile_a.get('position_name')} vs {profile_b.get('position_name')}; la comparación debe leerse con cautela."
            )

    result = {
        "version": "scouting_ai_v2",
        "mode": mode,
        "match_id_a": match_id_a,
        "player_id_a": player_id_a,
        "match_id_b": match_id_b,
        "player_id_b": player_id_b,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "status": "generated",
        "model": "local-tactical-profile-v2",
        "profile_a": profile_a,
        "profile_b": profile_b,
        "comparison": comparison,
        "radar_metrics": _radar_metrics(profile_a, profile_b),
        "narrative_markdown": narrative,
        "warnings": warnings,
        "language_warnings": language_warnings,
        "context_summary": _context_summary(profile_a, profile_b),
    }
    return to_jsonable(result)


def _build_narrative(
    profile_a: dict[str, Any],
    profile_b: dict[str, Any] | None,
    comparison: dict[str, Any] | None,
) -> str:
    player_name = profile_a.get("player_name")
    primary = profile_a.get("primary_archetype", {})
    secondary = profile_a.get("secondary_archetype", {})
    strengths = _list_text(profile_a.get("strengths", []))
    weaknesses = _list_text(profile_a.get("weaknesses", []))

    comparison_section = ""
    if profile_b and comparison:
        comparison_section = f"""
## Comparación de arquetipos

**Similitudes:**

{_list_text(comparison.get('similarities', []))}

**Diferencias:**

{_list_text(comparison.get('differences', []))}

**Complementariedad:**

{_list_text(comparison.get('complementarity', []))}
"""

    return f"""# Scouting AI v2

## Perfil táctico

{player_name} perfila como **{primary.get('name')}** a partir de métricas observadas en este partido. La lectura no busca adivinar su posición oficial, sino inferir qué comportamientos pesaron más: ataque {profile_a.get('attack_profile', {}).get('label')}, creación {profile_a.get('creation_profile', {}).get('label')}, progresión {profile_a.get('progression_profile', {}).get('label')}, fase defensiva {profile_a.get('defensive_profile', {}).get('label')} e impacto {profile_a.get('impact_profile', {}).get('label')}.

## Arquetipo principal

**{primary.get('name')}** con confianza {primary.get('score')}/100. {primary.get('description')} La señal viene de métricas como {_metric_names(primary)}.

## Arquetipo secundario

**{secondary.get('name')}** con score {secondary.get('score')}/100. Este segundo perfil sugiere una lectura complementaria, no una etiqueta absoluta.

## Fortalezas observadas

{strengths}

## Limitaciones observadas

{weaknesses}

## Uso recomendado

{_recommended_use(profile_a)}

## Riesgos de interpretación

Este perfil se basa en un partido y en eventos disponibles; no proyecta carrera, mercado ni encaje futuro como hecho. Si el rol observado difiere del rol habitual del jugador, la lectura debe validarse con más partidos y video.
{comparison_section}
"""


def _compare_profiles(profile_a: dict[str, Any], profile_b: dict[str, Any]) -> dict[str, Any]:
    primary_a = profile_a.get("primary_archetype", {})
    primary_b = profile_b.get("primary_archetype", {})
    strengths_a = set(profile_a.get("strengths", []))
    strengths_b = set(profile_b.get("strengths", []))
    shared_strengths = sorted(strengths_a & strengths_b)
    similarities = []
    if primary_a.get("name") == primary_b.get("name"):
        similarities.append(f"Ambos se acercan al arquetipo {primary_a.get('name')}.")
    if shared_strengths:
        similarities.append("Comparten señales en: " + ", ".join(shared_strengths) + ".")
    if not similarities:
        similarities.append("No comparten un arquetipo principal claro; la comparación es principalmente de contraste.")

    differences = [
        f"{profile_a.get('player_name')} se acerca a {primary_a.get('name')} ({primary_a.get('score')}/100), mientras {profile_b.get('player_name')} se acerca a {primary_b.get('name')} ({primary_b.get('score')}/100)."
    ]
    for label, key in (
        ("ataque", "attack_profile"),
        ("creación", "creation_profile"),
        ("progresión", "progression_profile"),
        ("fase defensiva", "defensive_profile"),
        ("impacto", "impact_profile"),
    ):
        score_a = _number(profile_a.get(key, {}).get("score"))
        score_b = _number(profile_b.get(key, {}).get("score"))
        if abs(score_a - score_b) >= 15:
            leader = profile_a.get("player_name") if score_a > score_b else profile_b.get("player_name")
            differences.append(f"Mayor señal de {label}: {leader}.")

    complementarity = []
    if profile_a.get("archetype") != profile_b.get("archetype"):
        complementarity.append("Perfiles distintos: pueden ser más útiles como roles complementarios que como ranking directo.")
    attack_a = _number(profile_a.get("attack_profile", {}).get("score"))
    attack_b = _number(profile_b.get("attack_profile", {}).get("score"))
    organization_a = max(
        _number(profile_a.get("creation_profile", {}).get("score")),
        _number(profile_a.get("progression_profile", {}).get("score")),
    )
    organization_b = max(
        _number(profile_b.get("creation_profile", {}).get("score")),
        _number(profile_b.get("progression_profile", {}).get("score")),
    )
    if attack_a >= attack_b + 15 and organization_b >= organization_a + 15:
        complementarity.append(
            f"{profile_a.get('player_name')} aporta mayor amenaza ofensiva, mientras {profile_b.get('player_name')} aporta más organización o progresión."
        )
    elif attack_b >= attack_a + 15 and organization_a >= organization_b + 15:
        complementarity.append(
            f"{profile_b.get('player_name')} aporta mayor amenaza ofensiva, mientras {profile_a.get('player_name')} aporta más organización o progresión."
        )
    if not complementarity:
        complementarity.append("La complementariedad debe validarse con contexto táctico y roles de equipo.")

    return {
        "similarities": similarities,
        "differences": differences,
        "complementarity": complementarity,
    }


def _radar_metrics(profile_a: dict[str, Any], profile_b: dict[str, Any] | None) -> dict[str, Any]:
    categories = ["Ataque", "Creación", "Progresión", "Defensa", "Impacto"]
    values_a = [
        profile_a.get("attack_profile", {}).get("score", 0),
        profile_a.get("creation_profile", {}).get("score", 0),
        profile_a.get("progression_profile", {}).get("score", 0),
        profile_a.get("defensive_profile", {}).get("score", 0),
        profile_a.get("impact_profile", {}).get("score", 0),
    ]
    values_b = [0, 0, 0, 0, 0]
    if profile_b:
        values_b = [
            profile_b.get("attack_profile", {}).get("score", 0),
            profile_b.get("creation_profile", {}).get("score", 0),
            profile_b.get("progression_profile", {}).get("score", 0),
            profile_b.get("defensive_profile", {}).get("score", 0),
            profile_b.get("impact_profile", {}).get("score", 0),
        ]
    return {
        "categories": categories,
        "player_a": {
            "name": profile_a.get("player_name"),
            "team_name": profile_a.get("team_name"),
            "values": values_a,
            "raw": _profile_scores(profile_a),
        },
        "player_b": {
            "name": profile_b.get("player_name") if profile_b else None,
            "team_name": profile_b.get("team_name") if profile_b else None,
            "values": values_b,
            "raw": _profile_scores(profile_b) if profile_b else {},
        },
    }


def _profile_scores(profile: dict[str, Any] | None) -> dict[str, Any]:
    if not profile:
        return {}
    return {
        "Ataque": profile.get("attack_profile", {}).get("score", 0),
        "Creación": profile.get("creation_profile", {}).get("score", 0),
        "Progresión": profile.get("progression_profile", {}).get("score", 0),
        "Defensa": profile.get("defensive_profile", {}).get("score", 0),
        "Impacto": profile.get("impact_profile", {}).get("score", 0),
    }


def _recommended_use(profile: dict[str, Any]) -> str:
    archetype = str(profile.get("archetype") or "")
    name = profile.get("player_name")
    if "Extremo" in archetype:
        return f"Usar a {name} para atacar espacios, acelerar tras recuperación y recibir en zonas donde pueda conducir o finalizar."
    if archetype in {"Segundo delantero", "Finalizador", "Delantero objetivo"}:
        return f"Usar a {name} cerca de zonas de definición, con libertad para atacar intervalos y convertir ventajas en remate."
    if archetype in {"Organizador", "Mediocentro constructor"}:
        return f"Usar a {name} como pieza de continuidad: recibir, progresar y conectar fases con volumen de pase."
    if "Recuperador" in archetype or "destructor" in archetype:
        return f"Usar a {name} para activar presión, sostener duelos y proteger zonas de pérdida."
    if "Lateral" in archetype:
        return f"Usar a {name} con responsabilidades de amplitud, progresión y apoyo en campo rival, cuidando el balance defensivo."
    if "Central" in archetype:
        return f"Usar a {name} para sostener salida o defensa de área según la señal dominante del perfil."
    return f"Usar a {name} según el arquetipo observado, validando con más partidos antes de tomar decisiones de mayor alcance."


def _context_summary(profile_a: dict[str, Any], profile_b: dict[str, Any] | None) -> dict[str, Any]:
    return {
        "player_a": profile_a.get("player_name"),
        "team_a": profile_a.get("team_name"),
        "archetype_a": profile_a.get("archetype"),
        "confidence_a": profile_a.get("confidence"),
        "player_b": profile_b.get("player_name") if profile_b else None,
        "team_b": profile_b.get("team_name") if profile_b else None,
        "archetype_b": profile_b.get("archetype") if profile_b else None,
        "confidence_b": profile_b.get("confidence") if profile_b else None,
    }


def _metric_names(archetype: dict[str, Any]) -> str:
    metrics = archetype.get("metrics", [])
    labels = {
        "xg": "xG",
        "shots": "tiros",
        "goals": "goles",
        "impact_score": "impacto",
        "key_passes": "pases clave",
        "passes": "pases",
        "progressive_passes": "pases progresivos",
        "pass_accuracy_pct": "precisión de pase",
        "events": "volumen de eventos",
        "pressures": "presiones",
        "duels": "duelos",
        "carries": "conducciones",
        "carry_distance": "distancia en conducción",
    }
    return ", ".join(labels.get(metric, str(metric)) for metric in metrics) or "métricas observadas"


def _list_text(values: list[Any]) -> str:
    if not values:
        return "No hay señales dominantes suficientes; conviene ampliar muestra."
    return "\n".join(f"- {value}" for value in values)


def _number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0
