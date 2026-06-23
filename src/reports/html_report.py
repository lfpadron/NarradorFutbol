"""HTML renderer for final match reports."""

from __future__ import annotations

import markdown

from src.reports.markdown_report import render_markdown_report


def render_html_report(report: dict) -> str:
    markdown_text = render_markdown_report(report)
    body = markdown.markdown(markdown_text, extensions=["tables", "sane_lists"])
    title = _html_title(report)
    return f"""<!doctype html>
<html lang="es">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{title}</title>
  <style>
    :root {{
      color-scheme: light;
      --ink: #16202a;
      --muted: #5b6875;
      --line: #d9e0e7;
      --accent: #0f766e;
      --soft: #eef7f5;
    }}
    body {{
      margin: 0;
      font-family: "Segoe UI", Arial, sans-serif;
      color: var(--ink);
      background: #f6f8fb;
      line-height: 1.55;
    }}
    main {{
      max-width: 1040px;
      margin: 0 auto;
      padding: 40px 24px 64px;
      background: #ffffff;
      min-height: 100vh;
      box-shadow: 0 0 0 1px rgba(22, 32, 42, 0.06);
    }}
    h1 {{
      margin: 0 0 24px;
      font-size: 34px;
      border-bottom: 4px solid var(--accent);
      padding-bottom: 14px;
    }}
    h2 {{
      margin-top: 34px;
      padding-bottom: 8px;
      border-bottom: 1px solid var(--line);
      font-size: 23px;
    }}
    h3 {{ margin-top: 24px; }}
    p, li {{ color: var(--ink); }}
    strong {{ color: #0b1720; }}
    table {{
      border-collapse: collapse;
      width: 100%;
      margin: 16px 0 24px;
      font-size: 14px;
    }}
    th, td {{
      border: 1px solid var(--line);
      padding: 8px 10px;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      background: var(--soft);
      color: #0b3b37;
      font-weight: 700;
    }}
    code {{
      background: #eef1f5;
      padding: 2px 5px;
      border-radius: 4px;
    }}
    ul {{ padding-left: 22px; }}
  </style>
</head>
<body>
  <main>
    {body}
  </main>
</body>
</html>
"""


def _html_title(report: dict) -> str:
    summary = report.get("match_summary", {})
    return (
        f"Reporte {summary.get('home_team_name', '')} "
        f"{summary.get('home_score', '')}-{summary.get('away_score', '')} "
        f"{summary.get('away_team_name', '')}"
    ).strip()

