from __future__ import annotations

from pathlib import Path

import pytest

from src.security.auth import hash_password, verify_password
from src.security.invitations import accept_invitation, create_invitation
from src.security.models import ROLE_ADMIN, ROLE_ANALYST
from src.security.storage import authenticate_user, initialize_security, list_users


def test_password_hash_does_not_store_plain_text(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    password_hash = hash_password("super-secret-password")

    assert "super-secret-password" not in password_hash
    assert verify_password("super-secret-password", password_hash)
    assert not verify_password("wrong-password", password_hash)


def test_initialize_security_creates_seed_admins(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "security.sqlite"
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("SEED_ADMIN_EMAIL_1", "admin.one@example.com")
    monkeypatch.setenv("SEED_ADMIN_EMAIL_2", "admin.two@example.com")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "AdminPassword123!")

    initialize_security(db_path)

    users = list_users(db_path)
    assert {user["email"] for user in users} == {"admin.one@example.com", "admin.two@example.com"}
    assert all(user["role"] == ROLE_ADMIN for user in users)
    assert authenticate_user("admin.one@example.com", "AdminPassword123!", db_path)


def test_invitation_acceptance_creates_analyst(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    db_path = tmp_path / "security.sqlite"
    monkeypatch.setenv("APP_SECRET_KEY", "test-secret")
    monkeypatch.setenv("SEED_ADMIN_EMAIL_1", "admin@example.com")
    monkeypatch.setenv("SEED_ADMIN_EMAIL_2", "")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "AdminPassword123!")
    initialize_security(db_path)

    invitation = create_invitation(
        "analyst@example.com",
        invited_by="admin@example.com",
        role=ROLE_ANALYST,
        ttl_hours=1,
        db_path=db_path,
    )
    user = accept_invitation(invitation["token"], "AnalystPassword123!", db_path=db_path)

    assert user["email"] == "analyst@example.com"
    assert user["role"] == ROLE_ANALYST
    assert authenticate_user("analyst@example.com", "AnalystPassword123!", db_path)

    with pytest.raises(ValueError):
        accept_invitation(invitation["token"], "AnotherPassword123!", db_path=db_path)
