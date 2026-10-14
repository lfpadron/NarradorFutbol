from __future__ import annotations

import io
import json
from email.message import Message
from types import SimpleNamespace
from urllib.error import HTTPError, URLError

import pytest

from src.security import guest_otp, storage
from src.security.guest_otp import GuestAccessError, send_guest_token, verify_guest_token
from src.security.models import ROLE_ADMIN, ROLE_ANALYST, ROLE_GUEST


@pytest.fixture
def otp(tmp_path, monkeypatch):
    monkeypatch.setattr(storage, "SECURITY_DB_PATH", tmp_path / "otp.sqlite")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "")
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")
    storage.initialize_security()
    clock = SimpleNamespace(now=1000.0)
    monkeypatch.setattr(guest_otp, "time", SimpleNamespace(time=lambda: clock.now))
    calls = []

    def provider(endpoint, payload):
        calls.append((endpoint, payload))
        return {
            "user": {"id": "verified-user", "email": payload["email"], "email_confirmed_at": "2026-10-14T00:00:00Z"}
        }

    monkeypatch.setattr(guest_otp, "_auth_request", provider)
    return clock, calls


def test_guest_is_created_only_after_email_verification_and_token_is_single_use(otp):
    clock, calls = otp
    send_guest_token(" NEW@EXAMPLE.COM ")
    assert storage.get_user_by_email("new@example.com") is None
    user = verify_guest_token("new@example.com", "012345")
    assert user["role"] == ROLE_GUEST and user["is_active"] and user["name"] == ""
    assert calls == [
        ("otp", {"email": "new@example.com", "create_user": True}),
        ("verify", {"email": "new@example.com", "token": "012345", "type": "email"}),
    ]
    with pytest.raises(GuestAccessError):
        verify_guest_token("new@example.com", "012345")
    with storage.get_connection() as conn:
        assert conn.execute("SELECT password_hash FROM users").fetchone()[0] == ""


def test_returning_guest_keeps_name_role_and_account(otp):
    guest = storage.provision_verified_guest("guest@example.com")
    storage.update_own_name("Nombre", actor=guest)
    send_guest_token(guest["email"])
    user = verify_guest_token(guest["email"], "123456")
    assert user["id"] == guest["id"]
    assert user["name"] == "Nombre"


def test_token_expires_at_exactly_one_hour(otp):
    clock, calls = otp
    send_guest_token("guest@example.com")
    clock.now += 3600
    with pytest.raises(GuestAccessError, match="caducado"):
        verify_guest_token("guest@example.com", "123456")
    assert len(calls) == 1


def test_token_can_be_verified_just_before_expiry(otp):
    clock, calls = otp
    send_guest_token("guest@example.com")
    clock.now += 3599
    assert verify_guest_token("guest@example.com", "123456")


def test_resend_cooldown_is_shared_across_sessions(otp):
    clock, calls = otp
    send_guest_token("guest@example.com")
    clock.now += 59
    with pytest.raises(GuestAccessError, match="60 segundos"):
        send_guest_token("GUEST@example.com")
    clock.now += 1
    send_guest_token("guest@example.com")
    assert len(calls) == 2


@pytest.mark.parametrize("token", ["", "12345", "1234567", "12ab56", "１２３４５６"])
def test_invalid_token_format_never_calls_provider(otp, token):
    clock, calls = otp
    with pytest.raises(GuestAccessError, match="6 dígitos"):
        verify_guest_token("guest@example.com", token)
    assert calls == []


@pytest.mark.parametrize("role,active", [(ROLE_ADMIN, True), (ROLE_ANALYST, True), (ROLE_GUEST, False)])
def test_otp_cannot_bypass_staff_password_or_disabled_account(otp, role, active):
    clock, calls = otp
    storage.ensure_user("blocked@example.com", "Password123!", role, is_active=active)
    with pytest.raises(GuestAccessError):
        send_guest_token("blocked@example.com")
    with pytest.raises(GuestAccessError):
        verify_guest_token("blocked@example.com", "123456")
    assert calls == []


def test_disable_after_send_prevents_login(otp):
    admin = storage.ensure_user("admin@example.com", "Password123!", ROLE_ADMIN)
    guest = storage.provision_verified_guest("guest@example.com")
    send_guest_token(guest["email"])
    storage.set_user_active(guest["email"], False, actor=admin)
    with pytest.raises(GuestAccessError):
        verify_guest_token(guest["email"], "123456")


def test_disable_during_provider_verification_prevents_login(otp, monkeypatch):
    admin = storage.ensure_user("admin@example.com", "Password123!", ROLE_ADMIN)
    guest = storage.provision_verified_guest("guest@example.com")
    send_guest_token(guest["email"])

    def provider(endpoint, payload):
        storage.set_user_active(guest["email"], False, actor=admin)
        return {"user": {"id": "id", "email": guest["email"], "email_confirmed_at": "now"}}

    monkeypatch.setattr(guest_otp, "_auth_request", provider)
    with pytest.raises(ValueError, match="no está disponible"):
        verify_guest_token(guest["email"], "123456")


@pytest.mark.parametrize(
    "identity",
    [
        {},
        {"id": "id", "email": "guest@example.com"},
        {"id": "id", "email": "wrong@example.com", "email_confirmed_at": "now"},
    ],
)
def test_provider_must_confirm_exact_email(otp, monkeypatch, identity):
    send_guest_token("guest@example.com")
    monkeypatch.setattr(guest_otp, "_auth_request", lambda *args: {"user": identity})
    with pytest.raises(GuestAccessError, match="verificar el correo"):
        verify_guest_token("guest@example.com", "123456")
    assert storage.user_count() == 0


def test_invalid_attempts_are_limited_persistently(otp, monkeypatch):
    send_guest_token("guest@example.com")

    def invalid(*args):
        raise GuestAccessError("Token inválido")

    monkeypatch.setattr(guest_otp, "_auth_request", invalid)
    for _ in range(5):
        with pytest.raises(GuestAccessError, match="inválido"):
            verify_guest_token("guest@example.com", "123456")
    with pytest.raises(GuestAccessError, match="agotaron"):
        verify_guest_token("guest@example.com", "123456")


def test_transport_sends_supabase_api_key_and_expected_json(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co/")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "sb_publishable_test")

    def transport(request, timeout):
        assert request.full_url == "https://project.supabase.co/auth/v1/otp"
        assert request.get_header("Apikey") == "sb_publishable_test"
        assert json.loads(request.data) == {"email": "guest@example.com", "create_user": True}
        assert timeout == 15
        return io.BytesIO(b"{}")

    monkeypatch.setattr(guest_otp, "urlopen", transport)
    assert guest_otp._auth_request("otp", {"email": "guest@example.com", "create_user": True}) == {}


@pytest.mark.parametrize(
    "error,message",
    [
        (HTTPError("https://test", 429, "secret", Message(), None), "límite"),
        (HTTPError("https://test", 403, "secret", Message(), None), "inválido"),
        (URLError("secret"), "conectar"),
    ],
)
def test_transport_errors_do_not_leak_secrets(monkeypatch, error, message):
    monkeypatch.setenv("SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setenv("SUPABASE_PUBLISHABLE_KEY", "secret")

    def transport(*args, **kwargs):
        raise error

    monkeypatch.setattr(guest_otp, "urlopen", transport)
    with pytest.raises(GuestAccessError, match=message) as exc:
        guest_otp._auth_request("verify", {})
    assert "secret" not in str(exc.value)


def test_missing_configuration_does_not_create_accounts_or_requests(otp, monkeypatch):
    monkeypatch.delenv("SUPABASE_URL")
    assert not guest_otp.is_configured()
    with pytest.raises(GuestAccessError, match="configurado"):
        send_guest_token("guest@example.com")
    assert storage.user_count() == 0


def test_streamlit_guest_login_redirect_and_permissions(otp):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file("app/streamlit_app.py", default_timeout=15).run()
    app.text_input(key="guest_email").set_value("guest@example.com")
    next(button for button in app.button if button.label == "Enviar token").click().run()
    assert not app.exception
    app.text_input(key="guest_token").set_value("012345")
    next(button for button in app.button if button.label == "Entrar").click().run()
    assert not app.exception
    assert app.title[0].value == "Mi usuario"
    labels = {button.label for button in app.button}
    assert "Usuarios" not in labels and "Ingesta" not in labels
    assert "Partidos" in labels


def test_streamlit_guest_can_use_requested_token_in_a_new_browser_session(otp):
    from streamlit.testing.v1 import AppTest

    send_guest_token("guest@example.com")
    app = AppTest.from_file("app/streamlit_app.py", default_timeout=15).run()
    app.text_input(key="guest_email").set_value("guest@example.com")
    app.text_input(key="guest_token").set_value("012345")
    next(button for button in app.button if button.label == "Entrar").click().run()
    assert not app.exception
    assert app.title[0].value == "Mi usuario"
