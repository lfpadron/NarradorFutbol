"""Export Scouting AI v2 reports."""

from __future__ import annotations

import html
import json
import base64
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import markdown

from src.comparison.player_visuals import player_chart_colors, plot_player_radar
from src.config import SCOUTING_DIR, project_relative
from src.ingestion.utils import to_jsonable
from src.reports.pdf_report import render_pdf_report
from src.scouting.scouting_exporter import render_scouting_docx
from src.ui.i18n import is_english, translate_text


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
    radar_png, radar_error = _render_radar_png(result)
    html_text = render_scouting_v2_html(result, markdown_text, radar_png=radar_png)
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
        "radar_status": "generated" if radar_png else "not_generated",
        "radar_error_message": radar_error,
    }

    if include_html:
        paths["html"].write_text(html_text, encoding="utf-8")
        save_result["html"] = _public_path(paths["html"])
        save_result["html_status"] = "generated"

    if include_docx:
        figures = (
            [("Scouting AI v2 Radar" if is_english(result.get("language")) else "Radar Scouting AI v2", radar_png)]
            if radar_png
            else None
        )
        docx_result = render_scouting_docx(result, markdown_text, paths["docx"].as_posix(), figures=figures)
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
    language = result.get("language")
    english = is_english(language)
    mode_value = str(result.get("mode"))
    if english and mode_value == "comparativo":
        mode_value = "comparative"
    lines = [
        "# Scouting AI v2 Report" if english else "# Reporte Scouting AI v2",
        "",
        "## General Information" if english else "## Datos generales",
        "",
        f"- **{'Mode' if english else 'Modo'}:** {mode_value}",
        f"- **{'Player A' if english else 'Jugador A'}:** {profile_a.get('player_name')} ({profile_a.get('team_name')})",
        f"- **Match ID A:** {result.get('match_id_a')}",
        f"- **Player ID A:** {result.get('player_id_a')}",
        f"- **{'Archetype A' if english else 'Arquetipo A'}:** {translate_text(profile_a.get('archetype'), language=language)} ({profile_a.get('confidence')}/100)",
    ]
    if result.get("mode") == "comparativo":
        lines.extend(
            [
                f"- **{'Player B' if english else 'Jugador B'}:** {profile_b.get('player_name')} ({profile_b.get('team_name')})",
                f"- **Match ID B:** {result.get('match_id_b')}",
                f"- **Player ID B:** {result.get('player_id_b')}",
                f"- **{'Archetype B' if english else 'Arquetipo B'}:** {translate_text(profile_b.get('archetype'), language=language)} ({profile_b.get('confidence')}/100)",
            ]
        )
    lines.extend(
        [
            f"- **{'Model' if english else 'Modelo'}:** {result.get('model')}",
            f"- **{'Generated at' if english else 'Generado en'}:** {result.get('generated_at')}",
            "",
            _strip_top_heading(str(result.get("narrative_markdown") or "")),
            "",
            "## Profile Table" if english else "## Tabla de perfiles",
            "",
            (
                "| Player | Primary archetype | Score | Secondary archetype | Secondary score |"
                if english
                else "| Jugador | Arquetipo principal | Score | Arquetipo secundario | Score secundario |"
            ),
            "| --- | --- | ---: | --- | ---: |",
            _profile_row(profile_a, language),
        ]
    )
    if result.get("mode") == "comparativo":
        lines.append(_profile_row(profile_b, language))

    lines.extend(["", "## Profile Radar" if english else "## Radar de perfil", ""])
    lines.extend(_radar_table_lines(result.get("radar_metrics", {}), language))

    lines.extend(["", "## Warnings" if english else "## Advertencias", ""])
    all_warnings = list(warnings)
    all_warnings.extend(f"{'Language' if english else 'Lenguaje'}: {warning}" for warning in language_warnings)
    if all_warnings:
        lines.extend(f"- {warning}" for warning in all_warnings)
    else:
        lines.append("- No warnings were detected." if english else "- No se detectaron advertencias.")

    lines.extend(
        [
            "",
            "## Traceability" if english else "## Trazabilidad",
            "",
            (
                "- Source: StatsBomb Open Data transformed into analytical DuckDB tables."
                if english
                else "- Fuente: StatsBomb Open Data transformada a DuckDB analítico."
            ),
            (
                "- Profile inferred from observed metrics: xG, shots, key passes, assists, passes, accuracy, progression, pressure, duels, and impact."
                if english
                else "- Perfil inferido desde métricas observadas: xG, tiros, pases clave, asistencias, pases, precisión, progresión, presión, duelos e impacto."
            ),
            (
                "- The archetype describes match behaviours; it does not replace video review or a longitudinal sample."
                if english
                else "- El arquetipo describe comportamientos en el partido; no sustituye revisión de video ni muestra longitudinal."
            ),
            "",
        ]
    )
    return "\n".join(lines)


def render_scouting_v2_html(
    result: dict[str, Any],
    markdown_text: str | None = None,
    radar_png: bytes | None = None,
) -> str:
    markdown_text = markdown_text if markdown_text is not None else render_scouting_v2_markdown(result)
    body = markdown.markdown(markdown_text, extensions=["tables", "sane_lists"])
    title = html.escape(_html_title(result))
    language = result.get("language")
    lang = "en" if is_english(language) else "es"
    radar_html = _radar_html(radar_png, language)
    return f"""<!doctype html>
<html lang="{lang}">
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
    .radar-figure {{
      margin: 18px 0 28px;
      page-break-inside: avoid;
      text-align: center;
    }}
    .radar-figure img {{
      width: 100%;
      max-width: 760px;
      height: auto;
    }}
    .radar-figure figcaption {{
      margin-top: 8px;
      color: var(--muted);
      font-size: 12px;
    }}
  </style>
</head>
<body>
  <main>
    {body}
    {radar_html}
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


def _profile_row(profile: dict[str, Any], language: object | None = None) -> str:
    secondary = profile.get("secondary_archetype", {})
    return (
        f"| {profile.get('player_name')} | {translate_text(profile.get('archetype'), language=language)} | "
        f"{profile.get('confidence')} | {translate_text(secondary.get('name'), language=language)} | "
        f"{secondary.get('score')} |"
    )


def _radar_table_lines(radar_metrics: dict[str, Any], language: object | None = None) -> list[str]:
    categories = list(radar_metrics.get("categories", []))
    player_a = radar_metrics.get("player_a", {})
    player_b = radar_metrics.get("player_b", {})
    values_a = list(player_a.get("values", []))
    values_b = list(player_b.get("values", []))
    has_player_b = bool(player_b.get("name"))
    if not categories:
        return [
            (
                "There are not enough metrics to build a radar."
                if is_english(language)
                else "No hay métricas suficientes para construir radar."
            )
        ]
    if has_player_b:
        lines = [
            (
                f"| Metric | {player_a.get('name') or 'Player A'} | {player_b.get('name') or 'Player B'} |"
                if is_english(language)
                else f"| Métrica | {player_a.get('name') or 'Jugador A'} | {player_b.get('name') or 'Jugador B'} |"
            ),
            "| --- | ---: | ---: |",
        ]
        for category, value_a, value_b in zip(categories, values_a, values_b):
            lines.append(f"| {translate_text(category, language=language)} | {value_a} | {value_b} |")
        return lines
    lines = [
        (
            f"| Metric | {player_a.get('name') or 'Player A'} |"
            if is_english(language)
            else f"| Métrica | {player_a.get('name') or 'Jugador A'} |"
        ),
        "| --- | ---: |",
    ]
    for category, value_a in zip(categories, values_a):
        lines.append(f"| {translate_text(category, language=language)} | {value_a} |")
    return lines


def _render_radar_png(result: dict[str, Any]) -> tuple[bytes | None, str | None]:
    try:
        radar_metrics = result.get("radar_metrics", {})
        if not radar_metrics.get("categories"):
            return None, (
                "Radar has no available categories."
                if is_english(result.get("language"))
                else "Radar sin categorías disponibles."
            )
        profile_a = result.get("profile_a", {})
        profile_b = result.get("profile_b") or {}
        colors = player_chart_colors(profile_a.get("team_name"), profile_b.get("team_name"))
        figure = plot_player_radar(radar_metrics, colors)
        figure.update_layout(
            title="Scouting AI v2 Radar" if is_english(result.get("language")) else "Radar Scouting AI v2",
            height=560,
        )
        return figure.to_image(format="png", width=980, height=560, scale=2), None
    except Exception as exc:
        return None, str(exc)


def _radar_html(radar_png: bytes | None, language: object | None = None) -> str:
    if not radar_png:
        return ""
    encoded = base64.b64encode(radar_png).decode("ascii")
    caption = (
        "Normalized 0-100 radar by observed tactical profile."
        if is_english(language)
        else "Radar normalizado 0-100 por perfil táctico observado."
    )
    return f"""
    <figure class="radar-figure">
      <img src="data:image/png;base64,{encoded}" alt="Radar Scouting AI v2">
      <figcaption>{caption}</figcaption>
    </figure>
    """


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
