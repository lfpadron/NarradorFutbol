"""Match event data for the standalone player cards (no changes to shared metrics)."""

from __future__ import annotations

import json
import math
from collections import Counter
from typing import Any


def load_player_cards(match_id: int, player_ids: list[int]) -> list[dict[str, Any]]:
    from src.analytics.db import query_one, query_records

    if not 1 <= len(player_ids) <= 2 or len(set(player_ids)) != len(player_ids):
        raise ValueError("Selecciona uno o dos jugadores distintos.")
    match = query_one(
        """SELECT m.*, c.competition_name FROM "match" m
           LEFT JOIN competition c ON c.competition_id = m.competition_id
           WHERE m.match_id = ?""",
        (match_id,),
    )
    if match is None:
        raise ValueError("No se encontró el partido seleccionado.")
    rows = query_records("SELECT raw_event_json FROM event WHERE match_id = ? ORDER BY event_index", (match_id,))
    events = []
    for row in rows:
        try:
            event = json.loads(row.get("raw_event_json") or "null")
        except (TypeError, ValueError) as exc:
            raise ValueError("Los eventos originales del partido no están disponibles para las tarjetas.") from exc
        if not isinstance(event, dict):
            raise ValueError("Los eventos originales del partido no están disponibles para las tarjetas.")
        events.append(event)
    lineups = query_records("SELECT * FROM lineup WHERE match_id = ?", (match_id,))
    return [build_player_card(match, events, lineups, player_id) for player_id in player_ids]


def _name(event: dict[str, Any], key: str) -> str | None:
    return (event.get(key) or {}).get("name")


def _point(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) < 2:
        return None
    try:
        x, y = float(value[0]), float(value[1])
    except (TypeError, ValueError):
        return None
    return (x, y) if math.isfinite(x) and math.isfinite(y) and 0 <= x <= 120 and 0 <= y <= 80 else None


def _cards(events: list[dict[str, Any]]) -> list[tuple[int, str]]:
    cards = []
    for event in events:
        for key in ("foul_committed", "bad_behaviour"):
            name = _name(event.get(key) or {}, "card")
            if name:
                cards.append((int(event.get("minute") or 0), name))
    return cards


def _interval(
    events: list[dict[str, Any]], player_id: int, lineup: dict[str, Any], own: list[dict[str, Any]]
) -> tuple[int | None, int | None]:
    starter = lineup.get("starter") is True or any(
        _name(event, "type") == "Starting XI"
        and any((row.get("player") or {}).get("id") == player_id for row in event.get("tactics", {}).get("lineup", []))
        for event in events
    )
    start = 0 if starter else None
    end = None
    for event in events:
        if _name(event, "type") == "Substitution":
            if event.get("substitution", {}).get("replacement", {}).get("id") == player_id:
                start = int(event.get("minute") or 0)
            if event.get("player", {}).get("id") == player_id:
                end = int(event.get("minute") or 0)
    dismissals = [minute for minute, name in _cards(own) if name in {"Red Card", "Second Yellow"}]
    if dismissals:
        end = min([*dismissals, *([end] if end is not None else [])])
    # A player's final touch is not their exit time. Require a recorded match end.
    ends = [int(e.get("minute") or 0) for e in events if _name(e, "type") == "Half End"]
    if end is None and ends:
        final_period = max(int(e.get("period") or 1) for e in events)
        ends = [
            int(e.get("minute") or 0)
            for e in events
            if _name(e, "type") == "Half End" and int(e.get("period") or 1) == final_period
        ]
        end = max(ends) if ends else None
    return start, end


def build_player_card(
    match: dict[str, Any], events: list[dict[str, Any]], lineups: list[dict[str, Any]], player_id: int
) -> dict[str, Any]:
    """Calculate card-only metrics. Shootouts are excluded; missing locations never become (0, 0)."""
    events = [event for event in events if int(event.get("period") or 1) <= 4]
    own = [event for event in events if (event.get("player") or {}).get("id") == player_id]
    lineup = next((row for row in lineups if row.get("player_id") == player_id), {})
    if not own:
        raise ValueError(f"El jugador {player_id} no tiene eventos en este partido.")
    counts = Counter(_name(event, "type") for event in own)
    passes = [event for event in own if _name(event, "type") == "Pass"]
    shots = [event.get("shot") or {} for event in own if _name(event, "type") == "Shot"]
    dribbles = [event.get("dribble") or {} for event in own if _name(event, "type") == "Dribble"]
    tackles = [
        event.get("duel") or {}
        for event in own
        if _name(event, "type") == "Duel" and _name(event.get("duel") or {}, "type") == "Tackle"
    ]

    def completed(event: dict[str, Any]) -> bool:
        return not (event.get("pass") or {}).get("outcome")

    final_third, long_passes, pass_map = [], [], []
    for event in passes:
        data = event.get("pass") or {}
        start, end = _point(event.get("location")), _point(data.get("end_location"))
        if start and end:
            pass_map.append({"start": start, "end": end, "completed": completed(event)})
            if start[0] < 80 <= end[0]:
                final_third.append(event)
        if float(data.get("length") or 0) >= 30:
            long_passes.append(event)
    progressive_carries = 0
    receptions, recoveries = [], []
    for event in own:
        kind = _name(event, "type")
        start = _point(event.get("location"))
        if kind == "Carry":
            end = _point((event.get("carry") or {}).get("end_location"))
            if start and end and end[0] - start[0] >= 10:
                progressive_carries += 1
        if start and kind == "Ball Receipt*" and not (event.get("ball_receipt") or {}).get("outcome"):
            receptions.append(start)
        if start and kind == "Ball Recovery" and not (event.get("ball_recovery") or {}).get("recovery_failure"):
            recoveries.append(start)
    positions = Counter(_name(event, "position") for event in own if _name(event, "position"))
    start_minute, end_minute = _interval(events, player_id, lineup, own)
    return {
        "match": match,
        "player_id": player_id,
        "player_name": lineup.get("player_name") or own[0]["player"]["name"],
        "team_name": lineup.get("team_name") or _name(own[0], "team"),
        "position": positions.most_common(1)[0][0] if positions else lineup.get("position_name"),
        "start_minute": start_minute,
        "end_minute": end_minute,
        "rating": None,  # No player rating is supplied by the imported event data.
        "stats": {
            "shots": len(shots),
            "goals": sum(_name(shot, "outcome") == "Goal" for shot in shots),
            "xg": sum(float(shot.get("statsbomb_xg") or 0) for shot in shots),
            "passes": len(passes),
            "completed_passes": sum(completed(event) for event in passes),
            "final_third_passes": len(final_third),
            "completed_final_third_passes": sum(completed(event) for event in final_third),
            "long_passes": len(long_passes),
            "completed_long_passes": sum(completed(event) for event in long_passes),
            "key_passes": sum(bool((event.get("pass") or {}).get("shot_assist")) for event in passes),
            "pressures": counts["Pressure"],
            "tackles": len(tackles),
            "won_tackles": sum(
                _name(duel, "outcome") in {"Won", "Success", "Success In Play", "Success Out"} for duel in tackles
            ),
            "clearances": counts["Clearance"],
            "blocks": counts["Block"],
            "dribbles": len(dribbles),
            "completed_dribbles": sum(_name(dribble, "outcome") == "Complete" for dribble in dribbles),
            "progressive_carries": progressive_carries,
            "dispossessed": counts["Dispossessed"],
            "dribbled_past": counts["Dribbled Past"],
            "miscontrols": counts["Miscontrol"],
            "fouls_committed": counts["Foul Committed"],
            "fouls_won": counts["Foul Won"],
        },
        "cards": [name for _, name in _cards(own)],
        "passes": pass_map,
        "receptions": receptions,
        "recoveries": recoveries,
    }


def card_notes(language: str = "es") -> str:
    if language == "en":
        return (
            "Ratios: successful/attempted. Final-third passes: from x < 80 to x ≥ 80; long passes: ≥ 30 yards; "
            "progressive carries: forward gain ≥ 10 yards. Both maps attack upwards; only located events are plotted. "
            "Minutes include added time; shootouts excluded. N/A: rating or playing interval unavailable in the data."
        )
    return (
        "Fracciones: exitosos/intentos. Pases al último tercio: de x < 80 a x ≥ 80; largos: ≥ 30 yardas; "
        "conducciones progresivas: avance ≥ 10 yardas. Ambos mapas atacan hacia arriba; solo se grafican eventos "
        "con coordenadas. Minutos con añadido; sin tandas de penaltis. N/D: calificación o intervalo no disponible."
    )
