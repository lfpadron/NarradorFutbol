"""Security model constants."""

from __future__ import annotations

from dataclasses import dataclass

ROLE_ADMIN = "admin"
ROLE_ANALYST = "analyst"
VALID_ROLES = {ROLE_ADMIN, ROLE_ANALYST}


@dataclass(frozen=True)
class AuthUser:
    id: int
    email: str
    role: str
    is_active: bool
