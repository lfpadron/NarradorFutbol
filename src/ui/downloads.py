"""Streamlit download helpers for generated files."""

from __future__ import annotations

import re
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

import streamlit as st

from src.config import PROJECT_ROOT


DEFAULT_FILE_LABELS = {
    "markdown": "Markdown",
    "html": "HTML",
    "json": "JSON",
    "pdf": "PDF",
    "docx": "DOCX",
}

DEFAULT_EXPORT_KEYS = ("markdown", "html", "json", "pdf", "docx")

MIME_TYPES = {
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".html": "text/html",
    ".json": "application/json",
    ".md": "text/markdown",
    ".pdf": "application/pdf",
    ".txt": "text/plain",
}


def render_download_button(
    path_value: str | Path | None,
    label: str,
    key: str,
) -> bool:
    """Render a Streamlit download button for a generated local file."""

    path = resolve_generated_file(path_value)
    if path is None:
        return False
    if not path.exists():
        st.warning(f"No se encontro el archivo para descargar: `{path_value}`")
        return False
    if not path.is_file():
        st.warning(f"La ruta no apunta a un archivo descargable: `{path_value}`")
        return False

    st.download_button(
        f"Descargar {label}",
        data=path.read_bytes(),
        file_name=path.name,
        mime=MIME_TYPES.get(path.suffix.lower(), "application/octet-stream"),
        key=key,
    )
    return True


def render_export_downloads(
    paths: Mapping[str, Any],
    key_prefix: str,
    keys: Iterable[str] = DEFAULT_EXPORT_KEYS,
    labels: Mapping[str, str] = DEFAULT_FILE_LABELS,
) -> None:
    """Render download buttons for the generated files present in a paths dict."""

    items = [(key, paths.get(key)) for key in keys if paths.get(key)]
    if not items:
        return

    columns = st.columns(min(len(items), 4))
    for index, (file_key, path_value) in enumerate(items):
        label = labels.get(file_key, file_key.upper())
        widget_key = f"{key_prefix}_{file_key}_{_safe_key(str(path_value))}"
        with columns[index % len(columns)]:
            render_download_button(path_value, label, widget_key)


def resolve_generated_file(path_value: str | Path | None) -> Path | None:
    """Resolve a public export path into the local file Streamlit can serve."""

    if path_value is None:
        return None

    path = path_value if isinstance(path_value, Path) else Path(str(path_value))
    if path.is_absolute():
        return path

    return PROJECT_ROOT / path


def _safe_key(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9_-]+", "-", value)
    return clean.strip("-")[:120] or "file"
