"""Isolated player-card selection and exports for the player-analysis page."""

from __future__ import annotations

from typing import Any

import streamlit as st
import streamlit.components.v1 as components

from src.analytics.player_cards import load_player_cards
from src.reports.player_cards_export import player_cards_docx, player_cards_html, player_cards_pdf
from src.ui.i18n import current_language
from src.ui.player_card_charts import render_player_cards_png


@st.cache_data(show_spinner=False, max_entries=16, ttl=300)
def _build_cards(match_id: int, player_ids: tuple[int, ...], language: str) -> dict[str, Any]:
    cards = load_player_cards(match_id, list(player_ids))
    png = render_player_cards_png(cards, language)
    return {"cards": cards, "png": png, "html": player_cards_html(cards, png, language)}


@st.cache_data(show_spinner=False, max_entries=16)
def _document(cards: list[dict[str, Any]], png: bytes, language: str, file_format: str) -> bytes:
    exporter = player_cards_docx if file_format == "docx" else player_cards_pdf
    return exporter(cards, png, language)


def render_player_cards_panel(match_id: int, players: list[dict[str, Any]]) -> None:
    language = current_language()
    english = language == "en"
    st.subheader("Player cards" if english else "Tarjetas de jugadores")
    st.caption(
        "Choose one or two players from either team in the selected match."
        if english
        else "Elige uno o dos jugadores del mismo equipo o de equipos contrarios en el partido seleccionado."
    )
    by_id = {int(row["player_id"]): row for row in players if row.get("player_id") is not None}
    if not by_id:
        st.info(
            "No players available for this match." if english else "No hay jugadores disponibles para este partido."
        )
        return
    count = st.radio(
        "Number of players" if english else "Número de jugadores",
        [1, 2] if len(by_id) > 1 else [1],
        format_func=str,
        horizontal=True,
        key=f"player_cards_count_{match_id}",
    )
    columns = st.columns(count)
    selected: list[int] = []
    for index, column in enumerate(columns):
        choices = [player_id for player_id in by_id if player_id not in selected]
        with column:
            selected.append(
                st.selectbox(
                    f"{'Player' if english else 'Jugador'} {index + 1}",
                    choices,
                    format_func=lambda player_id: f"{by_id[player_id]['player_name']} | {by_id[player_id]['team_name']}",
                    key=f"player_cards_choice_{match_id}_{index}_{selected[0] if selected else 0}",
                )
            )
    selection = (match_id, tuple(selected), language)
    if st.button("Generate cards" if english else "Generar tarjetas", key="player_cards_generate"):
        try:
            with st.spinner("Generating cards..." if english else "Generando tarjetas..."):
                result = _build_cards(match_id, tuple(selected), language)
            st.session_state["player_cards_result"] = {"selection": selection, **result}
        except Exception as exc:
            st.session_state.pop("player_cards_result", None)
            st.error(f"{'Could not generate cards' if english else 'No se pudieron generar las tarjetas'}: {exc}")
    result = st.session_state.get("player_cards_result")
    if not result or result["selection"] != selection:
        return
    # The preview is the downloadable HTML, including its final StatsBomb/Astrogato credits.
    components.html(result["html"].decode("utf-8"), height=1020, scrolling=True)
    filename = f"player-cards-{match_id}-{'-'.join(map(str, selected))}-{language}"
    for column, file_format, mime in zip(
        st.columns(3),
        ("html", "docx", "pdf"),
        ("text/html", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", "application/pdf"),
    ):
        with column:
            try:
                data = (
                    result["html"]
                    if file_format == "html"
                    else _document(result["cards"], result["png"], language, file_format)
                )
                st.download_button(
                    f"{'Download' if english else 'Descargar'} {file_format.upper()}",
                    data,
                    file_name=f"{filename}.{file_format}",
                    mime=mime,
                    key=f"player_cards_download_{file_format}",
                    on_click="ignore",
                )
            except Exception as exc:
                st.error(f"{file_format.upper()}: {exc}")
