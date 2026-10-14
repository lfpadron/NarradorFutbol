"""Administrator-only account management."""

from __future__ import annotations

import math

import pandas as pd
import streamlit as st

from src.security.models import ROLE_ANALYST, ROLE_LABELS
from src.security.storage import (
    PAGE_SIZE,
    create_user,
    get_user_by_email,
    search_users,
    set_user_active,
    set_user_password,
    set_user_role,
    user_search_options,
)
from src.security.streamlit_auth import require_login


def _clear_filters() -> None:
    st.session_state["users_search"] = None
    st.session_state["users_role_filter"] = None
    st.session_state["users_filters"] = ("", None)
    st.session_state["users_page"] = 1


def _saved(message: str) -> None:
    st.session_state["users_notice"] = message
    st.session_state.pop("users_action", None)
    st.rerun()


def render_users_page() -> None:
    actor = require_login("Usuarios")
    st.title("Usuarios")
    st.write("Gestiona las cuentas, los roles y el acceso al Narrador de Fútbol.")
    notice = st.session_state.pop("users_notice", None)
    if notice:
        st.success(notice)
    with st.container(border=True):
        st.subheader("Buscar")
        with st.form("user_search_form", border=False):
            search_col, role_col = st.columns([2, 1])
            query = search_col.selectbox(
                "Correo o nombre",
                user_search_options(actor=actor),
                index=None,
                accept_new_options=True,
                placeholder="Escribe para buscar por correo o nombre",
                key="users_search",
            )
            role = role_col.selectbox(
                "Rol",
                [None, *ROLE_LABELS],
                format_func=lambda value: ROLE_LABELS.get(value, "Todos"),
                key="users_role_filter",
            )
            buttons = st.columns(2)
            apply = buttons[0].form_submit_button("Filtrar", type="primary", width="stretch")
            buttons[1].form_submit_button("Limpiar", on_click=_clear_filters, width="stretch")
        if apply:
            st.session_state["users_filters"] = (query or "", role)
            st.session_state["users_page"] = 1
        query_filter, role_filter = st.session_state.get("users_filters", ("", None))
        page = st.session_state.get("users_page", 1)
        users, total = search_users(query_filter, role_filter, page, actor=actor)
        pages = max(1, math.ceil(total / PAGE_SIZE))
        page = min(max(1, page), pages)
        st.session_state["users_page"] = page
        st.caption(f"{total} usuarios · Página {page} de {pages} · Hasta 20 registros por página")
        if not users:
            st.info("No se encontraron usuarios con estos filtros.")
        else:
            table = pd.DataFrame(
                [
                    {
                        "Correo": user["email"],
                        "Nombre": user["name"],
                        "Rol": ROLE_LABELS[user["role"]],
                        "Activo": user["is_active"],
                    }
                    for user in users
                ]
            )
            st.dataframe(table, hide_index=True, width="stretch")
            emails = [user["email"] for user in users]
            selected = st.selectbox(
                "Usuario seleccionado", emails, key=f"users_selected_{page}_{query_filter}_{role_filter}"
            )
            selected_user = next(user for user in users if user["email"] == selected)
            actions = st.columns(3)
            if actions[0].button("Capturar contraseña", width="stretch"):
                st.session_state["users_action"] = ("password", selected)
            if actions[1].button("Cambiar rol", width="stretch"):
                st.session_state["users_action"] = ("role", selected)
            if actions[2].button("Desactivar" if selected_user["is_active"] else "Activar", width="stretch"):
                try:
                    set_user_active(selected, not selected_user["is_active"], actor=actor)
                    _saved("Estado del usuario actualizado.")
                except ValueError as exc:
                    st.error(str(exc))
            action = st.session_state.get("users_action")
            if action and action[1] == selected:
                _render_action(action[0], selected, actor)
        previous, following = st.columns(2)
        if previous.button("Anterior", disabled=page <= 1, width="stretch"):
            st.session_state["users_page"] = page - 1
            st.session_state.pop("users_action", None)
            st.rerun()
        if following.button("Siguiente", disabled=page >= pages, width="stretch"):
            st.session_state["users_page"] = page + 1
            st.session_state.pop("users_action", None)
            st.rerun()
    _render_create_user(actor)


def _render_action(action: str, email: str, actor: dict) -> None:
    user = get_user_by_email(email)
    if not user:
        st.error("El usuario ya no existe.")
        return
    if action == "password":
        with st.form(f"password_form_{user['id']}", clear_on_submit=True):
            st.write(email)
            password = st.text_input("Contraseña nueva", type="password", max_chars=1024)
            confirm = st.text_input("Confirmar contraseña", type="password", max_chars=1024)
            st.caption("Al menos 10 caracteres. Reemplaza la contraseña anterior, si existe.")
            save = st.form_submit_button("Guardar contraseña", type="primary")
        if save:
            try:
                if password != confirm:
                    raise ValueError("Las contraseñas no coinciden.")
                set_user_password(email, password, actor=actor)
                _saved("Contraseña guardada.")
            except ValueError as exc:
                st.error(str(exc))
    elif action == "role":
        with st.form(f"role_form_{user['id']}"):
            st.write(email)
            role = st.selectbox(
                "Nuevo rol", list(ROLE_LABELS), index=list(ROLE_LABELS).index(user["role"]), format_func=ROLE_LABELS.get
            )
            st.caption("Puede haber un máximo de tres administradores activos.")
            save = st.form_submit_button("Guardar rol", type="primary")
        if save:
            try:
                set_user_role(email, role, actor=actor)
                _saved("Rol actualizado.")
            except ValueError as exc:
                st.error(str(exc))


def _render_create_user(actor: dict) -> None:
    with st.container(border=True):
        st.subheader("Crear usuario nuevo")
        st.caption("Todos los campos son obligatorios.")
        with st.form("create_user_form", clear_on_submit=True, border=False):
            left, right = st.columns(2)
            email = left.text_input("Correo", max_chars=254)
            name = right.text_input("Nombre", max_chars=120)
            password = st.text_input(
                "Contraseña nueva", type="password", max_chars=1024, help="Al menos 10 caracteres."
            )
            left, right = st.columns(2)
            role = left.selectbox(
                "Rol", list(ROLE_LABELS), index=list(ROLE_LABELS).index(ROLE_ANALYST), format_func=ROLE_LABELS.get
            )
            active = right.selectbox(
                "Estado", [True, False], format_func=lambda value: "Activo" if value else "Inactivo"
            )
            create = st.form_submit_button("Crear usuario", type="primary")
        if create:
            try:
                create_user(email, name, password, role, active, actor=actor)
                _saved("Usuario creado.")
            except ValueError as exc:
                st.error(str(exc))
