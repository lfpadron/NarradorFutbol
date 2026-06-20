"""Project configuration and filesystem paths."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")


def _resolve_data_dir() -> Path:
    configured = os.getenv("NARRADOR_DATA_DIR", "data")
    path = Path(configured)
    if not path.is_absolute():
        path = PROJECT_ROOT / path
    return path


DATA_DIR = _resolve_data_dir()
RAW_DIR = DATA_DIR / "raw"
METADATA_DIR = DATA_DIR / "metadata"
ANALYTICS_DIR = DATA_DIR / "analytics"
ANALYTICS_EXPORTS_DIR = ANALYTICS_DIR / "exports"

RAW_COMPETITIONS_DIR = RAW_DIR / "competitions"
RAW_MATCHES_DIR = RAW_DIR / "matches"
RAW_EVENTS_DIR = RAW_DIR / "events"
RAW_LINEUPS_DIR = RAW_DIR / "lineups"
RAW_THREE_SIXTY_DIR = RAW_DIR / "three-sixty"

COMPETITIONS_FILE = RAW_COMPETITIONS_DIR / "competitions.json"
ALL_MATCHES_CSV = METADATA_DIR / "all_matches.csv"
ALL_MATCHES_PARQUET = METADATA_DIR / "all_matches.parquet"
INGESTION_LOG_DB = METADATA_DIR / "ingestion_log.duckdb"
ANALYTICS_DB = ANALYTICS_DIR / "statsbomb.duckdb"

RAW_DIRECTORIES = (
    RAW_COMPETITIONS_DIR,
    RAW_MATCHES_DIR,
    RAW_EVENTS_DIR,
    RAW_LINEUPS_DIR,
    RAW_THREE_SIXTY_DIR,
)


def ensure_directories() -> None:
    """Create the project data directories used by ingestion."""

    for directory in (*RAW_DIRECTORIES, METADATA_DIR, ANALYTICS_DIR, ANALYTICS_EXPORTS_DIR):
        directory.mkdir(parents=True, exist_ok=True)


def project_relative(path: Path) -> str:
    """Return a stable project-relative path for log records."""

    try:
        return path.resolve().relative_to(PROJECT_ROOT).as_posix()
    except ValueError:
        return path.resolve().as_posix()
