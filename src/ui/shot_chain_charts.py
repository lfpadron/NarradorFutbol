"""Pitch artwork and a shared timeline for shot-chain stills and video."""

from __future__ import annotations

from io import BytesIO
from math import hypot, pi, sin
from textwrap import fill
from typing import Any

from matplotlib.backends.backend_agg import FigureCanvasAgg
from matplotlib.figure import Figure
from matplotlib.patches import Arc, Circle, FancyArrowPatch, Rectangle
import numpy as np

from src.analytics.shot_chains import shot_chain_title

HOME_COLOR = "#d62728"
AWAY_COLOR = "#1f77b4"
INK = "#e9f3f2"
MUTED = "#8eaaa9"
GOLD = "#ffcf5b"
BACKGROUND = "#081b23"


def oriented_point(point: list[float], is_home: bool) -> list[float]:
    # Match the fixed home-right / away-left convention in the advanced charts.
    return [point[0] if is_home else 120 - point[0], point[1]]


def _path_point(path: list[list[float]], fraction: float) -> list[float]:
    if len(path) == 1:
        return list(path[0])
    distances = [hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:])]
    distance = min(1.0, max(0.0, fraction)) * sum(distances)
    for a, b, length in zip(path, path[1:], distances):
        if distance <= length and length > 0:
            ratio = distance / length
            return [a[0] + ratio * (b[0] - a[0]), a[1] + ratio * (b[1] - a[1])]
        distance -= length
    return list(path[-1])


def build_animation_timeline(chain: dict[str, Any]) -> list[dict[str, Any]]:
    """Positions remain in event coordinates until the rendering step."""
    timeline: list[dict[str, Any]] = []
    elapsed = 0.0

    def add(kind: str, index: int, path: list[list[float]], duration: float) -> None:
        nonlocal elapsed
        timeline.append({"kind": kind, "stage": index, "path": path, "start": elapsed, "duration": duration})
        elapsed += duration

    stages = chain["stages"]
    add("hold", 0, [stages[0]["movement"][0]], 0.7)
    for index, stage in enumerate(stages):
        path = stage["movement"]
        distance = sum(hypot(b[0] - a[0], b[1] - a[1]) for a, b in zip(path, path[1:]))
        add("move", index, path, max(0.45, min(1.8, distance / 17)))
        if not stage["is_shot"]:
            add("pass", index, [path[-1], stage["end"]], 0.9)
        elif chain["is_goal"]:
            endpoint = stage.get("end") or [120, 40]
            goal_y = min(43.4, max(36.6, endpoint[1]))
            add("shot", index, [path[-1], [120, goal_y], [123, goal_y]], 0.85)
            add("rebound", index, [[123, goal_y], [120.8, 40], [122, 40.8]], 0.65)
            add("hold", index, [[122, 40.8]], 1.7)
        else:
            # Stylized exit for non-goals, including saves/blocks; never imply a goal.
            endpoint = stage.get("end") or [120, 32]
            projected_y = endpoint[1]
            if 35 < projected_y < 45:
                projected_y = 31 if path[-1][1] <= 40 else 49
            projected_y = max(-2, min(82, projected_y))
            add("shot", index, [path[-1], [120, projected_y], [129, projected_y]], 1.1)
            add("hold", index, [[129, projected_y]], 1.4)
    return timeline


def animation_state(chain: dict[str, Any], timeline: list[dict[str, Any]], seconds: float) -> dict[str, Any]:
    phase = timeline[-1]
    for item in timeline:
        if seconds < item["start"] + item["duration"]:
            phase = item
            break
    progress = min(1.0, max(0.0, (seconds - phase["start"]) / phase["duration"]))
    fraction = progress * progress * (3 - 2 * progress)
    index = phase["stage"]
    stages = chain["stages"]
    players = {}
    for stage in stages[:index]:
        players[stage["player_id"]] = stage["movement"][-1]
    stage = stages[index]
    players[stage["player_id"]] = (
        _path_point(phase["path"], fraction)
        if phase["kind"] == "move"
        else (
            stage["movement"][0]
            if index == 0 and phase["kind"] == "hold" and phase["start"] == 0
            else stage["movement"][-1]
        )
    )
    if phase["kind"] == "pass":
        receiver = stages[index + 1]
        previous = players.get(receiver["player_id"], receiver["movement"][0])
        players[receiver["player_id"]] = _path_point([previous, receiver["movement"][0]], fraction)
    ball = _path_point(phase["path"], fraction)
    lift = sin(pi * progress) * (2.0 if phase["kind"] == "pass" else 1.2) if phase["kind"] in {"pass", "shot"} else 0
    return {
        "players": players,
        "ball": ball,
        "lift": lift,
        "stage": index,
        "kind": phase["kind"],
        "progress": progress,
        "goal": chain["is_goal"] and phase["kind"] in {"rebound", "hold"} and phase["start"] > 0.7,
        "finished": seconds >= timeline[-1]["start"],
    }


def _pitch(ax: Any) -> None:
    ax.set(xlim=(-7, 130), ylim=(86, -6), aspect="equal")
    ax.axis("off")
    ax.add_patch(Rectangle((0, 0), 120, 80, facecolor="#103e3d", zorder=0))
    for x in range(0, 120, 20):
        ax.add_patch(Rectangle((x, 0), 10, 80, facecolor="#124745", zorder=0))
    line = {"edgecolor": "#78a29a", "facecolor": "none", "linewidth": 1.1}
    for x, y, width, height in [(0, 0, 120, 80), (0, 18, 18, 44), (102, 18, 18, 44), (0, 30, 6, 20), (114, 30, 6, 20)]:
        ax.add_patch(Rectangle((x, y), width, height, **line))
    ax.plot([60, 60], [0, 80], color="#78a29a", linewidth=1.1)
    ax.add_patch(Circle((60, 40), 10, **line))
    for x in (12, 60, 108):
        ax.add_patch(Circle((x, 40), 0.55, color="#abc9bd"))
    ax.add_patch(Arc((12, 40), 20, 20, theta1=-53, theta2=53, edgecolor="#78a29a", lw=1))
    ax.add_patch(Arc((108, 40), 20, 20, theta1=127, theta2=233, edgecolor="#78a29a", lw=1))
    for x in (-4, 120):
        ax.add_patch(Rectangle((x, 36), 4, 8, facecolor="#1c3540", edgecolor="#cfdbde", lw=1.5))
        for offset in (1, 2, 3):
            ax.plot([x + offset, x + offset], [36, 44], color="#70838c", lw=0.35)
        for y in (38, 40, 42):
            ax.plot([x, x + 4], [y, y], color="#70838c", lw=0.35)


def _figure(chain: dict[str, Any], language: str) -> tuple[Figure, Any]:
    english = language == "en"
    figure = Figure(figsize=(14, 8), dpi=100, facecolor=BACKGROUND)
    FigureCanvasAgg(figure)
    figure.text(
        0.045, 0.943, "SHOT SEQUENCE" if english else "SECUENCIA DE REMATE", color=MUTED, size=10, weight="bold"
    )
    figure.text(
        0.045, 0.887, shot_chain_title(chain, language), color=GOLD if chain["is_goal"] else INK, size=22, weight="bold"
    )
    figure.text(0.045, 0.834, f"{chain['home_team']}  →", color="#ff737b", size=10, weight="bold")
    figure.text(0.75, 0.834, f"←  {chain['away_team']}", ha="right", color="#6cbcff", size=10, weight="bold")
    ax = figure.add_axes((0.025, 0.15, 0.75, 0.665))
    _pitch(ax)
    panel = figure.add_axes((0.79, 0.17, 0.185, 0.64))
    panel.axis("off")
    panel.add_patch(Rectangle((0, 0), 1, 1, color="#102a33", transform=panel.transAxes))
    panel.text(0.08, 0.94, "THE BUILD-UP" if english else "LA JUGADA", color=MUTED, size=10, weight="bold")
    color = HOME_COLOR if chain["is_home"] else AWAY_COLOR
    for index, stage in enumerate(chain["stages"]):
        y = 0.82 - index * 0.19
        panel.scatter(
            [0.1],
            [y],
            s=180 if stage["is_shot"] else 120,
            marker="*" if stage["is_shot"] else "o",
            c=color,
            edgecolors=GOLD if stage["is_shot"] else INK,
        )
        action = (
            ("GOAL" if english else "GOL")
            if stage["is_shot"] and chain["is_goal"]
            else ("SHOT" if english else "TIRO") if stage["is_shot"] else ("PASS" if english else "PASE")
        )
        panel.text(
            0.21,
            y + 0.01,
            f"{index + 1:02d}  {action}",
            color=GOLD if stage["is_shot"] else MUTED,
            size=9,
            weight="bold",
        )
        panel.text(0.21, y - 0.035, fill(stage["player_name"], 22), va="top", color=INK, size=10, linespacing=1.3)
    panel.set(xlim=(0, 1), ylim=(0, 1))
    legend = (
        "● Player   ★ Shooter     ━ Pass / shot     ··· Movement"
        if english
        else "● Jugador   ★ Rematador     ━ Pase / tiro     ··· Desplazamiento"
    )
    figure.text(0.047, 0.112, legend, color=INK, size=10)
    figure.text(0.047, 0.067, "STATSBOMB OPEN DATA  /  NARRADOR FÚTBOL", color=MUTED, size=8)
    note = (
        "Event reconstruction · interpolated movement"
        if english
        else "Reconstrucción por eventos · desplazamiento interpolado"
    )
    figure.text(0.975, 0.067, note, ha="right", color=MUTED, size=8)
    return figure, ax


def _position_labels(ax: Any, labels: list[Any], points: list[list[float]]) -> None:
    """Place names using their rendered extents, including repeated players."""
    from matplotlib.transforms import Bbox

    renderer = ax.figure.canvas.get_renderer()
    obstacles = [Bbox.from_bounds(x - 12, y - 12, 24, 24) for x, y in ax.transData.transform(points)]
    placed = []
    candidates = [(0, 26), (0, -28), (-72, 14), (72, 14), (0, 53), (0, -55), (-84, -34), (84, -34)]
    for label in labels:
        if not label.get_visible():
            continue
        best_offset, best_score = candidates[0], float("inf")
        label.set_verticalalignment("center")
        for rank, offset in enumerate(candidates):
            label.set_position(offset)
            box = label.get_window_extent(renderer).expanded(1.08, 1.18)
            score = rank * 2.0
            for obstacle in [*obstacles, *placed]:
                intersection = Bbox.intersection(box, obstacle)
                if intersection is not None:
                    score += intersection.width * intersection.height
            if box.x0 < ax.bbox.x0 or box.x1 > ax.bbox.x1 or box.y0 < ax.bbox.y0 or box.y1 > ax.bbox.y1:
                score += 20000
            if score < best_score:
                best_offset, best_score = offset, score
        label.set_position(best_offset)
        placed.append(label.get_window_extent(renderer).expanded(1.08, 1.18))


def _arrow(ax: Any, start: list[float], end: list[float], color: str, alpha: float = 1.0) -> Any:
    patch = FancyArrowPatch(
        start,
        end,
        arrowstyle="-|>",
        mutation_scale=15,
        linewidth=2.5,
        color=color,
        alpha=alpha,
        zorder=3,
        shrinkA=9,
        shrinkB=9,
    )
    ax.add_patch(patch)
    return patch


def render_shot_chain_png(chain: dict[str, Any], language: str = "es") -> bytes:
    figure, ax = _figure(chain, language)
    color = HOME_COLOR if chain["is_home"] else AWAY_COLOR
    labels = []
    points = []
    shooter = chain["stages"][-1]["player_id"]
    for index, stage in enumerate(chain["stages"]):
        movement = [oriented_point(point, chain["is_home"]) for point in stage["movement"]]
        if len(movement) > 1:
            ax.plot(*zip(*movement), color=color, linewidth=2, linestyle=(0, (2, 3)), alpha=0.9)
            ax.scatter(*movement[0], s=60, facecolors="none", edgecolors=color, linewidths=1.5, zorder=4)
        end = stage.get("end")
        if end is not None:
            _arrow(ax, movement[-1], oriented_point(end, chain["is_home"]), GOLD if stage["is_shot"] else color)
        x, y = movement[-1]
        star = stage["player_id"] == shooter
        ax.scatter(
            [x],
            [y],
            s=420 if star else 230,
            marker="*" if star else "o",
            c=color,
            edgecolors=GOLD if star else INK,
            linewidths=1.8,
            zorder=5,
        )
        if not star:
            ax.text(x, y, str(index + 1), color="white", size=9, ha="center", va="center", weight="bold", zorder=6)
        label = ax.annotate(
            fill(stage["player_name"], 23),
            (x, y),
            xytext=(0, 26),
            textcoords="offset points",
            ha="center",
            va="bottom",
            color=INK,
            size=9,
            weight="bold",
            zorder=7,
            bbox={"boxstyle": "round,pad=0.35", "facecolor": BACKGROUND, "edgecolor": "none", "alpha": 0.9},
        )
        labels.append(label)
        points.append([x, y])
    _position_labels(ax, labels, points)
    buffer = BytesIO()
    figure.savefig(buffer, format="png", dpi=140, facecolor=BACKGROUND)
    figure.clear()
    return buffer.getvalue()


class ShotAnimationScene:
    """Agg scene with a cached pitch background for efficient MP4 encoding."""

    def __init__(self, chain: dict[str, Any], language: str = "es") -> None:
        self.chain = chain
        self.language = language
        self.timeline = build_animation_timeline(chain)
        self.duration = self.timeline[-1]["start"] + self.timeline[-1]["duration"]
        self.figure, self.ax = _figure(chain, language)
        self.color = HOME_COLOR if chain["is_home"] else AWAY_COLOR
        self.artists = []
        self.players = {}
        shooter = chain["stages"][-1]["player_id"]
        for stage in chain["stages"]:
            actor = stage["player_id"]
            if actor in self.players:
                continue
            star = actor == shooter
            (marker,) = self.ax.plot(
                [],
                [],
                linestyle="none",
                marker="*" if star else "o",
                markersize=21 if star else 13,
                markerfacecolor=self.color,
                markeredgecolor=GOLD if star else "white",
                markeredgewidth=1.5,
                zorder=8,
                animated=True,
            )
            label = self.ax.annotate(
                fill(stage["player_name"], 23),
                (0, 0),
                xytext=(0, 26),
                textcoords="offset points",
                ha="center",
                va="bottom",
                color=INK,
                size=9,
                weight="bold",
                bbox={"boxstyle": "round,pad=0.3", "facecolor": BACKGROUND, "edgecolor": "none", "alpha": 0.9},
                zorder=9,
                animated=True,
            )
            self.players[actor] = (marker, label)
            self.artists.extend([marker, label])
        self.paths = []
        for stage in chain["stages"]:
            (trail,) = self.ax.plot(
                [], [], color=GOLD if stage["is_shot"] else self.color, lw=2.5, alpha=0.8, animated=True, zorder=3
            )
            self.paths.append(trail)
        self.artists = [*self.paths, *self.artists]
        (self.shadow,) = self.ax.plot([], [], "o", color="#000000", alpha=0.38, markersize=9, animated=True, zorder=10)
        (self.ball,) = self.ax.plot(
            [],
            [],
            "o",
            markerfacecolor="white",
            markeredgecolor="#26333e",
            markeredgewidth=1.8,
            markersize=8,
            animated=True,
            zorder=11,
        )
        self.banner = self.ax.text(60, 9, "", ha="center", color=GOLD, size=24, weight="bold", animated=True, zorder=12)
        self.artists.extend([self.shadow, self.ball, self.banner])
        self.figure.canvas.draw()
        self.background = self.figure.canvas.copy_from_bbox(self.figure.bbox)

    def frame(self, seconds: float) -> np.ndarray:
        state = animation_state(self.chain, self.timeline, seconds)
        self.figure.canvas.restore_region(self.background)
        for actor, (marker, label) in self.players.items():
            point = state["players"].get(actor)
            marker.set_visible(point is not None)
            label.set_visible(point is not None)
            if point is not None:
                x, y = oriented_point(point, self.chain["is_home"])
                marker.set_data([x], [y])
                label.xy = (x, y)
        _position_labels(
            self.ax,
            [label for _, label in self.players.values()],
            [oriented_point(point, self.chain["is_home"]) for point in state["players"].values()],
        )
        for index, (stage, artist) in enumerate(zip(self.chain["stages"], self.paths)):
            path = []
            if index < state["stage"]:
                path = [*stage["movement"], stage["end"]]
            elif index == state["stage"]:
                if state["kind"] in {"pass", "shot", "rebound"} or state["finished"]:
                    path = [*stage["movement"], state["ball"]]
                else:
                    path = [stage["movement"][0], state["players"][stage["player_id"]]]
            points = [oriented_point(point, self.chain["is_home"]) for point in path if point is not None]
            artist.set_data(*zip(*points) if points else ([], []))
        x, y = oriented_point(state["ball"], self.chain["is_home"])
        self.shadow.set_data([x], [y])
        self.ball.set_data([x], [y - state["lift"]])
        self.banner.set_text(("GOAL!" if self.language == "en" else "¡GOL!") if state["goal"] else "")
        for artist in self.artists:
            if artist.get_visible():
                self.ax.draw_artist(artist)
        return np.asarray(self.figure.canvas.buffer_rgba())[:, :, :3].copy()

    def close(self) -> None:
        self.figure.clear()
