"""Benchmark checks for transformed data and narrative claims."""

from __future__ import annotations

from typing import Any

from src.narrative.fact_guard import normalize_text


def check_match_summary(case: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    expected = case["expected"]
    summary = context.get("match_summary", {})
    failures = []
    comparisons = {
        "match_id": (case.get("match_id"), summary.get("match_id")),
        "home_team": (expected.get("home_team"), summary.get("home_team_name")),
        "away_team": (expected.get("away_team"), summary.get("away_team_name")),
        "home_score": (expected.get("home_score"), _to_int(summary.get("home_score"))),
        "away_score": (expected.get("away_score"), _to_int(summary.get("away_score"))),
        "winner": (expected.get("winner"), summary.get("winner_team_name")),
    }
    for key, (wanted, actual) in comparisons.items():
        if _normalize_value(wanted) != _normalize_value(actual):
            failures.append({"field": key, "expected": wanted, "actual": actual})
    status = "PASS" if not failures else "FAIL"
    return _check_result(
        "match_summary",
        status,
        "Match summary matches expected benchmark." if status == "PASS" else "Match summary differs.",
        {"comparisons": comparisons, "failures": failures},
    )


def check_dominance(case: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    expected = case["expected"]
    expected_dominant = expected.get("dominant_team")
    dominance = context.get("dominance", [])
    xg_breakdown = context.get("xg_breakdown", [])
    leader = dominance[0] if dominance else {}
    xg_leader = _xg_leader(xg_breakdown)
    warnings = []
    failures = []

    if expected_dominant:
        if normalize_text(str(leader.get("team_name") or "")) != normalize_text(str(expected_dominant)):
            failures.append(
                {
                    "field": "dominance_leader",
                    "expected": expected_dominant,
                    "actual": leader.get("team_name"),
                }
            )
        if xg_leader and normalize_text(xg_leader) != normalize_text(str(expected_dominant)):
            warnings.append(
                {
                    "field": "xg_leader",
                    "expected": expected_dominant,
                    "actual": xg_leader,
                }
            )

    if failures:
        status = "FAIL"
        message = "Dominance leader differs from expected benchmark."
    elif warnings:
        status = "WARNING"
        message = "Dominance leader matches, but xG leader differs."
    else:
        status = "PASS"
        message = "Dominance and xG are consistent with expected benchmark."
    return _check_result(
        "dominance",
        status,
        message,
        {"leader": leader, "xg_leader": xg_leader, "warnings": warnings, "failures": failures},
    )


def check_key_players(case: dict[str, Any], context: dict[str, Any]) -> dict[str, Any]:
    expected_players = case["expected"].get("key_players_any", [])
    haystack = _collect_player_haystack(context)
    matches = []
    for player in expected_players:
        player_norm = normalize_text(player)
        if any(player_norm in item or item in player_norm for item in haystack):
            matches.append(player)
    status = "PASS" if matches else "FAIL"
    return _check_result(
        "key_players",
        status,
        "Expected key player appears in analytical context." if matches else "Expected key player not found.",
        {"expected_any": expected_players, "matches": matches},
    )


def check_narrative_claims(case: dict[str, Any], narrative: str) -> dict[str, Any]:
    expected = case["expected"]
    text = normalize_text(narrative)
    failures = []
    warnings = []
    home_score = expected.get("home_score")
    away_score = expected.get("away_score")
    score_patterns = {
        f"{home_score}-{away_score}",
        f"{home_score} - {away_score}",
        f"{away_score}-{home_score}",
        f"{away_score} - {home_score}",
    }
    if not any(pattern in narrative for pattern in score_patterns):
        failures.append("Narrative does not mention the expected score.")
    winner = normalize_text(str(expected.get("winner") or ""))
    if winner and winner not in text:
        failures.append("Narrative does not mention the expected winner.")

    prohibited_hits = []
    for claim in expected.get("must_not_claim", []):
        if _claim_present(claim, text):
            prohibited_hits.append(claim)
    if prohibited_hits:
        failures.append("Narrative includes prohibited claims.")

    if home_score != away_score and "empate" in text:
        failures.append("Narrative claims a draw in a non-draw match.")
    if abs(int(home_score or 0) - int(away_score or 0)) < 3 and "goleada" in text:
        warnings.append("Narrative uses goleada for a match decided by fewer than three goals.")
    if "remontada" in text:
        warnings.append("Narrative mentions comeback; benchmark does not expect it.")

    if failures:
        status = "FAIL"
        message = "Narrative contains factual benchmark violations."
    elif warnings:
        status = "WARNING"
        message = "Narrative has soft claims to review."
    else:
        status = "PASS"
        message = "Narrative claims are consistent with benchmark."
    return _check_result(
        "narrative_claims",
        status,
        message,
        {"failures": failures, "warnings": warnings, "prohibited_hits": prohibited_hits},
    )


def _check_result(check_name: str, status: str, message: str, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "check_name": check_name,
        "status": status,
        "message": message,
        "details": details,
    }


def _to_int(value: Any) -> int | None:
    if value is None:
        return None
    return int(value)


def _normalize_value(value: Any) -> Any:
    if isinstance(value, str):
        return normalize_text(value)
    return value


def _xg_leader(rows: list[dict[str, Any]]) -> str | None:
    if not rows:
        return None
    leader = max(rows, key=lambda row: float(row.get("xg_total") or 0))
    return str(leader.get("team_name") or "") or None


def _collect_player_haystack(context: dict[str, Any]) -> set[str]:
    names = set()
    for key in ("top_players", "impact_players", "player_stats", "key_moments"):
        for row in context.get(key, []):
            name = row.get("player_name")
            if name:
                names.add(normalize_text(str(name)))
    return names


def _claim_present(claim: str, normalized_text: str) -> bool:
    claim_norm = normalize_text(claim)
    semantic_claims = {
        "draw": ("draw", "empate", "empatado"),
        "germany won": ("germany won", "alemania gano", "germany gano", "triunfo de germany"),
        "mexico lost": ("mexico lost", "mexico perdio", "mexico cayo"),
        "extra time": ("extra time", "tiempo extra", "prorroga"),
        "penalty shootout": ("penalty shootout", "tanda de penales", "penaltis"),
    }
    return any(pattern in normalized_text for pattern in semantic_claims.get(claim_norm, (claim_norm,)))
