"""Portable player-card artwork shared by the tab and all three exports."""

from __future__ import annotations

from io import BytesIO
from threading import RLock
from typing import Any
import textwrap

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Arc, Circle, FancyBboxPatch, Rectangle

RENDER_LOCK = RLock()
CARD_WIDTH = 452
CARD_HEIGHT = 692


def render_player_cards_png(cards: list[dict[str, Any]], language: str = "es") -> bytes:
    if not 1 <= len(cards) <= 2:
        raise ValueError("Se requieren una o dos tarjetas.")
    with RENDER_LOCK:
        width = 24 + len(cards) * CARD_WIDTH + (len(cards) - 1) * 16
        figure = Figure(figsize=(width / 100, 720 / 100), dpi=100, facecolor="#111827")
        FigureCanvasAgg(figure)
        axis = figure.add_axes((0, 0, 1, 1))
        axis.set(xlim=(0, width), ylim=(720, 0))
        axis.set_axis_off()
        for index, card in enumerate(cards):
            _draw_card(axis, 12 + index * (CARD_WIDTH + 16), card, language)
        output = BytesIO()
        figure.savefig(output, format="png", dpi=200, facecolor=figure.get_facecolor())
        figure.clear()
        return output.getvalue()


def _draw_card(axis: Any, x: float, card: dict[str, Any], language: str) -> None:
    english = language == "en"
    stats = card["stats"]

    def label(es: str, en: str) -> str:
        return en if english else es

    def text(px: float, py: float, value: str, size: float = 12, **kwargs: Any) -> Any:
        return axis.text(
            x + px,
            py,
            value,
            fontsize=size * 0.72,
            fontfamily="DejaVu Sans",
            va="top",
            color=kwargs.pop("color", "#0f172a"),
            **kwargs,
        )

    def box(px: float, py: float, width: float, height: float, edge: str, face: str = "#eef1f4") -> Any:
        patch = FancyBboxPatch(
            (x + px, py),
            width,
            height,
            boxstyle="round,pad=0,rounding_size=9",
            linewidth=0.7,
            edgecolor=edge,
            facecolor=face,
        )
        axis.add_patch(patch)
        return patch

    outer = box(0, 14, CARD_WIDTH, CARD_HEIGHT, "#dbe4ed", "#e7ecf1")
    header = Rectangle((x, 14), CARD_WIDTH, 106, linewidth=0, facecolor="#aacae9")
    header.set_clip_path(outer)
    axis.add_patch(header)
    match = card["match"]
    scoreline = (
        f"{match.get('home_team_name', '')} {match.get('home_score', '–')} - "
        f"{match.get('away_score', '–')} {match.get('away_team_name', '')}"
    )
    context = f"{match.get('competition_name') or ''} · {scoreline} · {match.get('match_date') or ''}".strip(" ·")
    _fit_text(text(226, 25, "\n".join(textwrap.wrap(context, 100)), 8, ha="center"), 424, 19)
    name = str(card["player_name"])
    name_lines = textwrap.wrap(name, 27, break_long_words=True) or [name]
    name_size = min(23, 560 / max(len(line) for line in name_lines))
    _fit_text(text(14, 47, "\n".join(name_lines), name_size, weight="bold", linespacing=1.05), 347, 44)
    start, end = card.get("start_minute"), card.get("end_minute")
    unavailable = "N/A" if english else "N/D"
    interval = f"{start}'–{end}'" if start is not None and end is not None else unavailable
    details = f"{card.get('team_name') or ''} · {card.get('position') or unavailable} · {interval}"
    # Long names and roles stay within the header, without crossing the rating badge.
    detail_y = 98 if len(name_lines) > 1 else 80
    _fit_text(text(14, detail_y, "\n".join(textwrap.wrap(details, 62)), 10, linespacing=1.1), 347, 18)
    box(371, 46, 67, 60, "#fff54a", "#aacae9")
    text(404.5, 53, label("Nota", "Rating"), 10, ha="center")
    text(404.5, 71, unavailable, 20, ha="center", weight="bold")

    box(11, 128, 430, 38, "#ff7c24")
    text(
        226,
        140,
        f"{label('Tiros', 'Shots')}: {stats['shots']}  ·  "
        f"{label('Goles', 'Goals')}: {stats['goals']}  ·  xG: {stats['xg']:.2f}",
        13,
        ha="center",
        weight="bold",
    )

    groups = [
        (
            11,
            170,
            84,
            "#9459ff",
            [
                f"{label('Pases', 'Passing')}: {stats['completed_passes']}/{stats['passes']}",
                f"{label('Último tercio', 'Final-third passes')}: {stats['completed_final_third_passes']}/{stats['final_third_passes']}",
                f"{label('Pases largos', 'Long passes')}: {stats['completed_long_passes']}/{stats['long_passes']}",
                f"{label('Pases clave', 'Key passes')}: {stats['key_passes']}",
            ],
        ),
        (
            230,
            170,
            84,
            "#bfbd00",
            [
                f"{label('Presiones', 'Pressures')}: {stats['pressures']}",
                f"{label('Entradas', 'Tackles')}: {stats['won_tackles']}/{stats['tackles']}",
                f"{label('Despejes', 'Clearances')}: {stats['clearances']}",
                f"{label('Bloqueos', 'Blocks')}: {stats['blocks']}",
            ],
        ),
        (
            11,
            263,
            67,
            "#477cff",
            [
                f"{label('Regates', 'Dribbles')}: {stats['completed_dribbles']}/{stats['dribbles']}",
                f"{label('Conducciones progresivas', 'Progressive carries')}: {stats['progressive_carries']}",
            ],
        ),
        (
            230,
            263,
            67,
            "#ff5364",
            [
                f"{label('Desposesiones', 'Dispossessed')}: {stats['dispossessed']}",
                f"{label('Veces superado', 'Dribbled past')}: {stats['dribbled_past']}",
                f"{label('Malos controles', 'Miscontrols')}: {stats['miscontrols']}",
            ],
        ),
    ]
    for px, py, height, color, lines in groups:
        box(px, py, 211, height, color)
        for index, line in enumerate(lines):
            _fit_text(text(px + 10, py + 12 + index * 16, line, 11, weight="bold"), 191, 14)

    box(11, 338, 430, 37, "#67a91b")
    card_labels = {
        "Yellow Card": label("Amarilla", "Yellow"),
        "Second Yellow": label("2ª amarilla", "2nd yellow"),
        "Red Card": label("Roja", "Red"),
    }
    bookings = ", ".join(card_labels.get(value, value) for value in card["cards"]) or label("Ninguna", "None")
    text(
        226,
        345,
        f"{label('Faltas', 'Fouls')}: {stats['fouls_committed']}  ·  "
        f"{label('Recibidas', 'Won')}: {stats['fouls_won']}",
        11,
        ha="center",
        weight="bold",
    )
    text(226, 360, f"{label('Tarjetas', 'Cards')}: {bookings}", 10, ha="center")

    for px, title in (
        (11, label("Recepciones de balón", "Ball receiving")),
        (230, label("Mapa de pases", "Passing map")),
    ):
        box(px, 385, 211, 310, "#eef1f4")
        text(px + 105.5, 393, title, 11, ha="center", weight="bold")
        _pitch(axis, x + px + 7, 410, 197, 260)

    def pitch_point(point: tuple[float, float], px: float) -> tuple[float, float]:
        # StatsBomb attacks towards x=120; rotate so the attacking goal is at the top.
        return x + px + 7 + point[1] * 197 / 80, 670 - point[0] * 260 / 120

    for points, color in ((card["receptions"], "#ef4444"), (card["recoveries"], "#2563eb")):
        for point in points:
            axis.plot(*pitch_point(point, 11), marker="o", markersize=3.6, color=color, alpha=0.85, markeredgewidth=0)
    for event in card["passes"]:
        begin, end = pitch_point(event["start"], 230), pitch_point(event["end"], 230)
        axis.annotate(
            "",
            xy=end,
            xytext=begin,
            arrowprops={
                "arrowstyle": "-|>",
                "color": "#4f7eff",
                "lw": 0.7,
                "alpha": 0.70,
                "mutation_scale": 5,
                "shrinkA": 0,
                "shrinkB": 0,
            },
        )
        axis.plot(
            *begin,
            marker="o",
            markersize=2.2,
            markerfacecolor="#c8d5ff",
            markeredgecolor="#4f7eff",
            markeredgewidth=0.35,
            alpha=0.8,
        )
    if not card["receptions"] and not card["recoveries"]:
        text(116, 526, label("Sin eventos con ubicación", "No located events"), 9, ha="center", color="#64748b")
    if not card["passes"]:
        text(335, 526, label("Sin pases con ubicación", "No located passes"), 9, ha="center", color="#64748b")
    axis.plot(x + 22, 683, "o", color="#ef4444", markersize=3)
    text(28, 678, label("Recepción", "Reception"), 8)
    axis.plot(x + 119, 683, "o", color="#2563eb", markersize=3)
    text(125, 678, label("Recuperación", "Recovery"), 8)
    axis.plot([x + 242, x + 254], [683, 683], color="#4f7eff", linewidth=0.7)
    text(258, 678, label("Trayectoria", "Trajectory"), 8)
    axis.plot(x + 348, 683, "o", markerfacecolor="#c8d5ff", markeredgecolor="#4f7eff", markersize=3)
    text(354, 678, label("Inicio", "Pass start"), 8)


def _fit_text(artist: Any, width: float, height: float) -> None:
    """Fit unusually long names/labels without truncating or overlapping the badge."""
    bounds = artist.get_window_extent(artist.figure.canvas.get_renderer())
    scale = min(1, width / max(bounds.width, 1), height / max(bounds.height, 1))
    if scale < 1:
        artist.set_fontsize(artist.get_fontsize() * scale)


def _pitch(axis: Any, x: float, y: float, width: float, height: float) -> None:
    color = "#374151"
    axis.add_patch(Rectangle((x, y), width, height, facecolor="#f5f6f8", edgecolor=color, linewidth=0.8))
    axis.plot([x, x + width], [y + height / 2] * 2, color=color, linewidth=0.8)
    # Coordinates below use the native 120 x 80 yard pitch proportions.
    for top in (True, False):
        baseline = y if top else y + height
        for box_width, depth in ((44, 18), (20, 6)):
            h = height * depth / 120
            axis.add_patch(
                Rectangle(
                    (x + width * (80 - box_width) / 160, baseline if top else baseline - h),
                    width * box_width / 80,
                    h,
                    fill=False,
                    edgecolor=color,
                    linewidth=0.8,
                )
            )
        axis.add_patch(
            Circle(
                (x + width / 2, baseline + (1 if top else -1) * height * 12 / 120), 1.7, facecolor=color, linewidth=0
            )
        )
    axis.add_patch(
        Arc(
            (x + width / 2, y + height / 2),
            width * 20 / 80,
            height * 20 / 120,
            theta1=0,
            theta2=360,
            edgecolor=color,
            linewidth=0.8,
        )
    )
    axis.add_patch(Circle((x + width / 2, y + height / 2), 1.7, facecolor=color, linewidth=0))
