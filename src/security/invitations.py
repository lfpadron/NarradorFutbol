"""Invitation token workflow."""

from __future__ import annotations

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from src.security.auth import get_app_secret
from src.security.models import ROLE_ANALYST, VALID_ROLES
from src.security.storage import (
    create_user_from_invitation,
    get_connection,
    get_user_by_email,
    normalize_email,
)


def create_invitation(
    email: str,
    invited_by: str,
    role: str = ROLE_ANALYST,
    ttl_hours: int | None = None,
    db_path: Path | None = None,
) -> dict[str, Any]:
    if role not in VALID_ROLES:
        raise ValueError(f"Rol inválido: {role}")
    clean_email = normalize_email(email)
    token = secrets.token_urlsafe(32)
    now = _now_datetime()
    ttl = ttl_hours if ttl_hours is not None else int(os.getenv("INVITATION_TTL_HOURS", "72"))
    expires_at = now + timedelta(hours=ttl)
    with get_connection(db_path) as connection:
        connection.execute(
            """
            INSERT INTO invitations (email, token_hash, role, invited_by, expires_at, accepted_at, created_at)
            VALUES (?, ?, ?, ?, ?, NULL, ?)
            """,
            (
                clean_email,
                hash_invitation_token(token),
                role,
                invited_by,
                _iso(expires_at),
                _iso(now),
            ),
        )
    return {
        "email": clean_email,
        "role": role,
        "token": token,
        "expires_at": _iso(expires_at),
    }


def accept_invitation(token: str, password: str, db_path: Path | None = None) -> dict[str, Any]:
    invitation = get_invitation_by_token(token, db_path=db_path)
    if invitation is None:
        raise ValueError("Token de invitación inválido.")
    if invitation.get("accepted_at"):
        raise ValueError("La invitación ya fue aceptada.")
    if _parse_iso(str(invitation["expires_at"])) < _now_datetime():
        raise ValueError("La invitación expiró.")

    existing = get_user_by_email(str(invitation["email"]), db_path=db_path)
    if existing is not None and existing.get("is_active"):
        raise ValueError("Ya existe un usuario activo con ese correo.")

    user = create_user_from_invitation(
        str(invitation["email"]),
        password,
        str(invitation["role"]),
        db_path=db_path,
    )
    with get_connection(db_path) as connection:
        connection.execute(
            "UPDATE invitations SET accepted_at = ? WHERE id = ?",
            (_iso(_now_datetime()), invitation["id"]),
        )
    return user


def get_invitation_by_token(token: str, db_path: Path | None = None) -> dict[str, Any] | None:
    with get_connection(db_path) as connection:
        row = connection.execute(
            "SELECT * FROM invitations WHERE token_hash = ?",
            (hash_invitation_token(token),),
        ).fetchone()
    return dict(row) if row is not None else None


def list_invitations(db_path: Path | None = None) -> list[dict[str, Any]]:
    with get_connection(db_path) as connection:
        rows = connection.execute("""
            SELECT id, email, role, invited_by, expires_at, accepted_at, created_at
            FROM invitations
            ORDER BY created_at DESC
            LIMIT 50
            """).fetchall()
    return [dict(row) for row in rows]


def hash_invitation_token(token: str) -> str:
    payload = f"{token}{get_app_secret()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _now_datetime() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _iso(value: datetime) -> str:
    return value.isoformat(timespec="seconds")


def _parse_iso(value: str) -> datetime:
    return datetime.fromisoformat(value)
