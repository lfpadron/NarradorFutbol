"""Portable PDF and H.264/MP4 exports of the shot-chain artwork."""

from __future__ import annotations

from io import BytesIO
import math
from pathlib import Path
import shutil
import subprocess
import tempfile
from threading import RLock
from typing import Any

from src.analytics.shot_chains import shot_chain_title
from src.ui.shot_chain_charts import ShotAnimationScene

# Matplotlib is not thread-safe; serialize video scenes across Streamlit sessions.
RENDER_LOCK = RLock()


def shot_chain_pdf(chain: dict[str, Any], png: bytes, language: str = "es") -> bytes:
    from reportlab.lib.pagesizes import A4, landscape
    from reportlab.lib.utils import ImageReader
    from reportlab.pdfgen.canvas import Canvas

    output = BytesIO()
    width, height = landscape(A4)
    canvas = Canvas(output, pagesize=(width, height))
    canvas.setTitle(shot_chain_title(chain, language))
    canvas.setAuthor("Narrador Fútbol")
    canvas.setFillColorRGB(8 / 255, 27 / 255, 35 / 255)
    canvas.rect(0, 0, width, height, fill=1, stroke=0)
    image = ImageReader(BytesIO(png))
    image_width, image_height = image.getSize()
    scale = min(width / image_width, height / image_height)
    display_width, display_height = image_width * scale, image_height * scale
    canvas.drawImage(image, (width - display_width) / 2, (height - display_height) / 2, display_width, display_height)
    canvas.showPage()
    canvas.save()
    return output.getvalue()


def shot_chain_video(chain: dict[str, Any], language: str = "es", fps: int = 24) -> bytes:
    executable = shutil.which("ffmpeg")
    if not executable:
        raise RuntimeError(
            "Install FFmpeg on the Streamlit server to generate MP4 videos."
            if language == "en"
            else "Instala FFmpeg en el servidor de Streamlit para generar videos MP4."
        )
    if not 1 <= fps <= 60:
        raise ValueError("fps must be between 1 and 60")
    with RENDER_LOCK:
        scene = ShotAnimationScene(chain, language)
        try:
            width, height = scene.figure.canvas.get_width_height()
            with tempfile.TemporaryDirectory(prefix="narrador-shot-") as directory:
                video_path = Path(directory) / "shot.mp4"
                with tempfile.TemporaryFile() as errors:
                    command = [
                        executable,
                        "-hide_banner",
                        "-loglevel",
                        "error",
                        "-y",
                        "-f",
                        "rawvideo",
                        "-vcodec",
                        "rawvideo",
                        "-s",
                        f"{width}x{height}",
                        "-pix_fmt",
                        "rgb24",
                        "-r",
                        str(fps),
                        "-i",
                        "pipe:0",
                        "-an",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "20",
                        "-pix_fmt",
                        "yuv420p",
                        "-movflags",
                        "+faststart",
                        str(video_path),
                    ]
                    process = subprocess.Popen(
                        command,
                        stdin=subprocess.PIPE,
                        stdout=subprocess.DEVNULL,
                        stderr=errors,
                        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
                    )
                    try:
                        assert process.stdin is not None
                        for frame in range(math.ceil(scene.duration * fps)):
                            process.stdin.write(scene.frame(frame / fps).tobytes())
                        process.stdin.close()
                        if process.wait(timeout=90) != 0:
                            raise RuntimeError("FFmpeg encoding failed")
                    except (BrokenPipeError, RuntimeError, subprocess.TimeoutExpired) as exc:
                        process.kill()
                        process.wait()
                        errors.seek(0)
                        detail = errors.read(1500).decode("utf-8", errors="replace").strip()
                        raise RuntimeError(f"MP4: {detail or str(exc)}") from exc
                    finally:
                        if process.stdin and not process.stdin.closed:
                            process.stdin.close()
                        if process.poll() is None:
                            process.kill()
                            process.wait()
                return video_path.read_bytes()
        finally:
            scene.close()
