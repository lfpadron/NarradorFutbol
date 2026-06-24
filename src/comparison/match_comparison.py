"""Compare two transformed matches using the analytical context."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.analytics.ai_context import build_ai_match_context
from src.ingestion.utils import to_jsonable


def compare_matches(match_id_a: int, match_id_b: int) -> dict[str, Any]:
    """Build a robust analytical comparison between two transformed matches."""

    warnings: list[str] = []
    if match_id_a == match_id_b:
        warnings.append("Partido A y Partido B usan el mismo match_id.")

    context_a = build_ai_match_context(match_id_a)
    context_b = build_ai_match_context(match_id_b)
    metrics_a = _extract_metrics("A", context_a)
    metrics_b = _extract_metrics("B", context_b)

    warnings.extend(_context_warnings("A", context_a))
    warnings.extend(_context_warnings("B", context_b))

    return to_jsonable(
        {
            "mode": "match_comparison",
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "match_a": metrics_a["match"],
            "match_b": metrics_b["match"],
            "summary_comparison": _summary_comparison(metrics_a, metrics_b),
            "team_stats_comparison": _team_stats_comparison(metrics_a, metrics_b),
            "shot_comparison": _metric_comparison(metrics_a, metrics_b, "shots"),
            "xg_comparison": _metric_comparison(metrics_a, metrics_b, "xg"),
            "pass_comparison": _pass_comparison(metrics_a, metrics_b),
            "possession_comparison": _possession_comparison(metrics_a, metrics_b),
            "dominance_comparison": _dominance_comparison(metrics_a, metrics_b),
            "momentum_comparison": _momentum_comparison(metrics_a, metrics_b),
            "dangerous_attacks_comparison": _metric_comparison(metrics_a, metrics_b, "dangerous_attacks"),
            "impact_players_comparison": _impact_players_comparison(metrics_a, metrics_b),
            "key_moments_comparison": _key_moments_comparison(metrics_a, metrics_b),
            "warnings": warnings,
        }
    )


def _extract_metrics(label: str, context: dict[str, Any]) -> dict[str, Any]:
    summary = context.get("match_summary", {}) or {}
    shot_summary = context.get("shot_summary", {}) or {}
    pass_summary = context.get("pass_summary", {}) or {}
    possession_summary = context.get("possession_summary", {}) or {}
    dominance = list(context.get("dominance", []) or [])
    dangerous_attacks = list(context.get("dangerous_attacks", []) or [])
    impact_players = list(context.get("impact_players", []) or [])
    top_players = list(context.get("top_players", []) or [])
    key_moments = list(context.get("key_moments", []) or [])
    momentum = list(context.get("momentum", []) or [])
    team_stats = list(context.get("team_stats", []) or [])
    xg_breakdown = list(context.get("xg_breakdown", []) or [])

    shots = _number(summary.get("total_shots"), shot_summary.get("total_shots"))
    goals = _number(_score_goals(summary), summary.get("total_goals"))
    xg = _number(summary.get("total_xg"), shot_summary.get("total_xg"), _sum_rows(xg_breakdown, "xg_total"))
    passes = _number(summary.get("total_passes"), pass_summary.get("total_passes"))
    total_events = _number(summary.get("total_events"))
    dangerous_count = len(dangerous_attacks)

    return {
        "label": label,
        "match": _match_snapshot(label, summary, shots, goals, xg, passes, total_events, dangerous_count),
        "summary": summary,
        "team_stats": team_stats,
        "shots": {
            "total": shots,
            "goals": goals,
            "best_chance": shot_summary.get("best_chance"),
        },
        "xg": {
            "total": _round(xg),
            "by_team": _rows_by_team(xg_breakdown, "xg_total"),
        },
        "passes": {
            "total": passes,
            "successful": _number(pass_summary.get("successful_passes")),
            "completion_pct": pass_summary.get("pass_completion_pct"),
            "assists": _number(pass_summary.get("assists")),
            "key_passes": _number(pass_summary.get("key_passes")),
            "by_team": pass_summary.get("passes_by_team", {}),
            "completion_by_team": pass_summary.get("completion_by_team", {}),
        },
        "possession": {
            "total": _number(possession_summary.get("possessions_total")),
            "by_team": possession_summary.get("possessions_by_team", {}),
            "avg_events_per_possession": possession_summary.get("avg_events_per_possession"),
            "ending_in_shot": _number(possession_summary.get("possessions_ending_in_shot")),
            "ending_in_goal": _number(possession_summary.get("possessions_ending_in_goal")),
        },
        "dominance": {
            "leader": _first(dominance),
            "rows": dominance,
        },
        "momentum": _momentum_summary(momentum),
        "dangerous_attacks": {
            "total": dangerous_count,
            "with_shot": sum(1 for row in dangerous_attacks if row.get("has_shot")),
            "with_goal": sum(1 for row in dangerous_attacks if row.get("has_goal")),
            "by_team": _count_by_key(dangerous_attacks, "team_name"),
        },
        "impact_players": {
            "top": _first(impact_players) or _first(top_players),
            "rows": impact_players or top_players,
        },
        "key_moments": {
            "total": len(key_moments),
            "goals": sum(1 for row in key_moments if str(row.get("type") or "").lower() == "goal"),
            "big_chances": sum(1 for row in key_moments if str(row.get("type") or "").lower() == "big_chance"),
            "cards": sum(1 for row in key_moments if "card" in str(row.get("type") or "").lower()),
            "rows": key_moments,
        },
        "intensity": _intensity(total_events, shots),
    }


def _match_snapshot(
    label: str,
    summary: dict[str, Any],
    shots: float,
    goals: float,
    xg: float,
    passes: float,
    total_events: float,
    dangerous_count: int,
) -> dict[str, Any]:
    home = summary.get("home_team_name")
    away = summary.get("away_team_name")
    home_score = summary.get("home_score")
    away_score = summary.get("away_score")
    return {
        "label": label,
        "match_id": summary.get("match_id"),
        "match_date": summary.get("match_date"),
        "competition_id": summary.get("competition_id"),
        "season_id": summary.get("season_id"),
        "home_team_name": home,
        "away_team_name": away,
        "home_score": home_score,
        "away_score": away_score,
        "winner_team_name": summary.get("winner_team_name"),
        "scoreline": _scoreline(summary),
        "total_events": _int(total_events),
        "total_shots": _int(shots),
        "total_goals": _round(goals),
        "total_xg": _round(xg),
        "total_passes": _int(passes),
        "dangerous_attacks": dangerous_count,
    }


def _summary_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "match_a_scoreline": a["match"].get("scoreline"),
        "match_b_scoreline": b["match"].get("scoreline"),
        "winner_a": a["match"].get("winner_team_name"),
        "winner_b": b["match"].get("winner_team_name"),
        "goal_difference": _difference(a["shots"]["goals"], b["shots"]["goals"]),
        "shot_difference": _difference(a["shots"]["total"], b["shots"]["total"]),
        "xg_difference": _difference(a["xg"]["total"], b["xg"]["total"]),
        "pass_difference": _difference(a["passes"]["total"], b["passes"]["total"]),
        "dangerous_attack_difference": _difference(
            a["dangerous_attacks"]["total"],
            b["dangerous_attacks"]["total"],
        ),
        "intensity_a": a["intensity"],
        "intensity_b": b["intensity"],
        "more_intense_match": _winner_label(a["intensity"]["score"], b["intensity"]["score"]),
    }


def _team_stats_comparison(a: dict[str, Any], b: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for side, metrics in (("A", a), ("B", b)):
        for row in metrics.get("team_stats", []):
            clean = dict(row)
            clean["match_label"] = side
            clean["match_id"] = metrics["match"].get("match_id")
            clean["scoreline"] = metrics["match"].get("scoreline")
            rows.append(clean)
    return rows


def _metric_comparison(a: dict[str, Any], b: dict[str, Any], metric: str) -> dict[str, Any]:
    value_a = a[metric]["total"] if isinstance(a.get(metric), dict) else a.get(metric)
    value_b = b[metric]["total"] if isinstance(b.get(metric), dict) else b.get(metric)
    return {
        "match_a": value_a,
        "match_b": value_b,
        "difference_b_minus_a": _round(_number(value_b) - _number(value_a)),
        "higher_match": _winner_label(value_a, value_b),
    }


def _pass_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_passes": _metric_comparison(a, b, "passes"),
        "successful_passes": _values_with_difference(a["passes"]["successful"], b["passes"]["successful"]),
        "completion_pct": _values_with_difference(a["passes"]["completion_pct"], b["passes"]["completion_pct"]),
        "key_passes": _values_with_difference(a["passes"]["key_passes"], b["passes"]["key_passes"]),
        "by_team_a": a["passes"]["by_team"],
        "by_team_b": b["passes"]["by_team"],
    }


def _possession_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_possessions": _values_with_difference(a["possession"]["total"], b["possession"]["total"]),
        "avg_events_per_possession": _values_with_difference(
            a["possession"]["avg_events_per_possession"],
            b["possession"]["avg_events_per_possession"],
        ),
        "possessions_ending_in_shot": _values_with_difference(
            a["possession"]["ending_in_shot"],
            b["possession"]["ending_in_shot"],
        ),
        "by_team_a": a["possession"]["by_team"],
        "by_team_b": b["possession"]["by_team"],
    }


def _dominance_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    leader_a = a["dominance"]["leader"]
    leader_b = b["dominance"]["leader"]
    return {
        "leader_a": _dominance_snapshot(leader_a),
        "leader_b": _dominance_snapshot(leader_b),
        "dominance_score_difference": _values_with_difference(
            leader_a.get("dominance_score"),
            leader_b.get("dominance_score"),
        ),
        "rows_a": a["dominance"]["rows"],
        "rows_b": b["dominance"]["rows"],
    }


def _momentum_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_momentum": _values_with_difference(a["momentum"]["total_score"], b["momentum"]["total_score"]),
        "peak_momentum": _values_with_difference(a["momentum"]["peak_score"], b["momentum"]["peak_score"]),
        "leader_a": a["momentum"]["leader"],
        "leader_b": b["momentum"]["leader"],
        "peak_interval_a": a["momentum"]["peak_interval"],
        "peak_interval_b": b["momentum"]["peak_interval"],
    }


def _impact_players_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "top_player_a": _player_snapshot(a["impact_players"]["top"]),
        "top_player_b": _player_snapshot(b["impact_players"]["top"]),
        "impact_score_difference": _values_with_difference(
            (a["impact_players"]["top"] or {}).get("impact_score"),
            (b["impact_players"]["top"] or {}).get("impact_score"),
        ),
        "rows_a": a["impact_players"]["rows"][:10],
        "rows_b": b["impact_players"]["rows"][:10],
    }


def _key_moments_comparison(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    return {
        "total_key_moments": _values_with_difference(a["key_moments"]["total"], b["key_moments"]["total"]),
        "goals": _values_with_difference(a["key_moments"]["goals"], b["key_moments"]["goals"]),
        "big_chances": _values_with_difference(a["key_moments"]["big_chances"], b["key_moments"]["big_chances"]),
        "cards": _values_with_difference(a["key_moments"]["cards"], b["key_moments"]["cards"]),
        "rows_a": a["key_moments"]["rows"][:12],
        "rows_b": b["key_moments"]["rows"][:12],
    }


def _momentum_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    if not rows:
        return {"total_score": 0, "peak_score": 0, "leader": None, "peak_interval": None, "by_team": {}}
    by_team: dict[str, float] = {}
    peak = rows[0]
    for row in rows:
        team = str(row.get("team_name") or "Sin equipo")
        score = _number(row.get("momentum_score"))
        by_team[team] = by_team.get(team, 0.0) + score
        if score > _number(peak.get("momentum_score")):
            peak = row
    leader = max(by_team.items(), key=lambda item: item[1]) if by_team else None
    return {
        "total_score": _round(sum(by_team.values())),
        "peak_score": _round(peak.get("momentum_score")),
        "leader": {"team_name": leader[0], "momentum_score": _round(leader[1])} if leader else None,
        "peak_interval": {
            "team_name": peak.get("team_name"),
            "interval_start": peak.get("interval_start"),
            "interval_end": peak.get("interval_end"),
            "momentum_score": _round(peak.get("momentum_score")),
        },
        "by_team": {team: _round(value) for team, value in by_team.items()},
    }


def _intensity(total_events: float, shots: float) -> dict[str, Any]:
    score = _number(total_events) + _number(shots) * 25
    if score >= 4300:
        label = "alta"
    elif score >= 3200:
        label = "media"
    else:
        label = "baja"
    return {"events": _int(total_events), "shots": _int(shots), "score": _round(score), "label": label}


def _context_warnings(label: str, context: dict[str, Any]) -> list[str]:
    warnings = []
    validation = context.get("validation", {}) or {}
    if validation.get("status") and validation.get("status") != "PASS":
        warnings.append(f"Partido {label}: validación analítica en estado {validation.get('status')}.")
    if not context.get("dominance"):
        warnings.append(f"Partido {label}: no hay datos de dominio.")
    if not context.get("impact_players"):
        warnings.append(f"Partido {label}: no hay jugadores de impacto.")
    return warnings


def _dominance_snapshot(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "team_name": row.get("team_name"),
        "dominance_score": row.get("dominance_score"),
        "shots": row.get("shots"),
        "xg": row.get("xg"),
        "final_third_entries": row.get("final_third_entries"),
        "progressive_passes": row.get("progressive_passes"),
    }


def _player_snapshot(row: dict[str, Any] | None) -> dict[str, Any]:
    row = row or {}
    return {
        "player_name": row.get("player_name"),
        "team_name": row.get("team_name"),
        "impact_score": row.get("impact_score"),
        "goals": row.get("goals"),
        "assists": row.get("assists"),
        "shots": row.get("shots"),
        "xg": row.get("xg"),
        "key_passes": row.get("key_passes"),
    }


def _values_with_difference(value_a: Any, value_b: Any) -> dict[str, Any]:
    return {
        "match_a": value_a,
        "match_b": value_b,
        "difference_b_minus_a": _round(_number(value_b) - _number(value_a)),
        "higher_match": _winner_label(value_a, value_b),
    }


def _difference(value_a: Any, value_b: Any) -> dict[str, Any]:
    return _values_with_difference(value_a, value_b)


def _winner_label(value_a: Any, value_b: Any) -> str:
    number_a = _number(value_a)
    number_b = _number(value_b)
    if number_a > number_b:
        return "A"
    if number_b > number_a:
        return "B"
    return "Empate"


def _scoreline(summary: dict[str, Any]) -> str:
    return (
        f"{summary.get('home_team_name', 'N/D')} {summary.get('home_score', 'N/D')}-"
        f"{summary.get('away_score', 'N/D')} {summary.get('away_team_name', 'N/D')}"
    )


def _score_goals(summary: dict[str, Any]) -> float:
    return _number(summary.get("home_score")) + _number(summary.get("away_score"))


def _rows_by_team(rows: list[dict[str, Any]], value_key: str) -> dict[str, Any]:
    return {str(row.get("team_name")): row.get(value_key) for row in rows if row.get("team_name")}


def _count_by_key(rows: list[dict[str, Any]], key: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        value = str(row.get(key) or "Sin dato")
        counts[value] = counts.get(value, 0) + 1
    return counts


def _sum_rows(rows: list[dict[str, Any]], key: str) -> float:
    return sum(_number(row.get(key)) for row in rows)


def _first(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return rows[0] if rows else {}


def _number(*values: Any) -> float:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return 0.0


def _int(value: Any) -> int:
    return int(round(_number(value)))


def _round(value: Any, digits: int = 3) -> float:
    return round(_number(value), digits)
