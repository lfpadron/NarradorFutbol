"""Security model constants."""

from __future__ import annotations

from dataclasses import dataclass

ROLE_ADMIN = "admin"
ROLE_ANALYST = "analyst"
ROLE_GUEST = "guest"
VALID_ROLES = {ROLE_ADMIN, ROLE_ANALYST, ROLE_GUEST}
ROLE_LABELS = {ROLE_ADMIN: "Administrador", ROLE_ANALYST: "Analista", ROLE_GUEST: "Invitado"}


def can_access_page(role: str, page: str) -> bool:
    if role not in VALID_ROLES:
        return False
    if page == "Usuarios":
        return role == ROLE_ADMIN
    if page == "Ingesta":
        return role in {ROLE_ADMIN, ROLE_ANALYST}
    return page in {"Mi usuario", "Partidos", "Análisis", "Gráficas avanzadas", "Iniciar sesión"}


@dataclass(frozen=True)
class AuthUser:
    id: int
    email: str
    role: str
    is_active: bool
    name: str = ""
