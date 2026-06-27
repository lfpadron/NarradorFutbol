"""Persistent ingestion log stored in DuckDB."""

from __future__ import annotations

import math
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

import duckdb

from src.config import INGESTION_LOG_DB
from src.ingestion.utils import VALID_STATUSES, as_int, pick_first

LOG_COLUMNS = {
    "match_id",
    "competition_id",
    "season_id",
    "match_date",
    "home_team",
    "away_team",
    "events_status",
    "events_rows",
    "lineups_status",
    "three_sixty_status",
    "has_360",
    "last_attempt_at",
    "error_message",
    "event_file_path",
    "lineup_file_path",
    "three_sixty_file_path",
    "transformed_at",
}


class IngestionLog:
    def __init__(self, db_path: Path = INGESTION_LOG_DB) -> None:
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.connection = duckdb.connect(str(self.db_path))
        self.ensure_schema()

    def close(self) -> None:
        self.connection.close()

    def __enter__(self) -> "IngestionLog":
        return self

    def __exit__(self, *_: object) -> None:
        self.close()

    def ensure_schema(self) -> None:
        self.connection.execute("""
            CREATE TABLE IF NOT EXISTS ingestion_log (
                match_id BIGINT PRIMARY KEY,
                competition_id BIGINT,
                season_id BIGINT,
                match_date VARCHAR,
                home_team VARCHAR,
                away_team VARCHAR,
                events_status VARCHAR,
                events_rows BIGINT,
                lineups_status VARCHAR,
                three_sixty_status VARCHAR,
                has_360 BOOLEAN,
                last_attempt_at TIMESTAMP,
                error_message VARCHAR,
                event_file_path VARCHAR,
                lineup_file_path VARCHAR,
                three_sixty_file_path VARCHAR,
                transformed_at TIMESTAMP
            )
            """)

    def ensure_match(self, match_record: dict[str, Any]) -> int:
        summary = match_summary(match_record)
        match_id = summary["match_id"]
        if match_id is None:
            raise ValueError(f"Match record does not include match_id: {match_record}")

        self.connection.execute(
            """
            INSERT INTO ingestion_log (
                match_id,
                competition_id,
                season_id,
                match_date,
                home_team,
                away_team,
                events_status,
                events_rows,
                lineups_status,
                three_sixty_status,
                has_360,
                last_attempt_at,
                error_message,
                event_file_path,
                lineup_file_path,
                three_sixty_file_path,
                transformed_at
            )
            SELECT ?, ?, ?, ?, ?, ?, 'pending', NULL, 'pending', 'pending',
                   FALSE, NULL, NULL, NULL, NULL, NULL, NULL
            WHERE NOT EXISTS (
                SELECT 1 FROM ingestion_log WHERE match_id = ?
            )
            """,
            [
                summary["match_id"],
                summary["competition_id"],
                summary["season_id"],
                summary["match_date"],
                summary["home_team"],
                summary["away_team"],
                summary["match_id"],
            ],
        )
        self.update_match(
            match_id,
            competition_id=summary["competition_id"],
            season_id=summary["season_id"],
            match_date=summary["match_date"],
            home_team=summary["home_team"],
            away_team=summary["away_team"],
        )
        return match_id

    def start_attempt(self, match_id: int) -> None:
        self.update_match(match_id, last_attempt_at=datetime.now(timezone.utc))

    def update_match(self, match_id: int, **fields: Any) -> None:
        if not fields:
            return

        unknown_columns = set(fields) - LOG_COLUMNS
        if unknown_columns:
            raise ValueError(f"Unknown ingestion_log columns: {sorted(unknown_columns)}")

        self._validate_statuses(fields)

        assignments = ", ".join(f"{column} = ?" for column in fields)
        values = [_db_value(value) for value in fields.values()]
        values.append(match_id)
        self.connection.execute(
            f"UPDATE ingestion_log SET {assignments} WHERE match_id = ?",
            values,
        )

    def failed_match_ids(self) -> set[int]:
        rows = self.connection.execute("""
            SELECT match_id
            FROM ingestion_log
            WHERE events_status = 'failed'
               OR lineups_status = 'failed'
               OR three_sixty_status = 'failed'
            """).fetchall()
        return {int(row[0]) for row in rows}

    def summary(self) -> list[tuple[str, int]]:
        rows = self.connection.execute("""
            WITH statuses AS (
                SELECT events_status AS status FROM ingestion_log
                UNION ALL
                SELECT lineups_status AS status FROM ingestion_log
                UNION ALL
                SELECT three_sixty_status AS status FROM ingestion_log
            )
            SELECT status, COUNT(*) AS rows
            FROM statuses
            GROUP BY status
            ORDER BY status
            """).fetchall()
        return [(row[0], int(row[1])) for row in rows]

    @staticmethod
    def _validate_statuses(fields: dict[str, Any]) -> None:
        for column in ("events_status", "lineups_status", "three_sixty_status"):
            if column in fields and fields[column] not in VALID_STATUSES:
                raise ValueError(f"Invalid status for {column}: {fields[column]}")


def match_summary(record: dict[str, Any]) -> dict[str, Any]:
    return {
        "match_id": as_int(pick_first(record, "match_id")),
        "competition_id": as_int(pick_first(record, "competition_id")),
        "season_id": as_int(pick_first(record, "season_id")),
        "match_date": _string_or_none(pick_first(record, "match_date")),
        "home_team": _string_or_none(
            pick_first(
                record,
                "home_team_home_team_name",
                "home_team_name",
                "home_team",
            )
        ),
        "away_team": _string_or_none(
            pick_first(
                record,
                "away_team_away_team_name",
                "away_team_name",
                "away_team",
            )
        ),
    }


def _string_or_none(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return str(value)


def _db_value(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if hasattr(value, "item"):
        try:
            return _db_value(value.item())
        except (TypeError, ValueError):
            pass
    if isinstance(value, date) and not isinstance(value, datetime):
        return value.isoformat()
    return value
