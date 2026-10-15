from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

from src.security import storage
from src.security.auth import hash_password
from src.security.models import ROLE_ADMIN, ROLE_ANALYST, ROLE_GUEST, can_access_page
from src.ui.navigation import visible_page_definitions


@pytest.fixture
def accounts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db = tmp_path / "accounts.sqlite"
    monkeypatch.setattr(storage, "SECURITY_DB_PATH", db)
    monkeypatch.setenv("APP_SECRET_KEY", "tests-only-secret")
    monkeypatch.setenv("SEED_ADMIN_EMAIL_1", "owner@example.com")
    monkeypatch.setenv("SEED_ADMIN_EMAIL_2", "")
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "TestPassword123!")
    storage.initialize_security()
    return storage.get_user_by_email("owner@example.com"), db


def test_migrate_original_database_preserves_accounts_and_invitations(tmp_path, monkeypatch):
    monkeypatch.setenv("SEED_ADMIN_PASSWORD", "")
    db = tmp_path / "old.sqlite"
    password_hash = hash_password("OriginalPassword!")
    with sqlite3.connect(db) as conn:
        conn.execute("""CREATE TABLE users (
            id INTEGER PRIMARY KEY AUTOINCREMENT, email TEXT UNIQUE NOT NULL, password_hash TEXT NOT NULL,
            role TEXT NOT NULL CHECK(role IN ('admin', 'analyst')), is_active INTEGER NOT NULL DEFAULT 1,
            created_at TEXT NOT NULL, updated_at TEXT NOT NULL)""")
        conn.execute(
            "INSERT INTO users VALUES (7, 'old@example.com', ?, 'analyst', 0, '2026-01-01', '2026-02-01')",
            (password_hash,),
        )
    storage.initialize_security(db)
    storage.initialize_security(db)
    with storage.get_connection(db) as conn:
        row = conn.execute("SELECT * FROM users").fetchone()
        assert row["id"] == 7
        assert row["password_hash"] == password_hash
        assert row["created_at"] == "2026-01-01"
        assert row["updated_at"] == "2026-02-01"
        assert row["is_active"] == 0
        assert row["name"] == ""
    assert storage.provision_verified_guest("guest@example.com", db)["role"] == ROLE_GUEST


def test_initialization_does_not_reactivate_or_promote_seed(accounts):
    admin, db = accounts
    other = storage.create_user("other@example.com", "Other", "Password123!", ROLE_ADMIN, True, actor=admin)
    storage.set_user_role(admin["email"], ROLE_ANALYST, actor=other)
    storage.set_user_active(admin["email"], False, actor=other)
    storage.initialize_security()
    current = storage.get_user_by_email(admin["email"])
    assert not current["is_active"]
    assert current["role"] == ROLE_ANALYST


def test_password_login_requires_existing_active_staff(accounts):
    admin, db = accounts
    assert storage.authenticate_user(" OWNER@EXAMPLE.COM ", "TestPassword123!")
    assert not storage.authenticate_user("missing@example.com", "TestPassword123!")
    assert not storage.authenticate_user(admin["email"], "wrong")
    user = storage.create_user("analyst@example.com", "Analyst", "Password123!", ROLE_ANALYST, False, actor=admin)
    assert not storage.authenticate_user(user["email"], "Password123!")
    storage.create_user("guest@example.com", "Guest", "Password123!", ROLE_GUEST, True, actor=admin)
    assert not storage.authenticate_user("guest@example.com", "Password123!")


def test_admin_cap_applies_to_creation_promotion_and_activation(accounts):
    admin, db = accounts
    for i in range(2):
        storage.create_user(f"admin{i}@example.com", "Admin", "Password123!", ROLE_ADMIN, True, actor=admin)
    with pytest.raises(ValueError, match="tres administradores"):
        storage.create_user("fourth@example.com", "Fourth", "Password123!", ROLE_ADMIN, True, actor=admin)
    fourth = storage.create_user("fourth@example.com", "Fourth", "Password123!", ROLE_ADMIN, False, actor=admin)
    with pytest.raises(ValueError, match="tres administradores"):
        storage.set_user_active(fourth["email"], True, actor=admin)
    analyst = storage.create_user("analyst@example.com", "Analyst", "Password123!", ROLE_ANALYST, True, actor=admin)
    with pytest.raises(ValueError, match="tres administradores"):
        storage.set_user_role(analyst["email"], ROLE_ADMIN, actor=admin)
    storage.set_user_active("admin0@example.com", False, actor=admin)
    storage.set_user_role(analyst["email"], ROLE_ADMIN, actor=admin)


def test_concurrent_admin_creation_cannot_exceed_cap(accounts):
    admin, db = accounts
    storage.create_user("second@example.com", "Second", "Password123!", ROLE_ADMIN, True, actor=admin)

    def create(i):
        try:
            storage.create_user(f"race{i}@example.com", "Race", "Password123!", ROLE_ADMIN, True, actor=admin)
            return True
        except ValueError:
            return False

    with ThreadPoolExecutor(max_workers=2) as pool:
        assert sorted(pool.map(create, range(2))) == [False, True]


def test_database_guard_also_protects_other_writers(accounts):
    admin, db = accounts
    for i in range(2):
        storage.ensure_user(f"admin{i}@example.com", "Password123!", ROLE_ADMIN)
    storage.provision_verified_guest("guest@example.com")
    with pytest.raises(sqlite3.IntegrityError, match="tres administradores"):
        with storage.get_connection() as conn:
            conn.execute("UPDATE users SET role='admin' WHERE email='guest@example.com'")


@pytest.mark.parametrize("role", [ROLE_ANALYST, ROLE_GUEST])
def test_non_admin_cannot_manage_users_even_with_forged_role(accounts, role):
    admin, db = accounts
    user = storage.create_user("member@example.com", "Member", "Password123!", role, True, actor=admin)
    user["role"] = ROLE_ADMIN
    for action in [
        lambda: storage.set_user_active(admin["email"], False, actor=user),
        lambda: storage.set_user_role(admin["email"], ROLE_GUEST, actor=user),
        lambda: storage.set_user_password(admin["email"], "Replacement123!", actor=user),
        lambda: storage.search_users(actor=user),
        lambda: storage.user_search_options(actor=user),
        lambda: storage.create_user("bad@example.com", "Bad", "Password123!", ROLE_ADMIN, True, actor=user),
    ]:
        with pytest.raises(ValueError, match="administrador"):
            action()


def test_sessions_revoked_on_disable_role_and_password_changes(accounts):
    admin, db = accounts
    user = storage.create_user("member@example.com", "Member", "Password123!", ROLE_ANALYST, True, actor=admin)
    assert storage.validate_session(user)
    storage.set_user_active(user["email"], False, actor=admin)
    storage.set_user_active(user["email"], True, actor=admin)
    assert storage.validate_session(user) is None
    user = storage.authenticate_user(user["email"], "Password123!")
    storage.set_user_password(user["email"], "Replacement123!", actor=admin)
    assert storage.validate_session(user) is None
    assert storage.authenticate_user(user["email"], "Password123!") is None
    user = storage.authenticate_user(user["email"], "Replacement123!")
    storage.set_user_role(user["email"], ROLE_GUEST, actor=admin)
    assert storage.validate_session(user) is None


@pytest.mark.parametrize("role", [ROLE_ADMIN, ROLE_ANALYST])
def test_staff_change_own_password_requires_reauthentication_and_renews_session(accounts, role):
    admin, db = accounts
    user = storage.create_user("member@example.com", "Member", "Password123!", role, True, actor=admin)
    updated = storage.change_own_password("Password123!", "Replacement123!", actor=user)
    assert updated["id"] == user["id"]
    assert updated["role"] == role and updated["name"] == "Member"
    assert updated["session_version"] == user["session_version"] + 1
    assert storage.validate_session(user) is None
    assert storage.validate_session(updated) == updated
    assert storage.authenticate_user(user["email"], "Password123!") is None
    assert storage.authenticate_user(user["email"], "Replacement123!") == updated
    assert storage.authenticate_user(admin["email"], "TestPassword123!") == admin
    with storage.get_connection(db) as connection:
        stored = connection.execute("SELECT password_hash FROM users WHERE id = ?", (user["id"],)).fetchone()[0]
    assert "Replacement123!" not in stored


@pytest.mark.parametrize(
    "current,new,message",
    [
        ("", "Replacement123!", "actual es incorrecta"),
        ("WrongPassword!", "Replacement123!", "actual es incorrecta"),
        ("TestPassword123!", "short", "al menos 10"),
        ("TestPassword123!", "x" * 1025, "demasiado larga"),
    ],
)
def test_rejected_own_password_change_preserves_password_and_session(accounts, current, new, message):
    admin, db = accounts
    with pytest.raises(ValueError, match=message):
        storage.change_own_password(current, new, actor=admin)
    assert storage.authenticate_user(admin["email"], "TestPassword123!") == admin
    assert storage.validate_session(admin) == admin


def test_guest_cannot_change_own_password_even_with_forged_role(accounts):
    admin, db = accounts
    guest = storage.create_user("guest@example.com", "Guest", "Password123!", ROLE_GUEST, True, actor=admin)
    guest["role"] = ROLE_ADMIN
    with pytest.raises(ValueError, match="invitados"):
        storage.change_own_password("Password123!", "Replacement123!", actor=guest)
    with storage.get_connection(db) as connection:
        assert connection.execute("SELECT session_version FROM users WHERE id = ?", (guest["id"],)).fetchone()[0] == 0


@pytest.mark.parametrize("invalidate", ["disable", "role", "password"])
def test_invalidated_session_cannot_change_own_password(accounts, invalidate):
    admin, db = accounts
    user = storage.create_user("member@example.com", "Member", "Password123!", ROLE_ANALYST, True, actor=admin)
    if invalidate == "disable":
        storage.set_user_active(user["email"], False, actor=admin)
    elif invalidate == "role":
        storage.set_user_role(user["email"], ROLE_GUEST, actor=admin)
    else:
        storage.set_user_password(user["email"], "ResetByAdmin123!", actor=admin)
    with pytest.raises(ValueError, match="sesión ya no está activa"):
        storage.change_own_password("Password123!", "Replacement123!", actor=user)


def test_first_password_for_promoted_guest_and_optional_name(accounts):
    admin, db = accounts
    guest = storage.provision_verified_guest("guest@example.com")
    updated = storage.update_own_name(" Invitado ", actor=guest)
    assert updated["name"] == "Invitado"
    assert updated["email"] == guest["email"]
    assert updated["role"] == ROLE_GUEST
    assert storage.update_own_name("", actor=guest)["name"] == ""
    storage.set_user_password(guest["email"], "FirstPassword!", actor=admin)
    storage.set_user_role(guest["email"], ROLE_ANALYST, actor=admin)
    assert storage.authenticate_user(guest["email"], "FirstPassword!")


def test_search_names_emails_roles_pagination_and_literal_wildcards(accounts):
    admin, db = accounts
    for i in range(43):
        guest = storage.provision_verified_guest(f"visitor{i:02}@example.com")
        storage.update_own_name(f"José {i:02}", actor=guest)
    first, total = storage.search_users("JOSÉ", ROLE_GUEST, actor=admin)
    second, _ = storage.search_users("josé", ROLE_GUEST, page=2, actor=admin)
    last, _ = storage.search_users("josé", ROLE_GUEST, page=3, actor=admin)
    assert total == 43
    assert (len(first), len(second), len(last)) == (20, 20, 3)
    assert len({u["id"] for u in first + second + last}) == 43
    assert storage.search_users("VISITOR03", actor=admin)[1] == 1
    assert storage.search_users("%", actor=admin)[1] == 0
    assert storage.search_users("' OR 1=1 --", actor=admin)[1] == 0
    assert "José 03" in storage.user_search_options(actor=admin)


@pytest.mark.parametrize(
    "email,name,password,role",
    [
        ("bad", "Name", "Password123!", ROLE_GUEST),
        ("new@example.com", " ", "Password123!", ROLE_ANALYST),
        ("new@example.com", "Name", "short", ROLE_ANALYST),
        ("new@example.com", "Name", "Password123!", "unknown"),
        (" OWNER@example.com ", "Name", "Password123!", ROLE_ANALYST),
    ],
)
def test_invalid_account_creation(accounts, email, name, password, role):
    admin, db = accounts
    with pytest.raises(ValueError):
        storage.create_user(email, name, password, role, True, actor=admin)


@pytest.mark.parametrize(
    "role,users,ingest", [(ROLE_ADMIN, True, True), (ROLE_ANALYST, False, True), (ROLE_GUEST, False, False)]
)
def test_permissions_and_navigation(role, users, ingest):
    labels = {page["label"] for page in visible_page_definitions({"role": role, "is_active": True})}
    assert ("Usuarios" in labels) == users == can_access_page(role, "Usuarios")
    assert ("Ingesta" in labels) == ingest == can_access_page(role, "Ingesta")
    assert {"Mi usuario", "Partidos", "Análisis", "Gráficas avanzadas"} <= labels
    assert "Inicio" not in labels
    assert [page["label"] for page in visible_page_definitions()] == ["Iniciar sesión"]


def test_streamlit_staff_login_profile_and_logout(accounts):
    from streamlit.testing.v1 import AppTest

    app = AppTest.from_file("app/streamlit_app.py", default_timeout=15).run()
    assert not app.exception
    assert "Invitados" in [item.value for item in app.subheader]
    app.text_input(key="login_email").set_value("owner@example.com")
    app.text_input(key="login_password").set_value("TestPassword123!")
    next(button for button in app.button if button.label == "Iniciar sesión").click().run()
    assert not app.exception
    assert app.title[0].value == "Mi usuario"
    # AppTest does not retain programmatic page switches across separate run() calls.
    app.switch_page("pages/05_Mi_Usuario.py")
    name = next(field for field in app.text_input if field.label == "Nombre")
    name.set_value("Mi nombre")
    next(button for button in app.button if button.label == "Guardar cambios").click().run()
    assert storage.get_user_by_email("owner@example.com")["name"] == "Mi nombre"
    next(button for button in app.button if button.label == "Cerrar sesión").click().run()
    assert not app.exception
    assert "auth_user" not in app.session_state


def test_streamlit_user_filters_and_creation(accounts):
    from streamlit.testing.v1 import AppTest

    admin, db = accounts
    app = AppTest.from_file("app/streamlit_app.py", default_timeout=15)
    app.session_state["auth_user"] = admin
    app.run()
    next(button for button in app.button if button.label == "Usuarios").click().run()
    assert not app.exception
    app.switch_page("pages/06_Usuarios.py")
    for label, value in [("Correo", "new@example.com"), ("Nombre", "Nuevo"), ("Contraseña nueva", "NewPassword123!")]:
        next(field for field in app.text_input if field.label == label).set_value(value)
    next(button for button in app.button if button.label == "Crear usuario").click().run()
    assert not app.exception
    assert storage.authenticate_user("new@example.com", "NewPassword123!")
    app.selectbox(key="users_search").set_value("Nuevo")
    next(button for button in app.button if button.label == "Filtrar").click().run()
    assert list(app.dataframe[0].value["Correo"]) == ["new@example.com"]
    next(button for button in app.button if button.label == "Limpiar").click().run()
    assert not app.exception
    assert len(app.dataframe[0].value) == 2


@pytest.mark.parametrize("page", ["app/pages/01_Ingesta.py", "app/pages/06_Usuarios.py"])
def test_guest_cannot_open_restricted_page_directly(accounts, page):
    from streamlit.testing.v1 import AppTest

    guest = storage.provision_verified_guest("guest@example.com")
    app = AppTest.from_file(page, default_timeout=15)
    app.session_state["auth_user"] = guest
    app.run()
    assert not app.exception
    assert any("No tienes permiso" in error.value for error in app.error)
    assert not app.dataframe


def test_profile_uses_existing_language_preference(accounts):
    from streamlit.testing.v1 import AppTest

    admin, db = accounts
    app = AppTest.from_file("app/streamlit_app.py", default_timeout=15)
    app.session_state["auth_user"] = admin
    app.session_state["narrador_language"] = "en"
    app.run()
    assert not app.exception
    assert app.title[0].value == "My profile"
    assert next(field for field in app.text_input if field.label == "Role").value == "Administrator"
    assert any(button.label == "Update password" for button in app.button)


def test_streamlit_own_password_change_checks_current_and_confirmation(accounts):
    from streamlit.testing.v1 import AppTest

    admin, db = accounts
    app = AppTest.from_file("app/streamlit_app.py", default_timeout=15)
    app.session_state["auth_user"] = admin
    app.run()
    app.switch_page("pages/05_Mi_Usuario.py")

    def submit(current, new, confirmation):
        app.text_input(key="profile_current_password").set_value(current)
        app.text_input(key="profile_new_password").set_value(new)
        app.text_input(key="profile_confirm_password").set_value(confirmation)
        next(button for button in app.button if button.label == "Actualizar contraseña").click().run()
        assert not app.exception

    submit("WrongPassword!", "Replacement123!", "Replacement123!")
    assert any("actual es incorrecta" in error.value for error in app.error)
    assert storage.validate_session(admin) == admin
    submit("TestPassword123!", "Replacement123!", "Different123!")
    assert any("no coinciden" in error.value for error in app.error)
    assert storage.validate_session(admin) == admin
    submit("TestPassword123!", "Replacement123!", "Replacement123!")
    assert any("contraseña se ha actualizado" in message.value for message in app.success)
    assert storage.authenticate_user(admin["email"], "TestPassword123!") is None
    updated = app.session_state["auth_user"]
    assert storage.authenticate_user(admin["email"], "Replacement123!") == updated
    app.run()
    assert not app.exception
    assert app.title[0].value == "Mi usuario"
    assert storage.validate_session(updated) == updated


def test_streamlit_guest_password_form_is_disabled(accounts):
    from streamlit.testing.v1 import AppTest

    guest = storage.provision_verified_guest("guest@example.com")
    app = AppTest.from_file("app/streamlit_app.py", default_timeout=15)
    app.session_state["auth_user"] = guest
    app.run()
    assert not app.exception
    for key in ("profile_current_password", "profile_new_password", "profile_confirm_password"):
        assert app.text_input(key=key).disabled
    assert next(button for button in app.button if button.label == "Actualizar contraseña").disabled
    assert not next(button for button in app.button if button.label == "Guardar cambios").disabled
