from __future__ import annotations

import duckdb
import streamlit as st

from src.config import ANALYTICS_DB
from src.security.streamlit_auth import require_login

st.set_page_config(page_title="Narrador Inteligente de Futbol", layout="wide")
require_login()


@st.cache_data(show_spinner=False)
def get_database_status() -> dict[str, object]:
    if not ANALYTICS_DB.exists():
        return {"exists": False}

    try:
        with duckdb.connect(str(ANALYTICS_DB), read_only=True) as connection:
            return {
                "exists": True,
                "path": ANALYTICS_DB.as_posix(),
                "matches": connection.execute(
                    "SELECT COUNT(*) FROM vw_match_summary WHERE total_events > 0"
                ).fetchone()[0],
                "events": connection.execute("SELECT COUNT(*) FROM event").fetchone()[0],
                "shots": connection.execute("SELECT COUNT(*) FROM shot").fetchone()[0],
                "passes": connection.execute('SELECT COUNT(*) FROM "pass"').fetchone()[0],
            }
    except duckdb.Error as exc:
        return {"exists": True, "error": str(exc), "path": ANALYTICS_DB.as_posix()}


st.title("Narrador Inteligente de Futbol")
st.write(
    "Explorador local para revisar la ingesta, los partidos transformados y las "
    "metricas futbolisticas generadas desde StatsBomb Open Data."
)

status = get_database_status()

st.subheader("Estado de DuckDB")
if not status.get("exists"):
    st.warning("No existe `data/analytics/statsbomb.duckdb`.")
    st.code("uv run python -m src.transform.build_duckdb --limit 3 --force", language="bash")
elif status.get("error"):
    st.error("La base existe, pero no se pudo leer.")
    st.code(str(status["error"]))
else:
    st.caption(str(status.get("path")))
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Partidos transformados", status.get("matches", 0))
    col2.metric("Eventos", status.get("events", 0))
    col3.metric("Tiros", status.get("shots", 0))
    col4.metric("Pases", status.get("passes", 0))

st.subheader("Flujo recomendado")
st.code(
    "\n".join(
        [
            "uv run python -m src.ingestion.run_ingestion --limit 3",
            "uv run python -m src.transform.build_duckdb --limit 3 --force",
            "uv run python -m src.analytics.run_analysis --list-matches",
            "uv run streamlit run app/streamlit_app.py",
        ]
    ),
    language="bash",
)
