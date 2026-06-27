"""Textual TUI to control the Podman Compose deployment."""

from __future__ import annotations

import argparse
import os
import queue
import subprocess
import threading
import time
import webbrowser
from datetime import datetime
from typing import Callable, Iterable
from urllib.error import URLError
from urllib.request import urlopen

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, RichLog, Static

from src.config import PROJECT_ROOT

APP_TITLE = "Control del Sistema Narrador de Fútbol - Podman Compose Local"
DISPLAY_TITLE = "Control del Sistema Narrador de Fútbol"
APP_PORT = 8501
APP_URL = f"http://localhost:{APP_PORT}"
SERVICE_NAME = "narrador-futbol"
HOST_VOLUME_DIRS = (
    PROJECT_ROOT / "data",
    PROJECT_ROOT / "input",
    PROJECT_ROOT / "output",
    PROJECT_ROOT / "data" / "reports",
    PROJECT_ROOT / "data" / "scouting",
    PROJECT_ROOT / "data" / "analytics",
    PROJECT_ROOT / "data" / "security",
)


class PodmanController:
    """Run Podman Compose commands and stream their logs to the TUI."""

    def __init__(self, url: str = APP_URL) -> None:
        self.url = url
        self.log_queue: queue.Queue[str] = queue.Queue()
        self._active_thread: threading.Thread | None = None

    def is_running(self) -> bool:
        return self._container_is_running()

    def start_podman(self) -> None:
        self._run_background("Arrancar Podman", ["podman", "machine", "start"])

    def build(self) -> None:
        self._run_background("Construir aplicación", ["podman", "compose", "build"])

    def up(self) -> None:
        self._ensure_host_volume_dirs()
        if self._http_responds() and not self._container_is_running():
            self.log(
                f"El puerto {APP_PORT} ya responde fuera del contenedor. "
                "Apaga Streamlit local antes de encender Podman."
            )
            return
        self._run_background("Encender contenedor", ["podman", "compose", "up", "-d"], after=self._after_up)

    def down(self) -> None:
        self._run_background("Apagar contenedor", ["podman", "compose", "down"])

    def open_browser(self) -> None:
        self.log(f"Abriendo navegador en {self.url}")
        webbrowser.open(self.url)

    def drain_logs(self) -> list[str]:
        lines: list[str] = []
        while True:
            try:
                lines.append(self.log_queue.get_nowait())
            except queue.Empty:
                return lines

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.log_queue.put(f"{timestamp}  {message}")

    def _ensure_host_volume_dirs(self) -> None:
        for path in HOST_VOLUME_DIRS:
            if path.exists() and not path.is_dir():
                self.log(f"Ruta de volumen inválida, no es directorio: {path}")
                continue
            if not path.exists():
                path.mkdir(parents=True, exist_ok=True)
                self.log(f"Directorio creado para volumen: {path.relative_to(PROJECT_ROOT)}")

    def _run_background(
        self,
        label: str,
        command: list[str],
        after: Callable[[int], None] | None = None,
    ) -> None:
        if self._active_thread and self._active_thread.is_alive():
            self.log("Ya hay un comando en ejecución. Espera a que termine.")
            return

        thread = threading.Thread(target=self._run_command, args=(label, command, after), daemon=True)
        self._active_thread = thread
        thread.start()

    def _run_command(
        self,
        label: str,
        command: list[str],
        after: Callable[[int], None] | None,
    ) -> None:
        self.log(f"{label}...")
        self.log(f"$ {' '.join(command)}")
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        creationflags = getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0) if os.name == "nt" else 0

        try:
            process = subprocess.Popen(
                command,
                cwd=PROJECT_ROOT,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                env=env,
                creationflags=creationflags,
            )
        except FileNotFoundError:
            self.log("No se encontró `podman`. Revisa que Podman Desktop esté instalado y en PATH.")
            return

        if process.stdout is not None:
            for line in process.stdout:
                cleaned = line.rstrip()
                if cleaned:
                    self.log(cleaned)

        return_code = process.wait()
        if return_code == 0:
            self.log("Comando completado.")
        else:
            self.log(f"Comando finalizó con código {return_code}.")

        if after is not None:
            after(return_code)

    def _after_up(self, return_code: int) -> None:
        if return_code != 0:
            return
        if self._wait_until_running(timeout_seconds=60):
            self.log(f"Aplicación disponible en {self.url}")
            self._log_recent_compose_logs()
        else:
            self.log("El contenedor arrancó, pero Streamlit aún no responde en el puerto esperado.")

    def _log_recent_compose_logs(self) -> None:
        completed = subprocess.run(
            ["podman", "compose", "logs", "--tail", "60", SERVICE_NAME],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.stdout.strip():
            self.log("Últimos logs del servicio:")
            for line in completed.stdout.splitlines():
                if line.strip():
                    self.log(line)

    def _wait_until_running(self, timeout_seconds: float) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self._http_responds():
                return True
            time.sleep(1)
        return False

    def _http_responds(self) -> bool:
        try:
            with urlopen(self.url, timeout=0.8) as response:
                return 200 <= response.status < 500
        except (OSError, URLError):
            return False

    def _container_is_running(self) -> bool:
        completed = subprocess.run(
            ["podman", "ps", "--filter", f"name={SERVICE_NAME}", "--format", "{{.Names}}"],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        return bool(completed.stdout.strip())


class PodmanTuiApp(App[None]):
    """Terminal UI for controlling the Podman Compose app."""

    TITLE = APP_TITLE

    CSS = """
    Screen {
        background: #07131c;
    }

    #title {
        dock: top;
        height: 3;
        content-align: center middle;
        text-style: bold;
        background: #10243a;
        color: white;
    }

    #status {
        dock: top;
        height: 3;
        content-align: center middle;
        text-style: bold;
        border-bottom: solid #1d4b61;
    }

    #main {
        height: 1fr;
    }

    #buttons {
        width: 30;
        padding: 2 2;
        border-right: solid #1d4b61;
    }

    Button {
        width: 100%;
        margin: 1 0;
        height: 3;
        text-style: bold;
    }

    #log-panel {
        padding: 2;
        width: 1fr;
    }

    #logs {
        height: 1fr;
        border: solid #1d4b61;
        background: black;
        color: white;
    }
    """

    BINDINGS = [("q", "quit", "Cerrar"), ("r", "refresh_status", "Actualizar estado")]

    def __init__(self) -> None:
        super().__init__()
        self.controller = PodmanController()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(DISPLAY_TITLE, id="title")
        yield Static("Estado: revisando...", id="status")
        with Horizontal(id="main"):
            with Vertical(id="buttons"):
                yield Button("Arrancar podman", id="start-podman", variant="primary")
                yield Button("Construir aplicación", id="build-app", variant="warning")
                yield Button("Encender", id="start-app", variant="success")
                yield Button("Abrir navegador", id="open-browser", variant="primary")
                yield Button("Apagar", id="stop-app", variant="error")
                yield Button("Cerrar", id="close-tui", variant="default")
            with Vertical(id="log-panel"):
                yield Static("Logs")
                yield RichLog(id="logs", markup=False, highlight=False, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self._write_log("TUI Podman lista.")
        self._write_log(f"URL objetivo: {APP_URL}")
        self._refresh_status()
        self.set_interval(1.0, self._tick)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-podman":
            self.controller.start_podman()
        elif event.button.id == "build-app":
            self.controller.build()
        elif event.button.id == "start-app":
            self.controller.up()
        elif event.button.id == "open-browser":
            self.controller.open_browser()
        elif event.button.id == "stop-app":
            self.controller.down()
        elif event.button.id == "close-tui":
            self.exit()
        self._refresh_status()

    def action_refresh_status(self) -> None:
        self._refresh_status()
        self._write_log("Estado actualizado.")

    def _tick(self) -> None:
        for line in self.controller.drain_logs():
            self._write_log(line)
        self._refresh_status()

    def _refresh_status(self) -> None:
        status = self.query_one("#status", Static)
        if self.controller.is_running():
            status.update(Text("Estado: encendido", style="bold green"))
        else:
            status.update(Text("Estado: apagado", style="bold red"))

    def _write_log(self, message: str) -> None:
        self.query_one("#logs", RichLog).write(message)


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TUI de control Podman para Narrador de Fútbol.")
    parser.add_argument(
        "--smoke-test",
        action="store_true",
        help="Valida imports y estado sin abrir la TUI.",
    )
    parser.add_argument(
        "--compose-config-test",
        action="store_true",
        help="Ejecuta `podman compose config --quiet` para validar compose.yaml.",
    )
    return parser.parse_args(argv)


def run_smoke_test() -> None:
    controller = PodmanController()
    print("Podman TUI smoke test OK")
    print(f"project_root={PROJECT_ROOT}")
    print(f"url={controller.url}")
    print(f"status={'encendido' if controller.is_running() else 'apagado'}")


def run_compose_config_test() -> None:
    completed = subprocess.run(
        ["podman", "compose", "config", "--quiet"],
        cwd=PROJECT_ROOT,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)
    print("podman compose config OK")


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    if args.smoke_test:
        run_smoke_test()
        return
    if args.compose_config_test:
        run_compose_config_test()
        return
    PodmanTuiApp().run()


if __name__ == "__main__":
    main()
