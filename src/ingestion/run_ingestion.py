"""Command-line runner for StatsBomb raw data ingestion."""

from __future__ import annotations

import argparse
from typing import Any

from tqdm import tqdm

from src.config import ensure_directories, project_relative
from src.ingestion.download_360 import download_three_sixty
from src.ingestion.download_competitions import download_competitions
from src.ingestion.download_events import download_events
from src.ingestion.download_lineups import download_lineups
from src.ingestion.download_matches import (
    build_master_matches_index,
    competition_pairs,
    download_matches,
)
from src.ingestion.ingestion_log import IngestionLog
from src.ingestion.utils import as_int


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download StatsBomb Open Data raw JSON and update ingestion log.")
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Limit number of matches processed for events, lineups and 360.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Redownload files even when they already exist.",
    )
    parser.add_argument(
        "--retry-failed",
        action="store_true",
        help="Only process matches with failed statuses in the ingestion log.",
    )
    parser.add_argument(
        "--match-id",
        type=int,
        default=None,
        help="Only process one specific match_id for events, lineups and 360.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_directories()

    competitions_result = download_competitions(force=args.force)
    print(
        "competitions:",
        competitions_result.status,
        _path_text(competitions_result.path),
    )

    pairs = competition_pairs(competitions_result.data)
    print(f"competition/season pairs: {len(pairs)}")

    matches_downloaded = 0
    matches_skipped = 0
    matches_failed = 0
    for competition_id, season_id in tqdm(pairs, desc="matches"):
        try:
            result = download_matches(
                competition_id=competition_id,
                season_id=season_id,
                force=args.force,
            )
            if result.status == "downloaded":
                matches_downloaded += 1
            elif result.status == "skipped_existing":
                matches_skipped += 1
        except Exception as exc:
            matches_failed += 1
            print(
                "matches failed:",
                f"competition_id={competition_id}",
                f"season_id={season_id}",
                str(exc),
            )

    print(
        "matches summary:",
        f"downloaded={matches_downloaded}",
        f"skipped_existing={matches_skipped}",
        f"failed={matches_failed}",
    )

    all_matches = build_master_matches_index()
    print(f"master match index rows: {len(all_matches)}")

    with IngestionLog() as ingestion_log:
        match_records = all_matches.to_dict(orient="records")

        if args.retry_failed:
            failed_ids = ingestion_log.failed_match_ids()
            match_records = [record for record in match_records if as_int(record.get("match_id")) in failed_ids]
            print(f"retry_failed matches: {len(match_records)}")

        if args.match_id is not None:
            match_records = [record for record in match_records if as_int(record.get("match_id")) == args.match_id]
            if not match_records:
                raise SystemExit(f"match_id={args.match_id} not found in all_matches index.")
            print(f"selected match_id: {args.match_id}")

        if args.limit is not None:
            match_records = match_records[: args.limit]

        for record in tqdm(match_records, desc="match payloads"):
            process_match(record, ingestion_log=ingestion_log, force=args.force)

        print("ingestion log status summary:")
        for status, rows in ingestion_log.summary():
            print(f"- {status}: {rows}")


def process_match(
    match_record: dict[str, Any],
    ingestion_log: IngestionLog,
    force: bool = False,
) -> None:
    match_id = ingestion_log.ensure_match(match_record)
    ingestion_log.start_attempt(match_id)
    errors: list[str] = []

    try:
        events_result = download_events(match_id, force=force)
        ingestion_log.update_match(
            match_id,
            events_status=events_result.status,
            events_rows=events_result.rows,
            event_file_path=_path_text(events_result.path),
        )
    except Exception as exc:
        errors.append(f"events: {exc}")
        ingestion_log.update_match(match_id, events_status="failed")

    try:
        lineups_result = download_lineups(match_id, force=force)
        ingestion_log.update_match(
            match_id,
            lineups_status=lineups_result.status,
            lineup_file_path=_path_text(lineups_result.path),
        )
    except Exception as exc:
        errors.append(f"lineups: {exc}")
        ingestion_log.update_match(match_id, lineups_status="failed")

    try:
        three_sixty_result = download_three_sixty(match_id, force=force)
        ingestion_log.update_match(
            match_id,
            three_sixty_status=three_sixty_result.status,
            has_360=bool(three_sixty_result.has_data),
            three_sixty_file_path=_path_text(three_sixty_result.path),
        )
    except Exception as exc:
        errors.append(f"three-sixty: {exc}")
        ingestion_log.update_match(
            match_id,
            three_sixty_status="failed",
            has_360=False,
        )

    ingestion_log.update_match(
        match_id,
        error_message="; ".join(errors) if errors else None,
    )


def _path_text(path: Any) -> str | None:
    if path is None:
        return None
    return project_relative(path)


if __name__ == "__main__":
    main()
