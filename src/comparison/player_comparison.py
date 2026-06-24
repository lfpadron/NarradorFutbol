"""Compare two players within one match or across different matches."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.analytics.advanced_metrics import get_impact_players
from src.analytics.db import query_one, query_records
from src.analytics.key_moments import get_key_moments
from src.analytics.match_summary import get_match_summary
from src.analytics.player_stats import get_player_stats
from src.ingestion.utils import to_jsonable


def list_players_for_match(match_id: int) -> list[dict[str, Any]]:
    """Return players available for a transformed match."""

    rows = query_records(
        """
        SELECT
            player_id,
            MAX(player_name) AS player_name,
            MAX(team_name) AS team_name,
            COUNT(*) AS events,
            NULL AS minutes
        FROM event
        WHERE match_id = ?
          AND player_id IS NOT NULL
        GROUP BY player_id
        ORDER BY events DESC, player_name
        """,
        (match_id,),
    )
    return to_jsonable(rows)


def compare_players(
    match_id_a: int,
    player_id_a: int,
    match_id_b: int,
    player_id_b: int,
) -> dict[str, Any]:
    """Compare two players using match-level and event-level analytics."""

    match_a = get_match_summary(match_id_a)
    match_b = get_match_summary(match_id_b)
    player_a = _player_snapshot(match_id_a, player_id_a, "A")
    player_b = _player_snapshot(match_id_b, player_id_b, "B")
    warnings = _warnings(player_a, player_b, match_id_a, match_id_b, player_id_a, player_id_b)

    return to_jsonable(
        {
            "mode": "player_comparison",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "player_a": player_a,
            "player_b": player_b,
            "match_a": _match_snapshot("A", match_a),
            "match_b": _match_snapshot("B", match_b),
            "summary_comparison": _summary_comparison(player_a, player_b),
            "attacking_comparison": _attacking_comparison(player_a, player_b),
            "passing_comparison": _passing_comparison(player_a, player_b),
            "defensive_comparison": _defensive_comparison(player_a, player_b),
            "impact_comparison": _impact_comparison(player_a, player_b),
            "key_moments_comparison": _key_moments_comparison(player_a, player_b),
            "warnings": warnings,
        }
    )


def build_player_radar_metrics(comparison: dict[str, Any]) -> dict[str, Any]:
    """Build 0-100 radar metrics for two compared players."""

    player_a = comparison.get("player_a", {})
    player_b = comparison.get("player_b", {})
    raw_a = _radar_raw_scores(player_a)
    raw_b = _radar_raw_scores(player_b)
    categories = ["Ataque", "Creación", "Pase", "Progresión", "Presión", "Duelos", "Impacto"]
    values_a = []
    values_b = []
    for category in categories:
        score_a = _number(raw_a.get(category))
        score_b = _number(raw_b.get(category))
        max_score = max(score_a, score_b)
        if max_score <= 0:
            values_a.append(0)
            values_b.append(0)
        else:
            values_a.append(round(100.0 * score_a / max_score, 1))
            values_b.append(round(100.0 * score_b / max_score, 1))

    return to_jsonable(
        {
            "categories": categories,
            "player_a": {
                "name": player_a.get("player_name"),
                "team_name": player_a.get("team_name"),
                "values": values_a,
                "raw": raw_a,
            },
            "player_b": {
                "name": player_b.get("player_name"),
                "team_name": player_b.get("team_name"),
                "values": values_b,
                "raw": raw_b,
            },
        }
    )


def _player_snapshot(match_id: int, player_id: int, label: str) -> dict[str, Any]:
    stats = _find_player_stats(match_id, player_id)
    if stats is None:
        raise ValueError(f"player_id={player_id} no existe en match_id={match_id}.")

    extra = _extra_player_metrics(match_id, player_id)
    impact = _find_impact_player(match_id, player_id)
    key_moments = _player_key_moments(match_id, stats.get("player_name"))
    passes = _number(stats.get("passes"))
    successful = _number(stats.get("successful_passes"))
    pass_accuracy = round(100.0 * successful / passes, 2) if passes else None

    return {
        "label": label,
        "match_id": match_id,
        "player_id": int(player_id),
        "player_name": stats.get("player_name"),
        "team_id": stats.get("team_id"),
        "team_name": stats.get("team_name"),
        "events": _int(stats.get("events")),
        "shots": _int(stats.get("shots")),
        "goals": _round(stats.get("goals")),
        "xg": _round(stats.get("xg")),
        "assists": _int(stats.get("assists")),
        "key_passes": _int(stats.get("key_passes")),
        "passes": _int(stats.get("passes")),
        "successful_passes": _int(stats.get("successful_passes")),
        "pass_accuracy_pct": pass_accuracy,
        "progressive_passes": _int(extra.get("progressive_passes")),
        "carries": _int(stats.get("carries")),
        "carry_distance": _round(extra.get("carry_distance")),
        "duels": _int(stats.get("duels")),
        "pressures": _int(stats.get("pressures")),
        "counterpressures": _int(extra.get("counterpressures")),
        "fouls_committed": _int(stats.get("fouls_committed")),
        "fouls_won": _int(stats.get("fouls_won")),
        "impact_score": _round((impact or {}).get("impact_score")),
        "impact_available": impact is not None,
        "key_moments": key_moments,
        "key_moments_count": len(key_moments),
        "position_name": extra.get("position_name"),
    }


def _radar_raw_scores(player: dict[str, Any]) -> dict[str, float]:
    impact_score = _number(player.get("impact_score"))
    fallback_impact = (
        _number(player.get("goals")) * 8
        + _number(player.get("assists")) * 6
        + _number(player.get("key_passes")) * 3
        + _number(player.get("shots")) * 1.5
        + _number(player.get("xg")) * 5
        + _number(player.get("progressive_passes")) * 2
        + _number(player.get("pressures")) * 0.4
    )
    return {
        "Ataque": (
            _number(player.get("goals")) * 8
            + _number(player.get("shots")) * 2
            + _number(player.get("xg")) * 10
        ),
        "Creación": (
            _number(player.get("assists")) * 8
            + _number(player.get("key_passes")) * 3
        ),
        "Pase": (
            _number(player.get("successful_passes")) * 0.35
            + _number(player.get("pass_accuracy_pct")) * 0.65
        ),
        "Progresión": (
            _number(player.get("progressive_passes")) * 4
            + _number(player.get("carries")) * 0.8
        ),
        "Presión": _number(player.get("pressures")),
        "Duelos": _number(player.get("duels")),
        "Impacto": impact_score if impact_score else fallback_impact,
    }


def _find_player_stats(match_id: int, player_id: int) -> dict[str, Any] | None:
    for row in get_player_stats(match_id):
        if int(row.get("player_id") or -1) == int(player_id):
            return row
    return None


def _find_impact_player(match_id: int, player_id: int) -> dict[str, Any] | None:
    for row in get_impact_players(match_id, limit=50):
        if int(row.get("player_id") or -1) == int(player_id):
            return row
    return None


def _extra_player_metrics(match_id: int, player_id: int) -> dict[str, Any]:
    return query_one(
        """
        WITH base_events AS (
            SELECT *
            FROM event
            WHERE match_id = ?
              AND player_id = ?
        ),
        progressive AS (
            SELECT COUNT(*) AS progressive_passes
            FROM base_events e
            INNER JOIN "pass" p ON p.event_id = e.event_id
            WHERE e.location_x IS NOT NULL
              AND p.pass_end_x IS NOT NULL
              AND p.pass_outcome_name IS NULL
              AND e.location_x < 80
              AND p.pass_end_x >= 80
        ),
        carries AS (
            SELECT SUM(COALESCE(c.carry_distance, 0)) AS carry_distance
            FROM base_events e
            INNER JOIN carry c ON c.event_id = e.event_id
        ),
        pressures AS (
            SELECT SUM(CASE WHEN p.counterpress THEN 1 ELSE 0 END) AS counterpressures
            FROM base_events e
            INNER JOIN pressure p ON p.event_id = e.event_id
        ),
        position AS (
            SELECT position_name, COUNT(*) AS rows
            FROM base_events
            WHERE position_name IS NOT NULL
            GROUP BY position_name
            ORDER BY rows DESC, position_name
            LIMIT 1
        )
        SELECT
            COALESCE((SELECT progressive_passes FROM progressive), 0) AS progressive_passes,
            COALESCE((SELECT carry_distance FROM carries), 0) AS carry_distance,
            COALESCE((SELECT counterpressures FROM pressures), 0) AS counterpressures,
            (SELECT position_name FROM position) AS position_name
        """,
        (match_id, player_id),
    ) or {}


def _player_key_moments(match_id: int, player_name: Any) -> list[dict[str, Any]]:
    if not player_name:
        return []
    return [
        moment
        for moment in get_key_moments(match_id)
        if moment.get("player_name") == player_name
    ]


def _match_snapshot(label: str, summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "label": label,
        "match_id": summary.get("match_id"),
        "match_date": summary.get("match_date"),
        "home_team_name": summary.get("home_team_name"),
        "away_team_name": summary.get("away_team_name"),
        "home_score": summary.get("home_score"),
        "away_score": summary.get("away_score"),
        "scoreline": (
            f"{summary.get('home_team_name')} {summary.get('home_score')}-"
            f"{summary.get('away_score')} {summary.get('away_team_name')}"
        ),
    }


def _summary_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "same_match": a.get("match_id") == b.get("match_id"),
        "same_player": a.get("player_id") == b.get("player_id"),
        "same_team": a.get("team_name") == b.get("team_name"),
        "role_warning": _role_warning(a, b),
        "diff_goals": _diff(a, b, "goals"),
        "diff_xg": _diff(a, b, "xg"),
        "diff_shots": _diff(a, b, "shots"),
        "diff_assists": _diff(a, b, "assists"),
        "diff_key_passes": _diff(a, b, "key_passes"),
        "diff_pressures": _diff(a, b, "pressures"),
        "diff_impact_score": _diff(a, b, "impact_score"),
    }


def _attacking_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "shots": _values(a, b, "shots"),
        "goals": _values(a, b, "goals"),
        "xg": _values(a, b, "xg"),
        "carries": _values(a, b, "carries"),
        "carry_distance": _values(a, b, "carry_distance"),
    }


def _passing_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "passes": _values(a, b, "passes"),
        "successful_passes": _values(a, b, "successful_passes"),
        "pass_accuracy_pct": _values(a, b, "pass_accuracy_pct"),
        "assists": _values(a, b, "assists"),
        "key_passes": _values(a, b, "key_passes"),
        "progressive_passes": _values(a, b, "progressive_passes"),
    }


def _defensive_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "duels": _values(a, b, "duels"),
        "pressures": _values(a, b, "pressures"),
        "counterpressures": _values(a, b, "counterpressures"),
        "fouls_committed": _values(a, b, "fouls_committed"),
        "fouls_won": _values(a, b, "fouls_won"),
    }


def _impact_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "events": _values(a, b, "events"),
        "impact_score": _values(a, b, "impact_score"),
        "impact_available_a": a.get("impact_available"),
        "impact_available_b": b.get("impact_available"),
        "key_moments_count": _values(a, b, "key_moments_count"),
    }


def _key_moments_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "count": _values(a, b, "key_moments_count"),
        "rows_a": a.get("key_moments", []),
        "rows_b": b.get("key_moments", []),
    }


def _warnings(
    a: dict[str, Any],
    b: dict[str, Any],
    match_id_a: int,
    match_id_b: int,
    player_id_a: int,
    player_id_b: int,
) -> list[str]:
    warnings = []
    if match_id_a == match_id_b:
        warnings.append("Comparación dentro del mismo partido.")
    if player_id_a == player_id_b and match_id_a != match_id_b:
        warnings.append("Mismo player_id en partidos distintos; útil para comparar rendimiento entre contextos.")
    role_warning = _role_warning(a, b)
    if role_warning:
        warnings.append(role_warning)
    if not a.get("impact_available"):
        warnings.append("Jugador A no aparece en el ranking de impacto; impact_score puede ser 0.")
    if not b.get("impact_available"):
        warnings.append("Jugador B no aparece en el ranking de impacto; impact_score puede ser 0.")
    return warnings


def _role_warning(a: dict[str, Any], b: dict[str, Any]) -> str | None:
    role_a = a.get("position_name")
    role_b = b.get("position_name")
    if role_a and role_b and role_a != role_b:
        return f"Roles distintos detectados: Jugador A ({role_a}) vs Jugador B ({role_b}); leer la comparación con cuidado."
    return None


def _values(a: dict[str, Any], b: dict[str, Any], key: str) -> dict[str, Any]:
    value_a = a.get(key)
    value_b = b.get(key)
    return {
        "player_a": value_a,
        "player_b": value_b,
        "difference_b_minus_a": _round(_number(value_b) - _number(value_a)),
        "higher_player": _higher_label(value_a, value_b),
    }


def _diff(a: dict[str, Any], b: dict[str, Any], key: str) -> float:
    return _round(_number(b.get(key)) - _number(a.get(key)))


def _higher_label(value_a: Any, value_b: Any) -> str:
    number_a = _number(value_a)
    number_b = _number(value_b)
    if number_a > number_b:
        return "A"
    if number_b > number_a:
        return "B"
    return "Empate"


def _number(value: Any) -> float:
    if value is None or value == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _int(value: Any) -> int:
    return int(round(_number(value)))


def _round(value: Any, digits: int = 3) -> float:
    return round(_number(value), digits)
