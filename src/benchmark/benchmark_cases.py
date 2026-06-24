"""Benchmark case definitions."""

from __future__ import annotations

from typing import Any


BENCHMARK_CASES: list[dict[str, Any]] = [
    {
        "case_id": "germany_mexico_2018",
        "match_id": 7534,
        "label": "Germany 0-1 Mexico, World Cup 2018",
        "expected": {
            "home_team": "Germany",
            "away_team": "Mexico",
            "home_score": 0,
            "away_score": 1,
            "winner": "Mexico",
            "dominant_team": "Germany",
            "key_players_any": ["Hirving Lozano", "Lozano", "Hirving Rodrigo Lozano Bahena"],
            "themes_any": [
                "Mexico effective in transition",
                "Germany territorial dominance",
                "German dominance with Mexican efficiency",
            ],
            "must_not_claim": [
                "draw",
                "Germany won",
                "Mexico lost",
                "extra time",
                "penalty shootout",
            ],
        },
    },
]

FUTURE_BENCHMARK_IDEAS = [
    "brazil_germany_2014",
    "spain_netherlands_2014",
    "argentina_france_2018_or_2022",
]


def get_benchmark_case(case_id: str) -> dict[str, Any]:
    for case in BENCHMARK_CASES:
        if case["case_id"] == case_id:
            return case
    supported = ", ".join(case["case_id"] for case in BENCHMARK_CASES)
    raise ValueError(f"Unsupported benchmark case '{case_id}'. Supported cases: {supported}")

