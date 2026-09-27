from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from src.ingestion import single_match
from src.ingestion.single_match import MatchDownloadProgress, SingleMatchDownloadError
from src.ingestion.utils import DownloadResult


def sample_match_record(match_id: int = 1234) -> dict[str, Any]:
    return {
        "match_id": match_id,
        "match_date": "2024-04-20",
        "competition": {"competition_id": 9, "competition_name": "Demo League"},
        "season": {"season_id": 281, "season_name": "2023/2024"},
        "home_team": {"home_team_id": 10, "home_team_name": "Red FC"},
        "away_team": {"away_team_id": 20, "away_team_name": "Blue FC"},
        "home_score": 2,
        "away_score": 1,
    }


def test_find_local_match_record_returns_prepared_metadata(tmp_path: Path) -> None:
    raw_matches_dir = tmp_path / "matches"
    raw_matches_dir.mkdir()
    path = raw_matches_dir / "competition-9.season-281.json"
    path.write_text(json.dumps([sample_match_record()]), encoding="utf-8")

    result = single_match.find_local_match_record(1234, raw_matches_dir=raw_matches_dir)

    assert result is not None
    assert result["competition_id"] == 9
    assert result["season_id"] == 281
    assert result["home_team_home_team_name"] == "Red FC"
    assert result["away_team_away_team_name"] == "Blue FC"


def test_download_single_match_downloads_payloads_and_transforms(monkeypatch: Any, tmp_path: Path) -> None:
    record = single_match._prepare_match_record(sample_match_record(), 9, 281)
    progress: list[MatchDownloadProgress] = []
    log_updates: list[dict[str, Any]] = []

    class FakeIngestionLog:
        def __enter__(self) -> "FakeIngestionLog":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def ensure_match(self, match_record: dict[str, Any]) -> int:
            assert match_record == record
            return 1234

        def start_attempt(self, match_id: int) -> None:
            assert match_id == 1234

        def update_match(self, match_id: int, **fields: Any) -> None:
            assert match_id == 1234
            log_updates.append(fields)

    monkeypatch.setattr(single_match, "ensure_directories", lambda: None)
    monkeypatch.setattr(single_match, "resolve_match_record", lambda *_args, **_kwargs: record)
    monkeypatch.setattr(single_match, "IngestionLog", FakeIngestionLog)
    monkeypatch.setattr(
        single_match,
        "download_events",
        lambda *_args, **_kwargs: DownloadResult(
            status="downloaded",
            path=tmp_path / "events.json",
            data=[{"id": "event-1"}],
            rows=1,
        ),
    )
    monkeypatch.setattr(
        single_match,
        "download_lineups",
        lambda *_args, **_kwargs: DownloadResult(
            status="downloaded",
            path=tmp_path / "lineups.json",
            data=[{"team_id": 10}, {"team_id": 20}],
            rows=2,
        ),
    )
    monkeypatch.setattr(
        single_match,
        "download_three_sixty",
        lambda *_args, **_kwargs: DownloadResult(
            status="not_available",
            path=None,
            data=None,
            has_data=False,
        ),
    )
    monkeypatch.setattr(
        single_match,
        "_transform_downloaded_match",
        lambda _match_id: {"status": "transformed", "events_rows": 1},
    )
    monkeypatch.setattr(single_match, "project_relative", lambda path: path.as_posix())

    result = single_match.download_single_match(1234, progress_callback=progress.append)

    assert result.match_id == 1234
    assert result.home_team == "Red FC"
    assert result.away_team == "Blue FC"
    assert result.events_rows == 1
    assert result.lineups_rows == 2
    assert result.three_sixty_status == "not_available"
    assert result.transformation_status == "transformed"
    assert progress[-1].stage == "completed"
    assert progress[-1].progress == 1.0
    assert any(update.get("events_status") == "downloaded" for update in log_updates)
    assert any(update.get("transformed_at") is not None for update in log_updates)


def test_resolve_match_record_distinguishes_incomplete_catalog(monkeypatch: Any) -> None:
    monkeypatch.setattr(single_match, "find_local_match_record", lambda _match_id: None)
    monkeypatch.setattr(
        single_match,
        "download_competitions",
        lambda **_kwargs: DownloadResult(
            status="downloaded",
            path=None,
            data=[{"competition_id": 9, "season_id": 281}],
            rows=1,
        ),
    )

    def fail_matches(*_args: Any, **_kwargs: Any) -> DownloadResult:
        raise RuntimeError("temporary catalog outage")

    monkeypatch.setattr(single_match, "download_matches", fail_matches)

    with pytest.raises(SingleMatchDownloadError) as error_info:
        single_match.resolve_match_record(1234)

    assert error_info.value.code == "catalog_incomplete"
    assert error_info.value.details["failed_pairs"] == 1
