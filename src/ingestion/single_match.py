"""Download and transform one StatsBomb Open Data match."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

import duckdb

from src.config import ANALYTICS_DB, RAW_MATCHES_DIR, ensure_directories, project_relative
from src.ingestion.download_360 import download_three_sixty
from src.ingestion.download_competitions import download_competitions
from src.ingestion.download_events import download_events
from src.ingestion.download_lineups import download_lineups
from src.ingestion.download_matches import (
    MATCH_FILE_RE,
    build_master_matches_index,
    competition_pairs,
    download_matches,
)
from src.ingestion.ingestion_log import IngestionLog, match_summary
from src.ingestion.utils import DownloadResult, as_int, coerce_records, count_records, read_json
from src.transform.build_duckdb import refresh_global_dimensions, transform_match
from src.transform.schema import create_schema, create_views


@dataclass(frozen=True)
class MatchDownloadProgress:
    """One observable step in the single-match ingestion flow."""

    stage: str
    progress: float
    details: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class SingleMatchDownloadResult:
    """Result displayed by the ingestion page after a successful run."""

    match_id: int
    home_team: str | None
    away_team: str | None
    events_status: str
    events_rows: int
    lineups_status: str
    lineups_rows: int
    three_sixty_status: str
    three_sixty_rows: int
    transformation_status: str
    warnings: tuple[str, ...] = ()


class SingleMatchDownloadError(RuntimeError):
    """Expected ingestion failure with a stable code for bilingual UI messages."""

    def __init__(self, code: str, **details: Any) -> None:
        self.code = code
        self.details = details
        technical_message = str(details.get("cause") or details.get("message") or code)
        super().__init__(technical_message)


ProgressCallback = Callable[[MatchDownloadProgress], None]
_SINGLE_MATCH_LOCK = Lock()


def download_single_match(
    match_id: int,
    *,
    force: bool = False,
    progress_callback: ProgressCallback | None = None,
) -> SingleMatchDownloadResult:
    """Resolve, download, log and transform one public StatsBomb match."""

    if match_id <= 0:
        raise SingleMatchDownloadError("invalid_match_id", match_id=match_id)
    if not _SINGLE_MATCH_LOCK.acquire(blocking=False):
        raise SingleMatchDownloadError("download_in_progress", match_id=match_id)

    try:
        ensure_directories()
        _notify(progress_callback, "checking_local_catalog", 0.04, match_id=match_id)
        match_record = resolve_match_record(match_id, progress_callback=progress_callback)
        summary = match_summary(match_record)

        events_result: DownloadResult | None = None
        lineups_result: DownloadResult | None = None
        three_sixty_result: DownloadResult | None = None
        warnings: list[str] = []

        with IngestionLog() as ingestion_log:
            resolved_match_id = ingestion_log.ensure_match(match_record)
            ingestion_log.start_attempt(resolved_match_id)

            _notify(progress_callback, "downloading_events", 0.48, match_id=match_id)
            try:
                events_result = download_events(match_id, force=force)
                ingestion_log.update_match(
                    match_id,
                    events_status=events_result.status,
                    events_rows=events_result.rows,
                    event_file_path=_path_text(events_result.path),
                )
                _notify(
                    progress_callback,
                    "events_ready",
                    0.62,
                    status=events_result.status,
                    rows=int(events_result.rows or 0),
                )
            except Exception as exc:
                ingestion_log.update_match(match_id, events_status="failed", error_message=f"events: {exc}")
                _notify(progress_callback, "events_failed", 0.62, cause=str(exc))
                raise SingleMatchDownloadError("events_failed", match_id=match_id, cause=str(exc)) from exc

            _notify(progress_callback, "downloading_lineups", 0.65, match_id=match_id)
            try:
                lineups_result = download_lineups(match_id, force=force)
                ingestion_log.update_match(
                    match_id,
                    lineups_status=lineups_result.status,
                    lineup_file_path=_path_text(lineups_result.path),
                )
                _notify(
                    progress_callback,
                    "lineups_ready",
                    0.73,
                    status=lineups_result.status,
                    rows=int(lineups_result.rows or 0),
                )
            except Exception as exc:
                warning = f"lineups: {exc}"
                warnings.append(warning)
                ingestion_log.update_match(match_id, lineups_status="failed", error_message=warning)
                _notify(progress_callback, "lineups_failed", 0.73, cause=str(exc))

            _notify(progress_callback, "downloading_three_sixty", 0.76, match_id=match_id)
            try:
                three_sixty_result = download_three_sixty(match_id, force=force)
                ingestion_log.update_match(
                    match_id,
                    three_sixty_status=three_sixty_result.status,
                    has_360=bool(three_sixty_result.has_data),
                    three_sixty_file_path=_path_text(three_sixty_result.path),
                )
                _notify(
                    progress_callback,
                    "three_sixty_ready",
                    0.83,
                    status=three_sixty_result.status,
                    rows=count_records(three_sixty_result.data),
                )
            except Exception as exc:
                warning = f"three-sixty: {exc}"
                warnings.append(warning)
                ingestion_log.update_match(
                    match_id,
                    three_sixty_status="failed",
                    has_360=False,
                    error_message="; ".join(warnings),
                )
                _notify(progress_callback, "three_sixty_failed", 0.83, cause=str(exc))

            _notify(progress_callback, "transforming", 0.88, match_id=match_id)
            try:
                transformation = _transform_downloaded_match(match_id)
            except Exception as exc:
                ingestion_log.update_match(match_id, error_message=f"transformation: {exc}")
                raise SingleMatchDownloadError(
                    "transformation_failed",
                    match_id=match_id,
                    cause=str(exc),
                ) from exc
            if transformation.get("status") != "transformed":
                cause = str(transformation.get("error_message") or "Unknown transformation error")
                ingestion_log.update_match(match_id, error_message=cause)
                raise SingleMatchDownloadError("transformation_failed", match_id=match_id, cause=cause)

            ingestion_log.update_match(
                match_id,
                transformed_at=datetime.now(timezone.utc),
                error_message="; ".join(warnings) if warnings else None,
            )

        if events_result is None:
            raise SingleMatchDownloadError("events_failed", match_id=match_id)

        result = SingleMatchDownloadResult(
            match_id=match_id,
            home_team=summary.get("home_team"),
            away_team=summary.get("away_team"),
            events_status=events_result.status,
            events_rows=int(events_result.rows or 0),
            lineups_status=lineups_result.status if lineups_result else "failed",
            lineups_rows=int(lineups_result.rows or 0) if lineups_result else 0,
            three_sixty_status=three_sixty_result.status if three_sixty_result else "failed",
            three_sixty_rows=count_records(three_sixty_result.data) if three_sixty_result else 0,
            transformation_status=str(transformation["status"]),
            warnings=tuple(warnings),
        )
        _notify(progress_callback, "completed", 1.0, match_id=match_id)
        return result
    finally:
        _SINGLE_MATCH_LOCK.release()


def resolve_match_record(
    match_id: int,
    *,
    progress_callback: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Find match metadata locally or refresh the public competition catalog."""

    local_record = find_local_match_record(match_id)
    if local_record is not None:
        _notify(progress_callback, "building_match_index", 0.42, match_id=match_id)
        build_master_matches_index()
        _notify(progress_callback, "match_found", 0.45, match_id=match_id, source="local")
        return local_record

    _notify(progress_callback, "loading_catalog", 0.1, match_id=match_id)
    try:
        competitions = download_competitions(force=True)
        pairs = competition_pairs(competitions.data)
    except Exception as exc:
        raise SingleMatchDownloadError("catalog_failed", match_id=match_id, cause=str(exc)) from exc

    if not pairs:
        raise SingleMatchDownloadError("empty_catalog", match_id=match_id)

    refresh_pairs: list[tuple[int, int]] = []
    for index, (competition_id, season_id) in enumerate(pairs, start=1):
        _notify(
            progress_callback,
            "scanning_catalog",
            0.12 + (0.18 * index / len(pairs)),
            current=index,
            total=len(pairs),
        )
        try:
            result = download_matches(competition_id, season_id, force=False)
        except Exception:
            refresh_pairs.append((competition_id, season_id))
            continue
        if result.status == "skipped_existing":
            refresh_pairs.append((competition_id, season_id))
            continue
        match_record = _find_match_in_data(result.data, match_id, competition_id, season_id)
        if match_record is not None:
            return _finish_match_resolution(match_record, match_id, progress_callback, source="catalog")

    refresh_failures: list[str] = []
    if refresh_pairs:
        total_refresh = len(refresh_pairs)
        for index, (competition_id, season_id) in enumerate(refresh_pairs, start=1):
            _notify(
                progress_callback,
                "refreshing_catalog",
                0.3 + (0.12 * index / total_refresh),
                current=index,
                total=total_refresh,
            )
            try:
                result = download_matches(competition_id, season_id, force=True)
            except Exception as exc:
                refresh_failures.append(str(exc))
                continue
            match_record = _find_match_in_data(result.data, match_id, competition_id, season_id)
            if match_record is not None:
                return _finish_match_resolution(match_record, match_id, progress_callback, source="catalog")

    if refresh_failures:
        raise SingleMatchDownloadError(
            "catalog_incomplete",
            match_id=match_id,
            failed_pairs=len(refresh_failures),
            cause=refresh_failures[-1],
        )
    raise SingleMatchDownloadError("match_not_found", match_id=match_id)


def find_local_match_record(match_id: int, raw_matches_dir: Path = RAW_MATCHES_DIR) -> dict[str, Any] | None:
    """Return one raw match record from the local StatsBomb catalog."""

    for path in sorted(raw_matches_dir.glob("competition-*.season-*.json")):
        path_match = MATCH_FILE_RE.search(path.name)
        if path_match is None:
            continue
        competition_id = int(path_match.group("competition_id"))
        season_id = int(path_match.group("season_id"))
        record = _find_match_in_data(read_json(path), match_id, competition_id, season_id)
        if record is not None:
            return record
    return None


def _find_match_in_data(
    data: Any,
    match_id: int,
    competition_id: int,
    season_id: int,
) -> dict[str, Any] | None:
    for record in coerce_records(data):
        if as_int(record.get("match_id")) == match_id:
            return _prepare_match_record(record, competition_id, season_id)
    return None


def _prepare_match_record(record: dict[str, Any], competition_id: int, season_id: int) -> dict[str, Any]:
    prepared = dict(record)
    competition = prepared.get("competition") if isinstance(prepared.get("competition"), dict) else {}
    season = prepared.get("season") if isinstance(prepared.get("season"), dict) else {}
    home_team = prepared.get("home_team") if isinstance(prepared.get("home_team"), dict) else {}
    away_team = prepared.get("away_team") if isinstance(prepared.get("away_team"), dict) else {}

    prepared.setdefault("competition_id", as_int(competition.get("competition_id")) or competition_id)
    prepared.setdefault("season_id", as_int(season.get("season_id")) or season_id)
    prepared.setdefault(
        "home_team_home_team_name",
        home_team.get("home_team_name") or home_team.get("team_name") or home_team.get("name"),
    )
    prepared.setdefault(
        "away_team_away_team_name",
        away_team.get("away_team_name") or away_team.get("team_name") or away_team.get("name"),
    )
    return prepared


def _finish_match_resolution(
    match_record: dict[str, Any],
    match_id: int,
    progress_callback: ProgressCallback | None,
    *,
    source: str,
) -> dict[str, Any]:
    _notify(progress_callback, "building_match_index", 0.42, match_id=match_id)
    build_master_matches_index()
    _notify(progress_callback, "match_found", 0.45, match_id=match_id, source=source)
    return match_record


def _transform_downloaded_match(match_id: int) -> dict[str, Any]:
    connection = duckdb.connect(str(ANALYTICS_DB))
    try:
        create_schema(connection)
        refresh_global_dimensions(connection)
        result = transform_match(connection, match_id=match_id, force=True)
        create_views(connection)
        return result
    finally:
        connection.close()


def _notify(callback: ProgressCallback | None, stage: str, progress: float, **details: Any) -> None:
    if callback is None:
        return
    callback(MatchDownloadProgress(stage=stage, progress=max(0.0, min(progress, 1.0)), details=details))


def _path_text(path: Path | None) -> str | None:
    return project_relative(path) if path is not None else None
