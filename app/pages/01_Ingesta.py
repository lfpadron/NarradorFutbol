from __future__ import annotations

import duckdb
import pandas as pd
import streamlit as st

from src.config import INGESTION_LOG_DB


st.set_page_config(page_title="Ingesta", layout="wide")
st.title("Ingesta")


@st.cache_data(show_spinner=False)
def load_ingestion_summary() -> dict[str, object]:
    if not INGESTION_LOG_DB.exists():
        return {"exists": False}

    try:
        with duckdb.connect(str(INGESTION_LOG_DB), read_only=True) as connection:
            total_matches = connection.execute("SELECT COUNT(*) FROM ingestion_log").fetchone()[0]
            status_rows = connection.execute(
                """
                SELECT
                    events_status,
                    lineups_status,
                    three_sixty_status,
                    COUNT(*) AS rows
                FROM ingestion_log
                GROUP BY events_status, lineups_status, three_sixty_status
                ORDER BY rows DESC
                """
            ).fetchdf()
            counts = connection.execute(
                """
                SELECT
                    SUM(CASE WHEN events_status IN ('downloaded', 'skipped_existing') THEN 1 ELSE 0 END) AS events_downloaded,
                    SUM(CASE WHEN lineups_status IN ('downloaded', 'skipped_existing') THEN 1 ELSE 0 END) AS lineups_downloaded,
                    SUM(CASE WHEN three_sixty_status IN ('downloaded', 'skipped_existing') THEN 1 ELSE 0 END) AS three_sixty_available,
                    SUM(CASE WHEN three_sixty_status = 'not_available' THEN 1 ELSE 0 END) AS three_sixty_not_available,
                    SUM(CASE WHEN three_sixty_status = 'failed' THEN 1 ELSE 0 END) AS three_sixty_failed
                FROM ingestion_log
                """
            ).fetchone()
            errors = connection.execute(
                """
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
                """
            ).fetchdf()
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
