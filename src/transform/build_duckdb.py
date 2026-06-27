"""Build the analytical DuckDB database from raw StatsBomb JSON files."""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any

import duckdb

from src.config import ANALYTICS_DB, RAW_EVENTS_DIR, ensure_directories
from src.transform.normalize_360 import normalize_360_for_match
from src.transform.normalize_competitions import normalize_competitions
from src.transform.normalize_events import normalize_events_for_match
from src.transform.normalize_lineups import normalize_lineups_for_match
from src.transform.normalize_matches import normalize_matches
from src.transform.schema import TABLE_COLUMNS, create_schema, create_views
from src.transform.utils import (
    EVENT_FILE_RE,
    insert_rows,
    match_id_from_path,
    quote_identifier,
    replace_dimension_rows,
)

PER_MATCH_TABLES = [
    "lineup",
    "event",
    "pass",
    "shot",
    "carry",
    "duel",
    "pressure",
    "foul",
    "goalkeeper_action",
    "substitution",
    "event_relationship",
    "freeze_frame",
    "visible_area",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Transform raw StatsBomb JSON into data/analytics/statsbomb.duckdb.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of raw event matches transformed.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Rebuild/reprocess existing transformed rows.",
    )
    parser.add_argument(
        "--match-id",
        type=int,
        default=None,
        help="Transform a specific match_id.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_directories()

    if args.force and args.match_id is None and ANALYTICS_DB.exists():
        ANALYTICS_DB.unlink()

    connection = duckdb.connect(str(ANALYTICS_DB))
    try:
        create_schema(connection)
        refresh_global_dimensions(connection)

        match_ids = select_match_ids(args.match_id, args.limit)
        summary = {
            "transformed": 0,
            "failed": 0,
            "skipped_existing": 0,
            "events_rows": 0,
            "passes_rows": 0,
            "shots_rows": 0,
        }

        for match_id in match_ids:
            result = transform_match(connection, match_id=match_id, force=args.force)
            summary[result["status"]] = summary.get(result["status"], 0) + 1
            summary["events_rows"] += int(result.get("events_rows") or 0)
            summary["passes_rows"] += int(result.get("passes_rows") or 0)
            summary["shots_rows"] += int(result.get("shots_rows") or 0)

        create_views(connection)
        print_summary(summary, len(match_ids))
        print(f"analytics db: {ANALYTICS_DB.as_posix()}")
    finally:
        connection.close()


def refresh_global_dimensions(connection: duckdb.DuckDBPyConnection) -> None:
    competitions = normalize_competitions()
    matches = normalize_matches()

    connection.execute("DELETE FROM competition")
    connection.execute("DELETE FROM season")
    connection.execute('DELETE FROM "match"')

    insert_rows(connection, "competition", competitions["competition"], TABLE_COLUMNS["competition"])
    insert_rows(connection, "season", competitions["season"], TABLE_COLUMNS["season"])
    insert_rows(connection, "match", matches["match"], TABLE_COLUMNS["match"])
    replace_dimension_rows(
        connection,
        "team",
        matches["team"],
        TABLE_COLUMNS["team"],
        key_columns=["team_id"],
    )


def select_match_ids(match_id: int | None, limit: int | None) -> list[int]:
    if match_id is not None:
        return [match_id]

    match_ids = sorted(
        match_id
        for match_id in (match_id_from_path(path, EVENT_FILE_RE) for path in RAW_EVENTS_DIR.glob("events.match-*.json"))
        if match_id is not None
    )

    if limit is not None:
        match_ids = match_ids[:limit]
    return match_ids


def transform_match(
    connection: duckdb.DuckDBPyConnection,
    match_id: int,
    force: bool = False,
) -> dict[str, Any]:
    existing_log = get_existing_transformation_log(connection, match_id)
    if not force and existing_log is not None and existing_log["status"] in {"transformed", "skipped_existing"}:
        write_transformation_log(
            connection,
            match_id=match_id,
            status="skipped_existing",
            events_transformed=True,
            events_rows=existing_log.get("events_rows"),
            passes_rows=existing_log.get("passes_rows"),
            shots_rows=existing_log.get("shots_rows"),
            lineups_rows=existing_log.get("lineups_rows"),
            freeze_frame_rows=existing_log.get("freeze_frame_rows"),
        )
        return {"status": "skipped_existing"}

    delete_match_rows(connection, match_id)

    try:
        lineups = normalize_lineups_for_match(match_id)
        events = normalize_events_for_match(match_id)
        three_sixty = normalize_360_for_match(match_id)

        replace_dimension_rows(
            connection,
            "team",
            [*lineups["team"], *events["team"]],
            TABLE_COLUMNS["team"],
            key_columns=["team_id"],
        )
        replace_dimension_rows(
            connection,
            "player",
            [*lineups["player"], *events["player"]],
            TABLE_COLUMNS["player"],
            key_columns=["player_id"],
        )

        lineups_rows = insert_rows(connection, "lineup", lineups["lineup"], TABLE_COLUMNS["lineup"])
        events_rows = insert_rows(connection, "event", events["event"], TABLE_COLUMNS["event"])
        passes_rows = insert_rows(connection, "pass", events["pass"], TABLE_COLUMNS["pass"])
        shots_rows = insert_rows(connection, "shot", events["shot"], TABLE_COLUMNS["shot"])
        insert_rows(connection, "carry", events["carry"], TABLE_COLUMNS["carry"])
        insert_rows(connection, "duel", events["duel"], TABLE_COLUMNS["duel"])
        insert_rows(connection, "pressure", events["pressure"], TABLE_COLUMNS["pressure"])
        insert_rows(connection, "foul", events["foul"], TABLE_COLUMNS["foul"])
        insert_rows(
            connection,
            "goalkeeper_action",
            events["goalkeeper_action"],
            TABLE_COLUMNS["goalkeeper_action"],
        )
        insert_rows(connection, "substitution", events["substitution"], TABLE_COLUMNS["substitution"])
        insert_rows(
            connection,
            "event_relationship",
            events["event_relationship"],
            TABLE_COLUMNS["event_relationship"],
        )
        freeze_frame_rows = insert_rows(
            connection,
            "freeze_frame",
            events["freeze_frame"],
            TABLE_COLUMNS["freeze_frame"],
        )
        insert_rows(
            connection,
            "visible_area",
            three_sixty["visible_area"],
            TABLE_COLUMNS["visible_area"],
        )

        write_transformation_log(
            connection,
            match_id=match_id,
            events_transformed=True,
            events_rows=events_rows,
            passes_rows=passes_rows,
            shots_rows=shots_rows,
            lineups_rows=lineups_rows,
            freeze_frame_rows=freeze_frame_rows,
            status="transformed",
            error_message=None,
        )
        return {
            "status": "transformed",
            "events_rows": events_rows,
            "passes_rows": passes_rows,
            "shots_rows": shots_rows,
        }
    except Exception as exc:
        write_transformation_log(
            connection,
            match_id=match_id,
            events_transformed=False,
            events_rows=0,
            passes_rows=0,
            shots_rows=0,
            lineups_rows=0,
            freeze_frame_rows=0,
            status="failed",
            error_message=str(exc),
        )
        return {"status": "failed", "error_message": str(exc)}


def get_existing_transformation_log(
    connection: duckdb.DuckDBPyConnection,
    match_id: int,
) -> dict[str, Any] | None:
    row = connection.execute(
        """
        SELECT
            events_rows,
            passes_rows,
            shots_rows,
            lineups_rows,
            freeze_frame_rows,
            status
        FROM transformation_log
        WHERE match_id = ?
        """,
        [match_id],
    ).fetchone()
    if row is None:
        return None
    return {
        "events_rows": row[0],
        "passes_rows": row[1],
        "shots_rows": row[2],
        "lineups_rows": row[3],
        "freeze_frame_rows": row[4],
        "status": row[5],
    }


def delete_match_rows(connection: duckdb.DuckDBPyConnection, match_id: int) -> None:
    for table_name in PER_MATCH_TABLES:
        connection.execute(
            f"DELETE FROM {quote_identifier(table_name)} WHERE match_id = ?",
            [match_id],
        )
    connection.execute("DELETE FROM transformation_log WHERE match_id = ?", [match_id])


def write_transformation_log(
    connection: duckdb.DuckDBPyConnection,
    match_id: int,
    events_transformed: bool | None = None,
    events_rows: int | None = None,
    passes_rows: int | None = None,
    shots_rows: int | None = None,
    lineups_rows: int | None = None,
    freeze_frame_rows: int | None = None,
    status: str = "pending",
    error_message: str | None = None,
) -> None:
    connection.execute("DELETE FROM transformation_log WHERE match_id = ?", [match_id])
    insert_rows(
        connection,
        "transformation_log",
        [
            {
                "match_id": match_id,
                "events_transformed": events_transformed,
                "events_rows": events_rows,
                "passes_rows": passes_rows,
                "shots_rows": shots_rows,
                "lineups_rows": lineups_rows,
                "freeze_frame_rows": freeze_frame_rows,
                "status": status,
                "transformed_at": datetime.now(timezone.utc),
                "error_message": error_message,
            }
        ],
        TABLE_COLUMNS["transformation_log"],
    )


def print_summary(summary: dict[str, int], selected_matches: int) -> None:
    print("transformation summary:")
    print(f"- partidos seleccionados: {selected_matches}")
    print(f"- partidos transformados: {summary.get('transformed', 0)}")
    print(f"- partidos fallidos: {summary.get('failed', 0)}")
    print(f"- partidos omitidos: {summary.get('skipped_existing', 0)}")
    print(f"- eventos cargados: {summary.get('events_rows', 0)}")
    print(f"- pases cargados: {summary.get('passes_rows', 0)}")
    print(f"- tiros cargados: {summary.get('shots_rows', 0)}")


if __name__ == "__main__":
    main()
