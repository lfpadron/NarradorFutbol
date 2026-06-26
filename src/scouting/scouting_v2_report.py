"""Export Scouting AI v2 reports."""

from __future__ import annotations

import html
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import markdown

from src.config import SCOUTING_DIR, project_relative
from src.ingestion.utils import to_jsonable
from src.reports.pdf_report import render_pdf_report
from src.scouting.scouting_exporter import render_scouting_docx


def save_scouting_v2_report(
    result: dict[str, Any],
    include_html: bool = False,
    include_docx: bool = False,
    include_pdf: bool = False,
) -> dict[str, Any]:
    SCOUTING_DIR.mkdir(parents=True, exist_ok=True)
    match_a = int(result["match_id_a"])
    player_a = int(result["player_id_a"])
    match_b = result.get("match_id_b")
    player_b = result.get("player_id_b")
    exported_at, suffix, paths = _build_paths(match_a, player_a, match_b, player_b)

    markdown_text = render_scouting_v2_markdown(result)
    html_text = render_scouting_v2_html(result, markdown_text)
    paths["markdown"].write_text(markdown_text, encoding="utf-8")
    with paths["json"].open("w", encoding="utf-8") as file:
        json.dump(to_jsonable(result), file, ensure_ascii=False, indent=2)
        file.write("\n")

    save_result: dict[str, Any] = {
        "markdown": _public_path(paths["markdown"]),
        "html": None,
        "json": _public_path(paths["json"]),
        "pdf": None,
        "docx": None,
        "exported_at": exported_at.isoformat(timespec="seconds"),
        "exported_at_utc": datetime.now(timezone.utc).replace(tzinfo=None).isoformat(timespec="seconds"),
        "export_suffix": suffix,
        "html_status": "not_requested",
        "pdf_status": "not_requested",
        "docx_status": "not_requested",
        "pdf_error_message": None,
        "pdf_warning_message": None,
        "docx_error_message": None,
    }

    if include_html:
        paths["html"].write_text(html_text, encoding="utf-8")
        save_result["html"] = _public_path(paths["html"])
        save_result["html_status"] = "generated"

    if include_docx:
        docx_result = render_scouting_docx(result, markdown_text, paths["docx"].as_posix())
        docx_result["path"] = _public_path(docx_result.get("path") or paths["docx"])
        save_result["docx_status"] = docx_result["status"]
        save_result["docx_error_message"] = docx_result.get("error_message")
        if docx_result["status"] == "generated":
            save_result["docx"] = docx_result["path"]

    if include_pdf:
        pdf_result = render_pdf_report(html_text, paths["pdf"].as_posix())
        pdf_result["path"] = _public_path(pdf_result.get("path") or paths["pdf"])
        save_result["pdf_status"] = pdf_result["status"]
        save_result["pdf_error_message"] = pdf_result.get("error_message")
        save_result["pdf_warning_message"] = pdf_result.get("warning_message")
        if pdf_result["status"] == "generated":
            save_result["pdf"] = pdf_result["path"]

    return save_result


def render_scouting_v2_markdown(result: dict[str, Any]) -> str:
    profile_a = result.get("profile_a", {})
    profile_b = result.get("profile_b") or {}
    warnings = result.get("warnings", [])
    language_warnings = result.get("language_warnings", [])
    lines = [
        "# Reporte Scouting AI v2",
        "",
        "## Datos generales",
        "",
        f"- **Modo:** {result.get('mode')}",
        f"- **Jugador A:** {profile_a.get('player_name')} ({profile_a.get('team_name')})",
        f"- **Match ID A:** {result.get('match_id_a')}",
        f"- **Player ID A:** {result.get('player_id_a')}",
        f"- **Arquetipo A:** {profile_a.get('archetype')} ({profile_a.get('confidence')}/100)",
    ]
    if result.get("mode") == "comparativo":
        lines.extend(
            [
                f"- **Jugador B:** {profile_b.get('player_name')} ({profile_b.get('team_name')})",
                f"- **Match ID B:** {result.get('match_id_b')}",
                f"- **Player ID B:** {result.get('player_id_b')}",
                f"- **Arquetipo B:** {profile_b.get('archetype')} ({profile_b.get('confidence')}/100)",
            ]
        )
    lines.extend(
        [
            f"- **Modelo:** {result.get('model')}",
            f"- **Generado en:** {result.get('generated_at')}",
            "",
            _strip_top_heading(str(result.get("narrative_markdown") or "")),
            "",
            "## Tabla de perfiles",
            "",
            "| Jugador | Arquetipo principal | Score | Arquetipo secundario | Score secundario |",
            "| --- | --- | ---: | --- | ---: |",
            _profile_row(profile_a),
        ]
    )
    if result.get("mode") == "comparativo":
        lines.append(_profile_row(profile_b))

    lines.extend(["", "## Advertencias", ""])
    all_warnings = list(warnings)
    all_warnings.extend(f"Lenguaje: {warning}" for warning in language_warnings)
    if all_warnings:
        lines.extend(f"- {warning}" for warning in all_warnings)
    else:
        lines.append("- No se detectaron advertencias.")

    lines.extend(
        [
            "",
            "## Trazabilidad",
            "",
            "- Fuente: StatsBomb Open Data transformada a DuckDB analítico.",
            "- Perfil inferido desde métricas observadas: xG, tiros, pases clave, asistencias, pases, precisión, progresión, presión, duelos e impacto.",
            "- El arquetipo describe comportamientos en el partido; no sustituye revisión de video ni muestra longitudinal.",
            "",
        ]
    )
    return "\n".join(lines)


def render_scouting_v2_html(result: dict[str, Any], markdown_text: str | None = None) -> str:
    markdown_text = markdown_text if markdown_text is not None else render_scouting_v2_markdown(result)
    body = markdown.markdown(markdown_text, extensions=["tables", "sane_lists"])
    title = html.escape(_html_title(result))
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #17212b;
      --muted: #5f6b76;
      --line: #dce3ea;
      --accent: #1b6957;
      --soft: #edf7f2;
    }}
    body {{
      margin: 0;
      background: #f5f7fa;
      color: var(--ink);
      font-family: "Segoe UI", Arial, sans-serif;
      line-height: 1.58;
    }}
    main {{
      max-width: 1040px;
      min-height: 100vh;
      margin: 0 auto;
      padding: 42px 28px 68px;
      background: #fff;
      box-shadow: 0 0 0 1px rgba(23, 33, 43, 0.07);
    }}
    h1 {{
      margin: 0 0 26px;
      padding-bottom: 14px;
      border-bottom: 4px solid var(--accent);
      font-size: 32px;
    }}
    h2 {{
      margin-top: 32px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--line);
      color: #153f35;
      font-size: 22px;
    }}
    p, li {{ color: var(--ink); }}
    table {{
      width: 100%;
      border-collapse: collapse;
      margin: 16px 0 24px;
      font-size: 14px;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{ background: var(--soft); color: #153f35; }}
  </style>
</head>
<body>
  <main>
    {body}
  </main>
</body>
</html>
"""


def _build_paths(
    match_a: int,
    player_a: int,
    match_b: Any,
    player_b: Any,
) -> tuple[datetime, str, dict[str, Path]]:
    exported_at = datetime.now()
    while True:
        suffix = exported_at.strftime("%Y%m%d_%H%M%S")
        if match_b is not None and player_b is not None:
            base_name = f"scouting_v2.match-{match_a}.{player_a}_vs_match-{int(match_b)}.{int(player_b)}_{suffix}"
        else:
            base_name = f"scouting_v2.match-{match_a}.{player_a}_{suffix}"
        paths = {
            "markdown": SCOUTING_DIR / f"{base_name}.md",
            "html": SCOUTING_DIR / f"{base_name}.html",
            "json": SCOUTING_DIR / f"{base_name}.json",
            "pdf": SCOUTING_DIR / f"{base_name}.pdf",
            "docx": SCOUTING_DIR / f"{base_name}.docx",
        }
        if not any(path.exists() for path in paths.values()):
            return exported_at, suffix, paths
        exported_at += timedelta(seconds=1)


def _profile_row(profile: dict[str, Any]) -> str:
    secondary = profile.get("secondary_archetype", {})
    return (
        f"| {profile.get('player_name')} | {profile.get('archetype')} | "
        f"{profile.get('confidence')} | {secondary.get('name')} | {secondary.get('score')} |"
    )


def _strip_top_heading(markdown_text: str) -> str:
    lines = markdown_text.strip().splitlines()
    if lines and lines[0].startswith("# "):
        return "\n".join(lines[1:]).strip()
    return markdown_text.strip()


def _html_title(result: dict[str, Any]) -> str:
    profile_a = result.get("profile_a", {})
    profile_b = result.get("profile_b") or {}
    if result.get("mode") == "comparativo":
        return f"Scouting v2 {profile_a.get('player_name')} vs {profile_b.get('player_name')}"
    return f"Scouting v2 {profile_a.get('player_name')}"


def _public_path(path_value: str | Path) -> str:
    path = path_value if isinstance(path_value, Path) else Path(str(path_value))
    if not path.is_absolute():
        return path.as_posix()
    return project_relative(path)
