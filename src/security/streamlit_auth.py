"""Streamlit authentication UI helpers."""

from __future__ import annotations

import os
import smtplib
from email.message import EmailMessage
from typing import Any
from urllib.parse import quote

import pandas as pd
import streamlit as st

from src.security.invitations import accept_invitation, create_invitation, list_invitations
from src.security.models import ROLE_ADMIN, ROLE_ANALYST
from src.security.storage import authenticate_user, initialize_security, list_users, set_user_active

SESSION_USER_KEY = "auth_user"


def require_login() -> dict:
    initialize_security()
    user = st.session_state.get(SESSION_USER_KEY)
    if not user:
        st.warning("Inicia sesión para usar el Narrador Inteligente de Fútbol.")
        st.info("Abre la página `Login` en la barra lateral.")
        st.stop()
    _render_sidebar_user(user)
    return user


def current_user() -> dict | None:
    return st.session_state.get(SESSION_USER_KEY)


def render_login_page() -> None:
    initialize_security()
    user = current_user()
    if user:
        _render_sidebar_user(user)
        st.success(f"Sesión activa: {user['email']} ({user['role']})")
        if user.get("role") == ROLE_ADMIN:
            render_admin_panel(user)
        return

    st.subheader("Iniciar sesión")
    with st.form("login_form"):
        email = st.text_input("Email")
        password = st.text_input("Contraseña", type="password")
        submitted = st.form_submit_button("Entrar")
    if submitted:
        authenticated = authenticate_user(email, password)
        if authenticated:
            st.session_state[SESSION_USER_KEY] = authenticated
            st.success("Sesión iniciada.")
            st.rerun()
        else:
            st.error("Credenciales inválidas o usuario inactivo.")

    st.divider()
    render_accept_invitation()


def render_accept_invitation() -> None:
    st.subheader("Aceptar invitación")
    query_token = ""
    try:
        query_token = st.query_params.get("invite_token", "")
    except Exception:
        query_token = ""

    with st.form("accept_invitation_form"):
        token = st.text_input("Token de invitación", value=query_token)
        password = st.text_input("Crear contraseña", type="password")
        confirm = st.text_input("Confirmar contraseña", type="password")
        submitted = st.form_submit_button("Aceptar invitación")
    if not submitted:
        return
    if len(password) < 10:
        st.error("La contraseña debe tener al menos 10 caracteres.")
        return
    if password != confirm:
        st.error("Las contraseñas no coinciden.")
        return
    try:
        user = accept_invitation(token, password)
    except ValueError as exc:
        st.error(str(exc))
        return
    st.session_state[SESSION_USER_KEY] = user
    st.success("Invitación aceptada y sesión iniciada.")
    st.rerun()


def render_admin_panel(user: dict) -> None:
    st.divider()
    st.subheader("Administración de usuarios")
    with st.form("invite_user_form"):
        email = st.text_input("Email a invitar")
        role = st.selectbox("Rol", [ROLE_ANALYST, ROLE_ADMIN])
        submitted = st.form_submit_button("Generar invitación")
    if submitted:
        try:
            invitation = create_invitation(email, invited_by=user["email"], role=role)
        except Exception as exc:
            st.error(f"No se pudo crear invitación: {exc}")
        else:
            st.success(f"Invitación generada para {invitation['email']}.")
            link = _invitation_link(invitation["token"])
            delivery = _send_invitation_email(invitation["email"], link)
            if delivery["status"] == "sent":
                st.info("Invitación enviada por SMTP.")
            else:
                if delivery.get("error_message"):
                    st.warning(f"No se pudo enviar por SMTP: {delivery['error_message']}")
                st.code(link, language="text")
                st.caption("SMTP no está configurado o falló; usa este enlace/token para desarrollo local.")

    users = list_users()
    if users:
        st.markdown("### Usuarios")
        st.dataframe(pd.DataFrame(users), width="stretch")
        emails = [row["email"] for row in users if row["email"] != user["email"]]
        if emails:
            selected = st.selectbox("Usuario para activar/desactivar", emails)
            action_cols = st.columns(2)
            if action_cols[0].button("Desactivar usuario"):
                set_user_active(selected, False)
                st.success(f"Usuario desactivado: {selected}")
                st.rerun()
            if action_cols[1].button("Activar usuario"):
                set_user_active(selected, True)
                st.success(f"Usuario activado: {selected}")
                st.rerun()

    invitations = list_invitations()
    if invitations:
        st.markdown("### Invitaciones recientes")
        st.dataframe(pd.DataFrame(invitations), width="stretch")


def _render_sidebar_user(user: dict) -> None:
    with st.sidebar:
        st.caption(f"Sesión: {user['email']}")
        st.caption(f"Rol: {user['role']}")
        if st.button("Cerrar sesión"):
            st.session_state.pop(SESSION_USER_KEY, None)
            st.rerun()


def _invitation_link(token: str) -> str:
    base_url = os.getenv("APP_BASE_URL", "").strip().rstrip("/")
    query = f"invite_token={quote(token)}"
    if base_url:
        return f"{base_url}/Login?{query}"
    return f"?{query}"


def _send_invitation_email(email: str, link: str) -> dict[str, Any]:
    host = os.getenv("SMTP_HOST", "").strip()
    from_email = os.getenv("SMTP_FROM_EMAIL", "").strip()
    if not host or not from_email:
        return {"status": "not_configured", "error_message": None}

    message = EmailMessage()
    message["Subject"] = "Invitación al Narrador Inteligente de Fútbol"
    message["From"] = from_email
    message["To"] = email
    message.set_content(
        "Has sido invitado al Narrador Inteligente de Fútbol.\n\n"
        f"Acepta la invitación aquí:\n{link}\n\n"
        "Si no esperabas esta invitación, puedes ignorar este correo."
    )

    port = int(os.getenv("SMTP_PORT", "587") or "587")
    username = os.getenv("SMTP_USERNAME", "").strip()
    password = os.getenv("SMTP_PASSWORD", "")
    use_tls = os.getenv("SMTP_USE_TLS", "true").strip().lower() not in {"0", "false", "no", "off"}

    try:
        with smtplib.SMTP(host, port, timeout=15) as smtp:
            if use_tls:
                smtp.starttls()
            if username and password:
                smtp.login(username, password)
            smtp.send_message(message)
    except Exception as exc:
        return {"status": "failed", "error_message": str(exc)}

    return {"status": "sent", "error_message": None}
