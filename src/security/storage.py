"""Persistent accounts, migration and transactional user administration."""

from __future__ import annotations

import os
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterator

from src.config import SECURITY_DB_PATH
from src.security.auth import hash_password, public_user, verify_password
from src.security.models import ROLE_ADMIN, ROLE_ANALYST, ROLE_GUEST, VALID_ROLES

PAGE_SIZE = 20
MAX_ACTIVE_ADMINS = 3
USERS_SQL = """
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    email TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    password_hash TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK(role IN ('admin', 'analyst', 'guest')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK(is_active IN (0, 1)),
    session_version INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
)
"""


@contextmanager
def get_connection(db_path: Path | None = None) -> Iterator[sqlite3.Connection]:
    path = db_path or SECURITY_DB_PATH
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path, timeout=15)
    connection.row_factory = sqlite3.Row
    try:
        with connection:
            yield connection
    finally:
        connection.close()


def initialize_security(db_path: Path | None = None) -> None:
    with get_connection(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        connection.execute(USERS_SQL)
        columns = {row["name"] for row in connection.execute("PRAGMA table_info(users)")}
        if "name" not in columns:
            # Extend the original role CHECK while preserving user IDs and password hashes.
            connection.execute("ALTER TABLE users RENAME TO users_v1")
            connection.execute(USERS_SQL)
            connection.execute("""
                INSERT INTO users (id, email, password_hash, role, is_active, created_at, updated_at)
                SELECT id, email, password_hash, role, is_active, created_at, updated_at FROM users_v1
            """)
            connection.execute("DROP TABLE users_v1")
        connection.execute("""
            CREATE TABLE IF NOT EXISTS invitations (
                id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT NOT NULL,
                token_hash TEXT UNIQUE NOT NULL,
                role TEXT NOT NULL CHECK(role IN ('admin', 'analyst')),
                invited_by TEXT NOT NULL, expires_at TEXT NOT NULL,
                accepted_at TEXT, created_at TEXT NOT NULL
            )
        """)
        connection.execute("""
            CREATE TABLE IF NOT EXISTS guest_otp_requests (
                email TEXT PRIMARY KEY, requested_at REAL NOT NULL,
                expires_at REAL NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
                request_id TEXT NOT NULL
            )
        """)
        # Protect legacy/internal writers and concurrent connections, too.
        connection.execute("""
            CREATE TRIGGER IF NOT EXISTS max_active_admins_insert BEFORE INSERT ON users
            WHEN NEW.role = 'admin' AND NEW.is_active = 1
              AND (SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1) >= 3
            BEGIN SELECT RAISE(ABORT, 'No puede haber más de tres administradores activos.'); END
        """)
        connection.execute("""
            CREATE TRIGGER IF NOT EXISTS max_active_admins_update BEFORE UPDATE ON users
            WHEN NEW.role = 'admin' AND NEW.is_active = 1
              AND NOT (OLD.role = 'admin' AND OLD.is_active = 1)
              AND (SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1) >= 3
            BEGIN SELECT RAISE(ABORT, 'No puede haber más de tres administradores activos.'); END
        """)
    ensure_seed_admins(db_path)


def ensure_seed_admins(db_path: Path | None = None) -> None:
    password = os.getenv("SEED_ADMIN_PASSWORD", "")
    if not password:
        return
    for key in ("SEED_ADMIN_EMAIL_1", "SEED_ADMIN_EMAIL_2"):
        email = os.getenv(key, "").strip()
        if not email:
            continue
        try:
            ensure_user(email, password, ROLE_ADMIN, db_path=db_path)
        except ValueError:
            # A full roster must not prevent existing accounts signing in.
            continue


def _insert_user(
    connection: sqlite3.Connection, email: str, password_hash: str, role: str, is_active: bool, name: str = ""
) -> dict[str, Any]:
    _check_admin_limit(connection, role, is_active)
    now = _now()
    connection.execute(
        """INSERT INTO users (email, name, password_hash, role, is_active, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (email, name, password_hash, role, int(is_active), now, now),
    )
    return public_user(dict(connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()))


def ensure_user(
    email: str, password: str, role: str, db_path: Path | None = None, is_active: bool = True
) -> dict[str, Any]:
    """Bootstrap a missing account; never undo an administrator's later changes."""
    email = validate_email(email)
    _validate_role(role)
    with get_connection(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row is not None:
            return public_user(dict(row))
        return _insert_user(connection, email, hash_password(password), role, is_active)


def create_user(
    email: str, name: str, password: str, role: str, is_active: bool, *, actor: dict, db_path: Path | None = None
) -> dict[str, Any]:
    email = validate_email(email)
    name = validate_name(name, required=True)
    validate_password(password)
    _validate_role(role)
    with get_connection(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _require_admin(connection, actor)
        if connection.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise ValueError("Ya existe un usuario con ese correo.")
        return _insert_user(connection, email, hash_password(password), role, is_active, name)


def authenticate_user(email: str, password: str, db_path: Path | None = None) -> dict[str, Any] | None:
    row = _get_user_row(normalize_email(email), db_path)
    if row is None or not row["is_active"] or row["role"] not in {ROLE_ADMIN, ROLE_ANALYST}:
        return None
    if not verify_password(password, row["password_hash"]):
        return None
    return public_user(dict(row))


def create_user_from_invitation(email: str, password: str, role: str, db_path: Path | None = None) -> dict[str, Any]:
    email = validate_email(email)
    validate_password(password)
    _validate_role(role)
    with get_connection(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        if connection.execute("SELECT 1 FROM users WHERE email = ?", (email,)).fetchone():
            raise ValueError("Ya existe un usuario con ese correo. Contacta al administrador.")
        return _insert_user(connection, email, hash_password(password), role, True)


def provision_verified_guest(email: str, db_path: Path | None = None) -> dict[str, Any]:
    """Only after OTP verification; never promotes or reactivates accounts."""
    email = validate_email(email)
    with get_connection(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()
        if row is not None:
            if not row["is_active"] or row["role"] != ROLE_GUEST:
                raise ValueError("El acceso de invitado no está disponible para este correo.")
            return public_user(dict(row))
        return _insert_user(connection, email, "", ROLE_GUEST, True)


def get_user_by_email(email: str, db_path: Path | None = None) -> dict[str, Any] | None:
    row = _get_user_row(normalize_email(email), db_path)
    return public_user(dict(row)) if row is not None else None


def validate_session(user: dict | None, db_path: Path | None = None) -> dict[str, Any] | None:
    if not user:
        return None
    current = get_user_by_email(user.get("email", ""), db_path)
    if (
        current
        and current["is_active"]
        and current["id"] == user.get("id")
        and current["session_version"] == user.get("session_version")
        and current["role"] in VALID_ROLES
    ):
        return current
    return None


def list_users(db_path: Path | None = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as connection:
        rows = connection.execute("SELECT * FROM users ORDER BY email").fetchall()
    return [public_user(dict(row)) for row in rows]


def search_users(
    query: str = "", role: str | None = None, page: int = 1, *, actor: dict, db_path: Path | None = None
) -> tuple[list[dict[str, Any]], int]:
    if role:
        _validate_role(role)
    query = query.strip().casefold()
    with get_connection(db_path) as connection:
        _require_admin(connection, actor)
        connection.create_function("casefold", 1, lambda value: str(value or "").casefold())
        where = "WHERE (instr(casefold(email), ?) > 0 OR instr(casefold(name), ?) > 0)"
        params: list[Any] = [query, query]
        if role:
            where += " AND role = ?"
            params.append(role)
        total = int(connection.execute(f"SELECT COUNT(*) FROM users {where}", params).fetchone()[0])
        page = min(max(1, page), max(1, (total + PAGE_SIZE - 1) // PAGE_SIZE))
        rows = connection.execute(
            f"SELECT * FROM users {where} ORDER BY email, id LIMIT ? OFFSET ?",
            [*params, PAGE_SIZE, (page - 1) * PAGE_SIZE],
        ).fetchall()
    return [public_user(dict(row)) for row in rows], total


def user_search_options(*, actor: dict, db_path: Path | None = None) -> list[str]:
    with get_connection(db_path) as connection:
        _require_admin(connection, actor)
        rows = connection.execute("SELECT email, name FROM users ORDER BY email").fetchall()
    return sorted({str(value) for row in rows for value in row if value}, key=str.casefold)


def set_user_active(email: str, is_active: bool, db_path: Path | None = None, *, actor: dict) -> None:
    with get_connection(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _require_admin(connection, actor)
        row = _require_user(connection, email)
        _check_admin_limit(connection, row["role"], is_active, row["id"])
        if bool(row["is_active"]) != is_active:
            connection.execute(
                "UPDATE users SET is_active = ?, session_version = session_version + 1, updated_at = ? WHERE id = ?",
                (int(is_active), _now(), row["id"]),
            )


def set_user_role(email: str, role: str, *, actor: dict, db_path: Path | None = None) -> None:
    _validate_role(role)
    with get_connection(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _require_admin(connection, actor)
        row = _require_user(connection, email)
        _check_admin_limit(connection, role, bool(row["is_active"]), row["id"])
        if row["role"] != role:
            connection.execute(
                "UPDATE users SET role = ?, session_version = session_version + 1, updated_at = ? WHERE id = ?",
                (role, _now(), row["id"]),
            )


def set_user_password(email: str, password: str, *, actor: dict, db_path: Path | None = None) -> None:
    validate_password(password)
    with get_connection(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        _require_admin(connection, actor)
        row = _require_user(connection, email)
        connection.execute(
            "UPDATE users SET password_hash = ?, session_version = session_version + 1, updated_at = ? WHERE id = ?",
            (hash_password(password), _now(), row["id"]),
        )


def change_own_password(
    current_password: str, new_password: str, *, actor: dict, db_path: Path | None = None
) -> dict[str, Any]:
    """Reauthenticate staff and revoke previous sessions while returning a renewed one."""
    with get_connection(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = _require_actor(connection, actor)
        if row["role"] not in {ROLE_ADMIN, ROLE_ANALYST}:
            raise ValueError("Los invitados no pueden actualizar su contraseña.")
        if not verify_password(current_password, row["password_hash"]):
            raise ValueError("La contraseña actual es incorrecta.")
        validate_password(new_password)
        connection.execute(
            "UPDATE users SET password_hash = ?, session_version = session_version + 1, updated_at = ? WHERE id = ?",
            (hash_password(new_password), _now(), row["id"]),
        )
        return public_user(dict(_require_user(connection, row["email"])))


def update_own_name(name: str, *, actor: dict, db_path: Path | None = None) -> dict[str, Any]:
    name = validate_name(name)
    with get_connection(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        row = _require_actor(connection, actor)
        connection.execute("UPDATE users SET name = ?, updated_at = ? WHERE id = ?", (name, _now(), row["id"]))
        updated = dict(row)
        updated["name"] = name
        return public_user(updated)


def user_count(db_path: Path | None = None) -> int:
    with get_connection(db_path) as connection:
        return int(connection.execute("SELECT COUNT(*) FROM users").fetchone()[0])


def normalize_email(email: str) -> str:
    return email.strip().lower()


def validate_email(email: str) -> str:
    email = normalize_email(email)
    if len(email) > 254 or not re.fullmatch(r"[^\s@]+@[^\s@.]+(?:\.[^\s@.]+)+", email):
        raise ValueError("Captura un correo válido.")
    return email


def validate_name(name: str, required: bool = False) -> str:
    name = name.strip()
    if required and not name:
        raise ValueError("El nombre es obligatorio.")
    if len(name) > 120:
        raise ValueError("El nombre puede tener hasta 120 caracteres.")
    return name


def validate_password(password: str) -> None:
    if len(password) < 10 or not password.strip():
        raise ValueError("La contraseña debe tener al menos 10 caracteres.")
    if len(password) > 1024:
        raise ValueError("La contraseña es demasiado larga.")


def _validate_role(role: str) -> None:
    if role not in VALID_ROLES:
        raise ValueError("Rol inválido.")


def _require_user(connection: sqlite3.Connection, email: str) -> sqlite3.Row:
    row = connection.execute("SELECT * FROM users WHERE email = ?", (normalize_email(email),)).fetchone()
    if row is None:
        raise ValueError("El usuario ya no existe.")
    return row


def _require_actor(connection: sqlite3.Connection, actor: dict) -> sqlite3.Row:
    row = _require_user(connection, actor.get("email", ""))
    if not row["is_active"] or row["id"] != actor.get("id") or row["session_version"] != actor.get("session_version"):
        raise ValueError("Tu sesión ya no está activa. Inicia sesión de nuevo.")
    return row


def _require_admin(connection: sqlite3.Connection, actor: dict) -> None:
    if _require_actor(connection, actor)["role"] != ROLE_ADMIN:
        raise ValueError("Solo un administrador puede gestionar usuarios.")


def _check_admin_limit(connection: sqlite3.Connection, role: str, active: bool, user_id: int = -1) -> None:
    if role == ROLE_ADMIN and active:
        count = connection.execute(
            "SELECT COUNT(*) FROM users WHERE role = 'admin' AND is_active = 1 AND id != ?", (user_id,)
        ).fetchone()[0]
        if count >= MAX_ACTIVE_ADMINS:
            raise ValueError("No puede haber más de tres administradores activos.")


def _get_user_row(email: str, db_path: Path | None = None) -> sqlite3.Row | None:
    with get_connection(db_path) as connection:
        return connection.execute("SELECT * FROM users WHERE email = ?", (email,)).fetchone()


def _now() -> str:
    return datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds")
