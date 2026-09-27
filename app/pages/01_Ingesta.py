from __future__ import annotations

import sys
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.config import INGESTION_LOG_DB
from src.ingestion.single_match import (
    MatchDownloadProgress,
    SingleMatchDownloadError,
    SingleMatchDownloadResult,
    download_single_match,
)
from src.security.streamlit_auth import require_login
from src.ui.footer import render_footer
from src.ui.i18n import is_english
from src.ui.navigation import ensure_page_shell

ensure_page_shell("Ingesta")
require_login()
st.title("Ingesta")

SINGLE_MATCH_INPUT_KEY = "single_match_download_id"
SINGLE_MATCH_RESULT_KEY = "single_match_download_result"


@st.cache_data(show_spinner=False)
def load_ingestion_summary() -> dict[str, object]:
    if not INGESTION_LOG_DB.exists():
        return {"exists": False}

    try:
        with duckdb.connect(str(INGESTION_LOG_DB), read_only=True) as connection:
            total_matches = connection.execute("SELECT COUNT(*) FROM ingestion_log").fetchone()[0]
            status_rows = connection.execute("""
                SELECT
                    events_status,
                    lineups_status,
                    three_sixty_status,
                    COUNT(*) AS rows
                FROM ingestion_log
                GROUP BY events_status, lineups_status, three_sixty_status
                ORDER BY rows DESC
                """).fetchdf()
            counts = connection.execute("""
                SELECT
                    SUM(CASE WHEN events_status IN ('downloaded', 'skipped_existing') THEN 1 ELSE 0 END) AS events_downloaded,
                    SUM(CASE WHEN lineups_status IN ('downloaded', 'skipped_existing') THEN 1 ELSE 0 END) AS lineups_downloaded,
                    SUM(CASE WHEN three_sixty_status IN ('downloaded', 'skipped_existing') THEN 1 ELSE 0 END) AS three_sixty_available,
                    SUM(CASE WHEN three_sixty_status = 'not_available' THEN 1 ELSE 0 END) AS three_sixty_not_available,
                    SUM(CASE WHEN three_sixty_status = 'failed' THEN 1 ELSE 0 END) AS three_sixty_failed
                FROM ingestion_log
                """).fetchone()
            errors = connection.execute("""
                SELECT
                    match_id,
                    home_team,
                    away_team,
                    events_status,
                    lineups_status,
                    three_sixty_status,
                    error_message,
                    last_attempt_at
                FROM ingestion_log
                WHERE error_message IS NOT NULL
                   OR events_status = 'failed'
                   OR lineups_status = 'failed'
                   OR three_sixty_status = 'failed'
                ORDER BY last_attempt_at DESC NULLS LAST
                LIMIT 20
                """).fetchdf()
            return {
                "exists": True,
                "total_matches": total_matches,
                "events_downloaded": counts[0] or 0,
                "lineups_downloaded": counts[1] or 0,
                "three_sixty_available": counts[2] or 0,
                "three_sixty_not_available": counts[3] or 0,
                "three_sixty_failed": counts[4] or 0,
                "status_rows": status_rows,
                "errors": errors,
            }
    except duckdb.Error as exc:
        return {"exists": True, "error": str(exc)}


def bilingual(es_text: str, en_text: str) -> str:
    return en_text if is_english() else es_text


def download_status_label(status: str) -> str:
    labels = {
        "downloaded": ("descargado", "downloaded"),
        "skipped_existing": ("ya existente", "already available"),
        "not_available": ("no disponible", "not available"),
        "failed": ("fallido", "failed"),
        "transformed": ("transformado", "transformed"),
    }
    es_label, en_label = labels.get(status, (status, status))
    return bilingual(es_label, en_label)


def progress_message(update: MatchDownloadProgress) -> str:
    details = update.details
    stage = update.stage
    match_id = details.get("match_id", "")
    status = download_status_label(str(details.get("status") or ""))
    rows = int(details.get("rows") or 0)
    current = int(details.get("current") or 0)
    total = int(details.get("total") or 0)
    cause = str(details.get("cause") or "")

    messages = {
        "checking_local_catalog": (
            f"Buscando el partido {match_id} en el catálogo local...",
            f"Looking for match {match_id} in the local catalog...",
        ),
        "loading_catalog": (
            "Consultando el catálogo público de StatsBomb...",
            "Loading the public StatsBomb catalog...",
        ),
        "scanning_catalog": (
            f"Revisando competición/temporada {current} de {total}...",
            f"Checking competition/season {current} of {total}...",
        ),
        "refreshing_catalog": (
            f"Actualizando catálogo {current} de {total}...",
            f"Refreshing catalog {current} of {total}...",
        ),
        "building_match_index": (
            "Actualizando el índice local de partidos...",
            "Updating the local match index...",
        ),
        "match_found": (
            f"Partido {match_id} localizado.",
            f"Match {match_id} found.",
        ),
        "downloading_events": (
            "Bajando eventos del partido...",
            "Downloading match events...",
        ),
        "events_ready": (
            f"Eventos listos: {rows} registros ({status}).",
            f"Events ready: {rows} records ({status}).",
        ),
        "events_failed": (
            f"Falló la descarga de eventos: {cause}",
            f"Event download failed: {cause}",
        ),
        "downloading_lineups": (
            "Bajando alineaciones...",
            "Downloading lineups...",
        ),
        "lineups_ready": (
            f"Alineaciones listas ({status}).",
            f"Lineups ready ({status}).",
        ),
        "lineups_failed": (
            f"No se pudieron bajar las alineaciones: {cause}",
            f"Lineup download failed: {cause}",
        ),
        "downloading_three_sixty": (
            "Buscando datos 360...",
            "Checking for 360 data...",
        ),
        "three_sixty_ready": (
            f"Datos 360: {status}.",
            f"360 data: {status}.",
        ),
        "three_sixty_failed": (
            f"No se pudieron bajar los datos 360: {cause}",
            f"360 data download failed: {cause}",
        ),
        "transforming": (
            "Transformando el partido y actualizando DuckDB...",
            "Transforming the match and updating DuckDB...",
        ),
        "completed": (
            f"Partido {match_id} listo para analizar.",
            f"Match {match_id} is ready for analysis.",
        ),
    }
    es_text, en_text = messages.get(stage, (stage, stage))
    return bilingual(es_text, en_text)


def should_log_progress(update: MatchDownloadProgress) -> bool:
    if update.stage not in {"scanning_catalog", "refreshing_catalog"}:
        return True
    current = int(update.details.get("current") or 0)
    total = int(update.details.get("total") or 0)
    interval = max(1, total // 5)
    return current in {1, total} or current % interval == 0


def download_error_message(error: SingleMatchDownloadError) -> str:
    match_id = error.details.get("match_id", "")
    messages = {
        "invalid_match_id": (
            "El número de partido debe ser un entero positivo.",
            "The match number must be a positive integer.",
        ),
        "download_in_progress": (
            "Ya hay una descarga en curso. Espera a que termine antes de iniciar otra.",
            "A download is already running. Wait for it to finish before starting another one.",
        ),
        "catalog_failed": (
            "No se pudo consultar el catálogo público de StatsBomb.",
            "The public StatsBomb catalog could not be loaded.",
        ),
        "empty_catalog": (
            "StatsBomb devolvió un catálogo vacío.",
            "StatsBomb returned an empty catalog.",
        ),
        "catalog_incomplete": (
            "No se pudo revisar todo el catálogo de StatsBomb. Intenta de nuevo en unos minutos.",
            "The full StatsBomb catalog could not be checked. Try again in a few minutes.",
        ),
        "match_not_found": (
            f"El partido {match_id} no aparece en StatsBomb Open Data. Verifica el número.",
            f"Match {match_id} was not found in StatsBomb Open Data. Check the number.",
        ),
        "events_failed": (
            f"No se pudieron bajar los eventos del partido {match_id}.",
            f"Events for match {match_id} could not be downloaded.",
        ),
        "transformation_failed": (
            f"Los archivos del partido {match_id} se bajaron, pero no pudieron transformarse.",
            f"Files for match {match_id} were downloaded but could not be transformed.",
        ),
    }
    es_text, en_text = messages.get(
        error.code,
        ("No se pudo completar la descarga.", "The download could not be completed."),
    )
    return bilingual(es_text, en_text)


def clear_single_match_download() -> None:
    st.session_state[SINGLE_MATCH_INPUT_KEY] = None
    st.session_state.pop(SINGLE_MATCH_RESULT_KEY, None)


def render_download_result(result: SingleMatchDownloadResult) -> None:
    st.success(
        bilingual(
            f"Partido {result.match_id} descargado y listo para analizar.",
            f"Match {result.match_id} downloaded and ready for analysis.",
        )
    )
    if result.home_team or result.away_team:
        st.write(f"**{result.home_team or '-'} vs. {result.away_team or '-'}**")

    result_cols = st.columns(4)
    result_cols[0].metric("Eventos", result.events_rows)
    result_cols[1].metric("Alineaciones", download_status_label(result.lineups_status))
    result_cols[2].metric("360", download_status_label(result.three_sixty_status))
    result_cols[3].metric("Transformación", download_status_label(result.transformation_status))

    for warning in result.warnings:
        st.warning(
            bilingual(
                f"El partido quedó disponible con una advertencia: {warning}",
                f"The match is available with a warning: {warning}",
            )
        )


st.subheader("Bajar datos")
st.write("Ingresa el identificador de StatsBomb para descargar y preparar un solo partido.")
match_number = st.number_input(
    "Número de partido *",
    min_value=1,
    step=1,
    value=None,
    key=SINGLE_MATCH_INPUT_KEY,
)
st.caption("* Campo obligatorio")
download_cols = st.columns([1, 1, 4])
download_requested = download_cols[0].button(
    "Bajar",
    icon=":material/download:",
    type="primary",
    use_container_width=True,
)
download_cols[1].button(
    "Limpiar",
    icon=":material/clear_all:",
    use_container_width=True,
    on_click=clear_single_match_download,
)

st.markdown("#### Estado")
if download_requested:
    if match_number is None:
        st.error(bilingual("El número de partido es obligatorio.", "The match number is required."))
    else:
        selected_match_id = int(match_number)
        initial_message = bilingual(
            f"Preparando la descarga del partido {selected_match_id}...",
            f"Preparing download for match {selected_match_id}...",
        )
        status_container = st.status(initial_message, expanded=True, state="running")
        progress_bar = st.progress(0, text=initial_message)

        def update_download_progress(update: MatchDownloadProgress) -> None:
            message = progress_message(update)
            progress_bar.progress(int(round(update.progress * 100)), text=message)
            if should_log_progress(update):
                status_container.write(message)

        try:
            result = download_single_match(
                selected_match_id,
                progress_callback=update_download_progress,
            )
            st.session_state[SINGLE_MATCH_RESULT_KEY] = result
            st.cache_data.clear()
            complete_message = bilingual(
                f"Partido {selected_match_id} listo.",
                f"Match {selected_match_id} is ready.",
            )
            progress_bar.progress(100, text=complete_message)
            status_container.update(label=complete_message, state="complete", expanded=False)
        except SingleMatchDownloadError as exc:
            st.session_state.pop(SINGLE_MATCH_RESULT_KEY, None)
            error_message = download_error_message(exc)
            status_container.write(error_message)
            if str(exc) and str(exc) != exc.code:
                status_container.code(str(exc))
            status_container.update(label=error_message, state="error", expanded=True)
        except Exception as exc:
            st.session_state.pop(SINGLE_MATCH_RESULT_KEY, None)
            error_message = bilingual(
                "Ocurrió un error inesperado durante la descarga.",
                "An unexpected error occurred during the download.",
            )
            status_container.write(error_message)
            status_container.code(str(exc))
            status_container.update(label=error_message, state="error", expanded=True)

stored_result = st.session_state.get(SINGLE_MATCH_RESULT_KEY)
if isinstance(stored_result, SingleMatchDownloadResult):
    render_download_result(stored_result)
elif not download_requested:
    st.caption(bilingual("Listo para bajar un partido.", "Ready to download a match."))

st.divider()


summary = load_ingestion_summary()

if not summary.get("exists"):
    st.info("Todavia no existe `data/metadata/ingestion_log.duckdb`.")
    st.code("uv run python -m src.ingestion.run_ingestion --limit 3", language="bash")
elif summary.get("error"):
    st.error("No se pudo leer la bitacora de ingesta.")
    st.code(str(summary["error"]))
else:
    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Partidos en bitacora", summary["total_matches"])
    col2.metric("Eventos descargados", summary["events_downloaded"])
    col3.metric("Lineups descargados", summary["lineups_downloaded"])
    col4.metric("360 disponibles", summary["three_sixty_available"])
    col5.metric("360 no disponibles", summary["three_sixty_not_available"])

    if summary["three_sixty_failed"]:
        st.warning(f"360 fallidos: {summary['three_sixty_failed']}")

    st.subheader("Estados")
    status_rows = summary["status_rows"]
    st.dataframe(status_rows if isinstance(status_rows, pd.DataFrame) else pd.DataFrame(), width="stretch")

    st.subheader("Errores recientes")
    errors = summary["errors"]
    if isinstance(errors, pd.DataFrame) and not errors.empty:
        st.dataframe(errors, width="stretch")
    else:
        st.success("No hay errores recientes registrados.")

render_footer()
