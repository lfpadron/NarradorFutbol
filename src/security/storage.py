"""SQLite storage for users and invitations."""

from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config import SECURITY_DB_PATH
from src.security.auth import hash_password, public_user, verify_password
from src.security.models import ROLE_ADMIN, VALID_ROLES

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'analyst')),
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS invitations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT NOT NULL,
    token_hash TEXT UNIQUE NOT NULL,
    role TEXT NOT NULL CHECK(role IN ('admin', 'analyst')),
    invited_by TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    accepted_at TEXT,
    created_at TEXT NOT NULL
);
"""


def get_connection(db_path: Path | None = None) -> sqlite3.Connection:
    path = db_path or SECURITY_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_security(db_path: Path | None = None) -> None:
    with get_connection(db_path) as connection:
        connection.executescript(SCHEMA_SQL)
    ensure_seed_admins(db_path)


def ensure_seed_admins(db_path: Path | None = None) -> None:
    admin_password = os.getenv("SEED_ADMIN_PASSWORD", "ChangeMe-v01!")
    for email in _seed_admin_emails():
        ensure_user(email, admin_password, ROLE_ADMIN, db_path=db_path)


def ensure_user(
    email: str,
    password: str,
    role: str,
    db_path: Path | None = None,
    is_active: bool = True,
) -> dict[str, Any]:
    clean_email = normalize_email(email)
    if role not in VALID_ROLES:
        raise ValueError(f"Rol inválido: {role}")
    now = _now()
    with get_connection(db_path) as connection:
        row = connection.execute("SELECT * FROM users WHERE email = ?", (clean_email,)).fetchone()
        if row is None:
            connection.execute(
                """
                INSERT INTO users (email, password_hash, role, is_active, created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (clean_email, hash_password(password), role, int(is_active), now, now),
            )
        else:
            connection.execute(
                """
                UPDATE users
                SET role = ?, is_active = 1, updated_at = ?
                WHERE email = ?
                """,
                (role, now, clean_email),
            )
    user = get_user_by_email(clean_email, db_path=db_path)
    if user is None:
        raise RuntimeError("No se pudo asegurar usuario.")
    return user


def authenticate_user(email: str, password: str, db_path: Path | None = None) -> dict[str, Any] | None:
    row = _get_user_row(normalize_email(email), db_path)
    if row is None or not bool(row["is_active"]):
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return public_user(dict(row))


def create_user_from_invitation(
    email: str,
    password: str,
    role: str,
    db_path: Path | None = None,
) -> dict[str, Any]:
    return ensure_user(email, password, role, db_path=db_path, is_active=True)


def get_user_by_email(email: str, db_path: Path | None = None) -> dict[str, Any] | None:
    row = _get_user_row(normalize_email(email), db_path)
    return public_user(dict(row)) if row is not None else None


def list_users(db_path: Path | None = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as connection:
        rows = connection.execute("""
            SELECT id, email, role, is_active, created_at, updated_at
            FROM users
            ORDER BY role, email
            """).fetchall()
    return [dict(row) for row in rows]


def set_user_active(email: str, is_active: bool, db_path: Path | None = None) -> None:
    with get_connection(db_path) as connection:
        connection.execute(
            "UPDATE users SET is_active = ?, updated_at = ? WHERE email = ?",
            (int(is_active), _now(), normalize_email(email)),
        )


def user_count(db_path: Path | None = None) -> int:
    with get_connection(db_path) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])


def normalize_email(email: str) -> str:
    return email.strip().lower()


def _get_user_row(email: str, db_path: Path | None = None) -> sqlite3.Row | None:
    with get_connection(db_path) as connection:
        return connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def _seed_admin_emails() -> list[str]:
    values = [
        os.getenv("SEED_ADMIN_EMAIL_1", "admin1@example.com"),
        os.getenv("SEED_ADMIN_EMAIL_2", "admin2@example.com"),
    ]
    return [normalize_email(value) for value in values if value.strip()]


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
