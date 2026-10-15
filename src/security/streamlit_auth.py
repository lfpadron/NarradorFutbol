"""Login, session validation and profile UI."""

from __future__ import annotations

import streamlit as st

from src.security.guest_otp import send_guest_token, verify_guest_token
from src.security.models import ROLE_GUEST, ROLE_LABELS, can_access_page
from src.security.storage import (
    authenticate_user,
    change_own_password,
    initialize_security,
    update_own_name,
    validate_session,
)
from src.ui.footer import render_footer
from src.ui.i18n import t

SESSION_USER_KEY = "auth_user"
PROFILE_PAGE = "pages/05_Mi_Usuario.py"
LOGIN_PAGE = "pages/00_Login.py"


def clear_session() -> None:
    language = st.session_state.get("narrador_language", "es")
    st.session_state.clear()
    st.session_state["narrador_language"] = language


def current_user() -> dict | None:
    saved = st.session_state.get(SESSION_USER_KEY)
    user = validate_session(saved)
    if saved and not user:
        clear_session()
        st.session_state["auth_notice"] = "Tu sesión ya no está activa. Inicia sesión de nuevo."
    if user:
        st.session_state[SESSION_USER_KEY] = user
    return user


def require_login(page: str | None = None) -> dict:
    initialize_security()
    user = current_user()
    if not user:
        st.switch_page(LOGIN_PAGE)
        st.stop()
    if page and not can_access_page(user["role"], page):
        st.error("No tienes permiso para acceder a esta pantalla.")
        render_footer()
        st.stop()
    _render_sidebar_user(user)
    return user


def _complete_login(user: dict) -> None:
    clear_session()
    st.session_state[SESSION_USER_KEY] = user
    st.session_state["auth_redirect_profile"] = True
    st.rerun()


def render_login_page() -> None:
    initialize_security()
    if current_user():
        st.switch_page(PROFILE_PAGE)
        return
    notice = st.session_state.pop("auth_notice", None)
    if notice:
        st.info(notice)
    st.title("Narrador Inteligente de Fútbol")
    st.write("Análisis, narración y una nueva manera de vivir cada partido.")
    st.header("Iniciar sesión")
    staff, guest = st.columns(2, gap="large")
    with staff, st.container(border=True):
        st.subheader("Administradores y analistas")
        st.caption("Accede con tu cuenta de trabajo.")
        with st.form("login_form", border=False):
            email = st.text_input("Correo", key="login_email", placeholder="tu@correo.com", max_chars=254)
            password = st.text_input("Contraseña", type="password", key="login_password", max_chars=1024)
            submitted = st.form_submit_button("Iniciar sesión", type="primary", width="stretch")
        if submitted:
            user = authenticate_user(email, password)
            if user:
                _complete_login(user)
            st.error("Credenciales inválidas o usuario inactivo.")
    with guest, st.container(border=True):
        st.subheader("Invitados")
        st.caption("Entra con tu correo. No necesitas invitación ni contraseña.")
        with st.form("guest_login_form", border=False, enter_to_submit=False):
            guest_email = st.text_input("Correo", key="guest_email", placeholder="tu@correo.com", max_chars=254)
            send = st.form_submit_button("Enviar token", width="stretch")
            token = st.text_input("Token de 6 dígitos", max_chars=6, placeholder="000000", key="guest_token")
            st.caption("El token caduca en 1 hora y solo se puede utilizar una vez.")
            enter = st.form_submit_button("Entrar", type="primary", width="stretch")
        if send:
            try:
                with st.spinner("Enviando token..."):
                    send_guest_token(guest_email)
                st.success("Token enviado. Revisa tu bandeja de entrada y la carpeta de spam.")
            except ValueError as exc:
                st.error(str(exc))
        if enter:
            try:
                with st.spinner("Verificando token..."):
                    user = verify_guest_token(guest_email, token)
                _complete_login(user)
            except ValueError as exc:
                st.error(str(exc))


def render_profile_page() -> None:
    user = require_login("Mi usuario")
    st.title("Mi usuario")
    st.write("Actualiza tu nombre para personalizar tu experiencia.")
    with st.container(border=True), st.form("profile_form", border=False):
        name = st.text_input("Nombre", value=user["name"], max_chars=120, help="Opcional")
        st.text_input("Correo", value=user["email"], disabled=True)
        st.text_input("Rol", value=str(t(ROLE_LABELS[user["role"]])), disabled=True)
        save = st.form_submit_button("Guardar cambios", type="primary")
    if save:
        try:
            st.session_state[SESSION_USER_KEY] = update_own_name(name, actor=user)
            st.success("Tu nombre se ha actualizado.")
        except ValueError as exc:
            st.error(str(exc))

    is_guest = user["role"] == ROLE_GUEST
    with st.container(border=True):
        st.subheader("Actualizar contraseña")
        if is_guest:
            st.caption("Los invitados acceden con un token de correo y no utilizan contraseña.")
        else:
            st.caption("Confirma tu contraseña actual y elige una nueva de al menos 10 caracteres.")
        with st.form("change_password_form", border=False, clear_on_submit=True):
            current_password = st.text_input(
                "Contraseña actual", type="password", key="profile_current_password", max_chars=1024, disabled=is_guest
            )
            new_password = st.text_input(
                "Contraseña nueva", type="password", key="profile_new_password", max_chars=1024, disabled=is_guest
            )
            confirmation = st.text_input(
                "Confirmar contraseña nueva",
                type="password",
                key="profile_confirm_password",
                max_chars=1024,
                disabled=is_guest,
            )
            change_password = st.form_submit_button("Actualizar contraseña", type="primary", disabled=is_guest)
        if change_password:
            try:
                if new_password != confirmation:
                    raise ValueError("Las contraseñas no coinciden.")
                st.session_state[SESSION_USER_KEY] = change_own_password(current_password, new_password, actor=user)
                st.success("Tu contraseña se ha actualizado.")
            except ValueError as exc:
                st.error(str(exc))


def _render_sidebar_user(user: dict) -> None:
    with st.sidebar:
        st.text(user["name"] or user["email"])
        st.caption(ROLE_LABELS[user["role"]])
        if st.button("Cerrar sesión", icon=":material/logout:", width="stretch"):
            clear_session()
            st.rerun()
