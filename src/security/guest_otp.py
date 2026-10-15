"""Supabase email OTP, without shared SDK sessions or locally stored tokens."""

from __future__ import annotations

import json
import os
import re
import secrets
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from dotenv import dotenv_values

from src.config import PROJECT_ROOT
from src.security.models import ROLE_GUEST
from src.security.storage import (
    get_connection,
    get_user_by_email,
    normalize_email,
    provision_verified_guest,
    validate_email,
)

OTP_TTL_SECONDS = 3600
OTP_RESEND_SECONDS = 60
OTP_MAX_ATTEMPTS = 5
SUPABASE_ENV_PATH = PROJECT_ROOT / ".env"


class GuestAccessError(ValueError):
    """An actionable message safe to show without provider internals or credentials."""


def _config() -> tuple[str, str]:
    url = os.getenv("SUPABASE_URL", "").strip()
    key = (os.getenv("SUPABASE_PUBLISHABLE_KEY", "") or os.getenv("SUPABASE_ANON_KEY", "")).strip()
    if not url or not key:
        # Pick up parameters added after Streamlit started, without overwriting runtime settings.
        local = dotenv_values(SUPABASE_ENV_PATH)
        url = url or (local.get("SUPABASE_URL") or "").strip()
        key = key or (local.get("SUPABASE_PUBLISHABLE_KEY") or local.get("SUPABASE_ANON_KEY") or "").strip()
    url = url.rstrip("/")
    parsed = urlparse(url)
    if not key or parsed.scheme != "https" or not parsed.netloc or parsed.username or parsed.query or parsed.fragment:
        raise GuestAccessError("El acceso de invitados aún no está configurado. Contacta al organizador.")
    return url, key


def is_configured() -> bool:
    try:
        _config()
    except GuestAccessError:
        return False
    return True


def _auth_request(endpoint: str, payload: dict[str, Any]) -> dict[str, Any]:
    url, key = _config()
    request = Request(
        f"{url}/auth/v1/{endpoint}",
        data=json.dumps(payload).encode("utf-8"),
        headers={"apikey": key, "Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=15) as response:
            result = json.loads(response.read())
    except HTTPError as exc:
        if exc.code == 429:
            raise GuestAccessError(
                "Se alcanzó el límite de solicitudes. Espera unos minutos e inténtalo de nuevo."
            ) from None
        if endpoint == "verify" and exc.code in {400, 403, 422}:
            raise GuestAccessError(
                "El token es inválido o ha caducado. Revisa el código o solicita uno nuevo."
            ) from None
        raise GuestAccessError(
            "No se pudo completar el acceso por correo. Inténtalo más tarde o contacta al organizador."
        ) from None
    except (URLError, TimeoutError, OSError, ValueError):
        raise GuestAccessError("No se pudo conectar con el servicio de acceso. Inténtalo de nuevo.") from None
    if not isinstance(result, dict):
        raise GuestAccessError("El servicio de acceso devolvió una respuesta inesperada. Inténtalo de nuevo.")
    return result


def _check_guest(email: str, db_path: Path | None) -> None:
    user = get_user_by_email(email, db_path)
    if user and (not user["is_active"] or user["role"] != ROLE_GUEST):
        raise GuestAccessError(
            "El acceso de invitado no está disponible para este correo. "
            "Si tienes una cuenta de administrador o analista, usa tu contraseña."
        )


def send_guest_token(email: str, db_path: Path | None = None) -> None:
    email = validate_email(email)
    _config()
    _check_guest(email, db_path)
    now = time.time()
    request_id = secrets.token_urlsafe(24)
    with get_connection(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        previous = connection.execute("SELECT * FROM guest_otp_requests WHERE email = ?", (email,)).fetchone()
        if previous and now - previous["requested_at"] < OTP_RESEND_SECONDS:
            raise GuestAccessError("Espera 60 segundos antes de solicitar otro token.")
        connection.execute("DELETE FROM guest_otp_requests WHERE expires_at <= ?", (now,))
        connection.execute(
            """INSERT INTO guest_otp_requests (email, requested_at, expires_at, attempts, request_id)
               VALUES (?, ?, ?, 0, ?) ON CONFLICT(email) DO UPDATE SET
               requested_at = excluded.requested_at, expires_at = excluded.expires_at,
               attempts = 0, request_id = excluded.request_id""",
            (email, now, now + OTP_TTL_SECONDS, request_id),
        )
    try:
        _auth_request("otp", {"email": email, "create_user": True})
    except GuestAccessError:
        with get_connection(db_path) as connection:
            connection.execute("DELETE FROM guest_otp_requests WHERE email = ? AND request_id = ?", (email, request_id))
        raise


def verify_guest_token(email: str, token: str, db_path: Path | None = None) -> dict[str, Any]:
    email = validate_email(email)
    token = token.strip()
    if not re.fullmatch(r"[0-9]{6}", token):
        raise GuestAccessError("Captura el token de 6 dígitos que recibiste por correo.")
    _check_guest(email, db_path)
    with get_connection(db_path) as connection:
        connection.execute("BEGIN IMMEDIATE")
        pending = connection.execute("SELECT * FROM guest_otp_requests WHERE email = ?", (email,)).fetchone()
        if not pending or time.time() >= pending["expires_at"]:
            raise GuestAccessError("El token ha caducado o no se ha solicitado. Envía un token nuevo.")
        if pending["attempts"] >= OTP_MAX_ATTEMPTS:
            raise GuestAccessError("Se agotaron los intentos para este token. Solicita uno nuevo.")
        connection.execute("UPDATE guest_otp_requests SET attempts = attempts + 1 WHERE email = ?", (email,))
        request_id = pending["request_id"]
    result = _auth_request("verify", {"email": email, "token": token, "type": "email"})
    identity = result.get("user")
    if (
        not isinstance(identity, dict)
        or not identity.get("id")
        or not identity.get("email_confirmed_at")
        or normalize_email(str(identity.get("email", ""))) != email
    ):
        raise GuestAccessError("No se pudo verificar el correo. Solicita un token nuevo.")
    with get_connection(db_path) as connection:
        consumed = connection.execute(
            "DELETE FROM guest_otp_requests WHERE email = ? AND request_id = ? AND expires_at > ?",
            (email, request_id, time.time()),
        ).rowcount
    if consumed != 1:
        raise GuestAccessError("El token ya se utilizó, caducó o fue reemplazado. Solicita uno nuevo.")
    return provision_verified_guest(email, db_path)
