"""Shared shot selection, static chart, animation, and export controls."""

from __future__ import annotations

from typing import Any

import streamlit as st

from src.analytics.shot_chains import load_shot_chains, shot_chain_rows, shot_chain_title
from src.reports.shot_chain_export import RENDER_LOCK, shot_chain_pdf, shot_chain_video
from src.ui.i18n import current_language
from src.ui.shot_chain_charts import render_shot_chain_png


@st.cache_data(show_spinner=False, max_entries=12, ttl=300)
def _load_chains(match_id: int, home_team: str, away_team: str) -> list[dict[str, Any]]:
    return load_shot_chains(match_id, home_team, away_team)


@st.cache_data(show_spinner=False, max_entries=24)
def _chart_png(chain: dict[str, Any], language: str) -> bytes:
    with RENDER_LOCK:
        return render_shot_chain_png(chain, language)


@st.cache_data(show_spinner=False, max_entries=12)
def _video(chain: dict[str, Any], language: str) -> bytes:
    return shot_chain_video(chain, language)


def render_shot_chain_panel(match_id: int, home_team: str, away_team: str, *, animated: bool = False) -> None:
    language = current_language()
    st.subheader("Animación de tiros" if animated else "Pases para tiro a gol")
    chains = _load_chains(match_id, home_team, away_team)
    if not chains:
        st.info("No hay tiros con coordenadas disponibles para este partido.")
        return
    by_id = {chain["shot_id"]: chain for chain in chains}
    ids = list(by_id)
    remembered = st.session_state.get(f"shot_chain_selected_{match_id}")
    selected = st.selectbox(
        "Jugada: minuto – equipo – gol/tiro a gol",
        ids,
        index=ids.index(remembered) if remembered in ids else 0,
        format_func=lambda shot_id: shot_chain_title(by_id[shot_id], language),
        key=f"shot_chain_choice_{match_id}",
    )
    st.session_state[f"shot_chain_selected_{match_id}"] = selected
    chain = by_id[selected]
    columns = st.columns(3)
    columns[0].metric("Pases previos", len(chain["stages"]) - 1)
    columns[1].metric("Participantes", len({stage["player_id"] for stage in chain["stages"]}))
    columns[2].metric("Rematador", chain["stages"][-1]["player_name"])
    st.caption("Hasta tres pases de la misma cadena. Local rojo hacia la derecha; visitante azul hacia la izquierda.")
    filename = f"shot-chain-{match_id}-{selected}-{language}"
    if animated:
        st.caption(
            "Reconstrucción por eventos con desplazamientos interpolados. "
            "El final del tiro es ilustrativo: salida del balón sin gol o rebote en la red con gol."
        )
        try:
            with st.spinner("Animando la jugada..."):
                video = _video(chain, language)
            st.video(video, format="video/mp4", autoplay=True, loop=True, muted=True)
            st.download_button(
                "Exportar video (MP4)",
                video,
                file_name=f"{filename}.mp4",
                mime="video/mp4",
                key=f"shot_chain_video_{match_id}_{selected}_{language}",
                on_click="ignore",
            )
        except RuntimeError as exc:
            st.error(str(exc))
            st.image(_chart_png(chain, language), width="stretch")
    else:
        png = _chart_png(chain, language)
        st.image(png, width="stretch")
        st.download_button(
            "Exportar PDF",
            shot_chain_pdf(chain, png, language),
            file_name=f"{filename}.pdf",
            mime="application/pdf",
            key=f"shot_chain_pdf_{match_id}_{selected}_{language}",
            on_click="ignore",
        )
    with st.expander("Detalle de la cadena"):
        st.dataframe(shot_chain_rows(chain, language), hide_index=True, width="stretch")
