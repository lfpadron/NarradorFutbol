"""Generic match validation that works without curated expectations."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Callable

from src.analytics.ai_context import build_ai_match_context
from src.analytics.db import AnalyticsDatabaseError, query_one
from src.benchmark.generic_narrative_checks import validate_narratives_for_any_match
from src.ingestion.utils import to_jsonable
from src.reports.report_builder import build_match_report

Check = dict[str, Any]


def validate_any_match(match_id: int, use_api: bool = False) -> dict[str, Any]:
    checks: list[Check] = []
    warnings: list[str] = []
    summary = _load_summary(match_id)
    checks.append(check_match_exists(match_id, summary))

    if summary is None:
        return to_jsonable(
            {
                "match_id": match_id,
                "mode": "generic_validation",
                "status": "FAIL",
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "checks": checks,
                "summary": {},
                "narrative_basic": {},
                "narrative_v2": {},
                "warnings": ["No se encontró el partido en DuckDB analítico."],
            }
        )

    context: dict[str, Any] = {}
    try:
        context = build_ai_match_context(match_id)
    except Exception as exc:
        checks.append(
            _check_result(
                "build_ai_context",
                "FAIL",
                "No se pudo construir el contexto analítico.",
                {"error": str(exc)},
            )
        )

    for check in (
        check_has_events,
        check_teams_and_score,
        check_goals_vs_score,
        check_xg_valid,
        check_shots_valid,
        check_coordinates,
        check_players,
    ):
        checks.append(_safe_check(check, match_id, summary, context))

    checks.append(_safe_check(check_dominance, match_id, summary, context))
    checks.append(_safe_check(check_report_generation, match_id, summary, context, use_api))

    narrative_result: dict[str, Any] = {"basic": {}, "v2": {}}
    try:
        narrative_result = validate_narratives_for_any_match(match_id, use_api=use_api)
        checks.extend(_narrative_checks(narrative_result))
    except Exception as exc:
        checks.append(
            _check_result(
                "generic_narrative_validation",
                "FAIL",
                "No se pudieron validar las narrativas.",
                {"error": str(exc)},
            )
        )

    warnings = [f"{check['check_name']}: {check['message']}" for check in checks if check.get("status") != "PASS"]

    return to_jsonable(
        {
            "match_id": match_id,
            "mode": "generic_validation",
            "status": _overall_status(checks),
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "checks": checks,
            "summary": _validation_summary(summary),
            "narrative_basic": narrative_result.get("basic", {}),
            "narrative_v2": narrative_result.get("v2", {}),
            "warnings": warnings,
        }
    )


def check_match_exists(match_id: int, summary: dict[str, Any] | None) -> Check:
    return _check_result(
        "check_match_exists",
        "PASS" if summary else "FAIL",
        "El partido existe en DuckDB analítico." if summary else "El partido no existe en DuckDB analítico.",
        {"match_id": match_id},
    )


def check_has_events(match_id: int, summary: dict[str, Any], context: dict[str, Any]) -> Check:
    total_events = int(summary.get("total_events") or 0)
    if total_events == 0:
        status = "FAIL"
        message = "El partido no tiene eventos transformados."
    elif total_events < 100:
        status = "WARNING"
        message = "El partido tiene pocos eventos; podría estar incompleto."
    else:
        status = "PASS"
        message = "El partido tiene eventos suficientes."
    return _check_result("check_has_events", status, message, {"total_events": total_events})


def check_teams_and_score(match_id: int, summary: dict[str, Any], context: dict[str, Any]) -> Check:
    missing = []
    for key in ("home_team_name", "away_team_name", "home_score", "away_score"):
        if summary.get(key) is None or summary.get(key) == "":
            missing.append(key)
    status = "PASS" if not missing else "FAIL"
    return _check_result(
        "check_teams_and_score",
        status,
        "Equipos y marcador disponibles." if status == "PASS" else "Faltan equipos o marcador.",
        {"missing": missing},
    )


def check_goals_vs_score(match_id: int, summary: dict[str, Any], context: dict[str, Any]) -> Check:
    score_goals = int(summary.get("home_score") or 0) + int(summary.get("away_score") or 0)
    detected_goals = int(summary.get("total_goals") or 0)
    diff = abs(score_goals - detected_goals)
    if diff == 0:
        status = "PASS"
        message = "Los goles detectados coinciden con el marcador."
    elif diff <= 1:
        status = "WARNING"
        message = "Los goles detectados difieren ligeramente del marcador; revisar datos incompletos u autogoles."
    else:
        status = "FAIL"
        message = "Contradicción fuerte entre marcador y eventos de gol."
    return _check_result(
        "check_goals_vs_score",
        status,
        message,
        {"score_goals": score_goals, "goals_detected": detected_goals, "difference": diff},
    )


def check_xg_valid(match_id: int, summary: dict[str, Any], context: dict[str, Any]) -> Check:
    shot_stats = _query_one_safe(
        """
        SELECT
            COUNT(*) AS shots,
            SUM(CASE WHEN shot_statsbomb_xg < 0 THEN 1 ELSE 0 END) AS negative_xg_rows,
            SUM(COALESCE(shot_statsbomb_xg, 0)) AS total_xg
        FROM shot
        WHERE match_id = ?
        """,
        (match_id,),
    )
    shots = int(shot_stats.get("shots") or 0)
    negative_rows = int(shot_stats.get("negative_xg_rows") or 0)
    total_xg = float(shot_stats.get("total_xg") or 0)
    if negative_rows > 0:
        status = "FAIL"
        message = "Hay valores de xG negativos."
    elif shots > 0 and total_xg == 0:
        status = "WARNING"
        message = "Hay tiros, pero el xG total es cero."
    else:
        status = "PASS"
        message = "El xG es válido."
    return _check_result(
        "check_xg_valid",
        status,
        message,
        {"shots": shots, "negative_xg_rows": negative_rows, "total_xg": total_xg},
    )


def check_shots_valid(match_id: int, summary: dict[str, Any], context: dict[str, Any]) -> Check:
    shots = int(summary.get("total_shots") or 0)
    status = "PASS" if shots > 0 else "WARNING"
    return _check_result(
        "check_shots_valid",
        status,
        "El partido tiene tiros registrados." if shots > 0 else "El partido no tiene tiros registrados.",
        {"shots": shots},
    )


def check_coordinates(match_id: int, summary: dict[str, Any], context: dict[str, Any]) -> Check:
    stats = _query_one_safe(
        """
        SELECT
            SUM(CASE WHEN location_x IS NOT NULL AND (location_x < 0 OR location_x > 120) THEN 1 ELSE 0 END) AS invalid_x,
            SUM(CASE WHEN location_y IS NOT NULL AND (location_y < 0 OR location_y > 80) THEN 1 ELSE 0 END) AS invalid_y,
            SUM(CASE WHEN location_x IS NULL OR location_y IS NULL THEN 1 ELSE 0 END) AS null_locations,
            COUNT(*) AS total_events
        FROM event
        WHERE match_id = ?
        """,
        (match_id,),
    )
    invalid = int(stats.get("invalid_x") or 0) + int(stats.get("invalid_y") or 0)
    status = "WARNING" if invalid else "PASS"
    return _check_result(
        "check_coordinates",
        status,
        "Coordenadas dentro del rango StatsBomb 120x80." if not invalid else "Hay coordenadas fuera de rango.",
        stats,
    )


def check_players(match_id: int, summary: dict[str, Any], context: dict[str, Any]) -> Check:
    stats = _query_one_safe(
        """
        SELECT
            COUNT(*) AS total_events,
            SUM(CASE WHEN player_id IS NULL THEN 1 ELSE 0 END) AS null_player_events,
            SUM(CASE WHEN player_id IS NOT NULL AND (player_name IS NULL OR player_name = '') THEN 1 ELSE 0 END) AS unnamed_player_events
        FROM event
        WHERE match_id = ?
        """,
        (match_id,),
    )
    total = int(stats.get("total_events") or 0)
    null_player_events = int(stats.get("null_player_events") or 0)
    unnamed = int(stats.get("unnamed_player_events") or 0)
    null_ratio = (null_player_events / total) if total else 1
    missing_relevant_names = [row for row in context.get("impact_players", []) if not row.get("player_name")]
    if unnamed or missing_relevant_names:
        status = "WARNING"
        message = "Hay jugadores relevantes o eventos con jugador sin nombre."
    elif null_ratio > 0.45:
        status = "WARNING"
        message = "Muchos eventos no tienen player_id; revisar tipo de datos del partido."
    else:
        status = "PASS"
        message = "Los datos de jugadores son razonables."
    return _check_result(
        "check_players",
        status,
        message,
        {
            "total_events": total,
            "null_player_events": null_player_events,
            "null_player_ratio": round(null_ratio, 4),
            "unnamed_player_events": unnamed,
            "missing_relevant_names": len(missing_relevant_names),
        },
    )


def check_dominance(match_id: int, summary: dict[str, Any], context: dict[str, Any]) -> Check:
    dominance = context.get("dominance", [])
    status = "PASS" if dominance else "WARNING"
    return _check_result(
        "check_dominance",
        status,
        "Se calculó dominio del partido." if dominance else "No se pudo calcular dominio del partido.",
        {"teams": [row.get("team_name") for row in dominance]},
    )


def check_report_generation(match_id: int, summary: dict[str, Any], context: dict[str, Any], use_api: bool) -> Check:
    report = build_match_report(match_id, use_api=use_api)
    status = "PASS" if report.get("match_id") == match_id else "FAIL"
    return _check_result(
        "check_report_generation",
        status,
        "El reporte se generó en memoria." if status == "PASS" else "El reporte generado no coincide con el partido.",
        {"match_id": report.get("match_id"), "warnings_count": len(report.get("warnings", []))},
    )


def _narrative_checks(narrative_result: dict[str, Any]) -> list[Check]:
    basic = narrative_result.get("basic", {})
    v2 = narrative_result.get("v2", {})
    basic_fact_warnings = basic.get("fact_warnings", [])
    basic_quality = basic.get("quality", {})
    v2_fact_warnings_total = int(v2.get("fact_warnings_total") or 0)
    v2_styles_checked = int(v2.get("styles_checked") or 0)
    return [
        _check_result(
            "check_basic_narrative",
            "PASS" if not basic_fact_warnings and int(basic_quality.get("overall_score") or 0) >= 70 else "WARNING",
            (
                "La narrativa básica respeta marcador y equipos."
                if not basic_fact_warnings
                else "La narrativa básica tiene advertencias factuales."
            ),
            {
                "fact_warnings": basic_fact_warnings,
                "quality_overall_score": basic_quality.get("overall_score"),
            },
        ),
        _check_result(
            "check_v2_narrative",
            "PASS" if v2_styles_checked and v2_fact_warnings_total == 0 else "WARNING",
            (
                "Narrador AI v2 respeta marcador y equipos."
                if v2_fact_warnings_total == 0
                else "Narrador AI v2 tiene advertencias factuales."
            ),
            {
                "styles_checked": v2_styles_checked,
                "fact_warnings_total": v2_fact_warnings_total,
                "best_style": v2.get("best_style"),
            },
        ),
    ]


def _load_summary(match_id: int) -> dict[str, Any] | None:
    return query_one(
        """
        SELECT *
        FROM vw_match_summary
        WHERE match_id = ?
        """,
        (match_id,),
    )


def _validation_summary(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "home_team": summary.get("home_team_name"),
        "away_team": summary.get("away_team_name"),
        "home_score": summary.get("home_score"),
        "away_score": summary.get("away_score"),
        "events": summary.get("total_events"),
        "shots": summary.get("total_shots"),
        "goals_detected": summary.get("total_goals"),
        "total_xg": summary.get("total_xg"),
    }


def _safe_check(
    check: Callable[..., Check],
    match_id: int,
    summary: dict[str, Any],
    context: dict[str, Any],
    *extra: Any,
) -> Check:
    try:
        return check(match_id, summary, context, *extra)
    except Exception as exc:
        return _check_result(
            check.__name__,
            "FAIL",
            "El check no pudo ejecutarse.",
            {"error": str(exc)},
        )


def _query_one_safe(sql: str, params: tuple[Any, ...]) -> dict[str, Any]:
    try:
        return query_one(sql, params) or {}
    except AnalyticsDatabaseError as exc:
        return {"error": str(exc)}


def _check_result(check_name: str, status: str, message: str, details: dict[str, Any]) -> Check:
    return {
        "check_name": check_name,
        "status": status,
        "message": message,
        "details": details,
    }


def _overall_status(checks: list[Check]) -> str:
    statuses = {check.get("status") for check in checks}
    if "FAIL" in statuses:
        return "FAIL"
    if "WARNING" in statuses:
        return "WARNING"
    return "PASS"
