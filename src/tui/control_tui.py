"""Textual TUI to control the local Streamlit app."""

from __future__ import annotations

import argparse
import os
import queue
import signal
import subprocess
import sys
import threading
import time
import webbrowser
from datetime import datetime
from pathlib import Path
from typing import Iterable
from urllib.error import URLError
from urllib.request import urlopen

from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Button, Footer, Header, RichLog, Static

from src.config import PROJECT_ROOT


APP_TITLE = "Control del sistema Narrador de Fútbol"
STREAMLIT_PORT = 8501
STREAMLIT_URL = f"http://localhost:{STREAMLIT_PORT}"
PID_FILE = PROJECT_ROOT / ".tmp" / "streamlit.pid"


class StreamlitController:
    """Start, stop, and inspect the local Streamlit server."""

    def __init__(self, port: int = STREAMLIT_PORT) -> None:
        self.port = port
        self.url = f"http://localhost:{port}"
        self.process: subprocess.Popen[str] | None = None
        self.log_queue: queue.Queue[str] = queue.Queue()

    def is_running(self) -> bool:
        try:
            with urlopen(self.url, timeout=0.8) as response:
                return 200 <= response.status < 500
        except (OSError, URLError):
            return False

    def start(self) -> None:
        if self.is_running():
            self.log("Streamlit ya esta encendido.")
            return

        command = [
            sys.executable,
            "-m",
            "streamlit",
            "run",
            str(PROJECT_ROOT / "app" / "streamlit_app.py"),
            "--server.headless",
            "true",
            "--server.port",
            str(self.port),
            "--browser.gatherUsageStats",
            "false",
        ]
        env = os.environ.copy()
        env["PYTHONUTF8"] = "1"
        env["STREAMLIT_BROWSER_GATHER_USAGE_STATS"] = "false"
        creationflags = subprocess.CREATE_NEW_PROCESS_GROUP if os.name == "nt" else 0

        self.log("Arrancando Streamlit...")
        self.process = subprocess.Popen(
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
        PID_FILE.parent.mkdir(parents=True, exist_ok=True)
        PID_FILE.write_text(str(self.process.pid), encoding="utf-8")
        self.log(f"Proceso Streamlit iniciado con PID {self.process.pid}.")
        threading.Thread(target=self._pipe_logs, daemon=True).start()

    def stop(self) -> None:
        stopped = False
        if self.process and self.process.poll() is None:
            self.log(f"Apagando Streamlit PID {self.process.pid}...")
            self._terminate_process(self.process)
            stopped = True

        for pid in self._known_pids():
            if self.process and pid == self.process.pid:
                continue
            if self._kill_pid(pid):
                stopped = True

        if PID_FILE.exists():
            PID_FILE.unlink()

        if stopped:
            self.log("Streamlit apagado.")
        elif self.is_running():
            self.log("No se pudo identificar el proceso de Streamlit, pero el puerto sigue respondiendo.")
        else:
            self.log("Streamlit ya estaba apagado.")

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

    def wait_until_running(self, timeout_seconds: float = 15) -> bool:
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            if self.is_running():
                return True
            time.sleep(0.4)
        return False

    def _pipe_logs(self) -> None:
        process = self.process
        if process is None or process.stdout is None:
            return
        for line in process.stdout:
            cleaned = line.rstrip()
            if cleaned:
                self.log(cleaned)
        return_code = process.poll()
        self.log(f"Proceso Streamlit finalizo con codigo {return_code}.")

    def _known_pids(self) -> set[int]:
        pids = set()
        if PID_FILE.exists():
            try:
                pids.add(int(PID_FILE.read_text(encoding="utf-8").strip()))
            except ValueError:
                pass
        pids.update(_pids_listening_on_port(self.port))
        return pids

    @staticmethod
    def _terminate_process(process: subprocess.Popen[str]) -> None:
        if process.poll() is not None:
            return
        try:
            if os.name == "nt":
                process.send_signal(signal.CTRL_BREAK_EVENT)
            else:
                process.terminate()
            process.wait(timeout=5)
        except (subprocess.TimeoutExpired, ProcessLookupError, ValueError):
            process.kill()

    def _kill_pid(self, pid: int) -> bool:
        if pid <= 0:
            return False
        try:
            if os.name == "nt":
                completed = subprocess.run(
                    ["taskkill", "/PID", str(pid), "/T", "/F"],
                    capture_output=True,
                    text=True,
                    encoding="utf-8",
                    errors="replace",
                    check=False,
                )
                if completed.returncode == 0:
                    self.log(f"Proceso PID {pid} terminado.")
                    return True
                return False
            os.kill(pid, signal.SIGTERM)
            self.log(f"Proceso PID {pid} terminado.")
            return True
        except OSError:
            return False


class ControlSistemaApp(App[None]):
    """Terminal UI for controlling Streamlit."""

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
        self.controller = StreamlitController()

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        yield Static(APP_TITLE, id="title")
        yield Static("Estado: revisando...", id="status")
        with Horizontal(id="main"):
            with Vertical(id="buttons"):
                yield Button("Arrancar streamlit", id="start-streamlit", variant="primary")
                yield Button("Abrir navegador", id="open-browser", variant="success")
                yield Button("Apagar", id="stop-streamlit", variant="error")
                yield Button("Cerrar", id="close-tui", variant="default")
            with Vertical(id="log-panel"):
                yield Static("Logs")
                yield RichLog(id="logs", markup=False, highlight=False, wrap=True)
        yield Footer()

    def on_mount(self) -> None:
        self._write_log("TUI lista.")
        self._refresh_status()
        self.set_interval(1.0, self._tick)

    async def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start-streamlit":
            self.controller.start()
            self._write_log("Comando de arranque enviado.")
        elif event.button.id == "open-browser":
            self.controller.open_browser()
            self._write_log("Comando de navegador enviado.")
        elif event.button.id == "stop-streamlit":
            self.controller.stop()
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


def _pids_listening_on_port(port: int) -> set[int]:
    if os.name == "nt":
        return _windows_port_pids(port)
    return _posix_port_pids(port)


def _windows_port_pids(port: int) -> set[int]:
    completed = subprocess.run(
        ["netstat", "-ano", "-p", "tcp"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    pids: set[int] = set()
    needle = f":{port}"
    for line in completed.stdout.splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        local_address, state, pid = parts[1], parts[3], parts[-1]
        if needle in local_address and state.upper() == "LISTENING":
            try:
                pids.add(int(pid))
            except ValueError:
                pass
    return pids


def _posix_port_pids(port: int) -> set[int]:
    completed = subprocess.run(
        ["lsof", "-ti", f":{port}"],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    pids: set[int] = set()
    for line in completed.stdout.splitlines():
        try:
            pids.add(int(line.strip()))
        except ValueError:
            pass
    return pids


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="TUI de control local para Streamlit.")
    parser.add_argument("--smoke-test", action="store_true", help="Validate imports and status checks without opening the TUI.")
    parser.add_argument("--start-stop-test", action="store_true", help="Start Streamlit, validate HTTP status, then stop it.")
    return parser.parse_args(argv)


def run_smoke_test() -> None:
    controller = StreamlitController()
    print("TUI smoke test OK")
    print(f"url={controller.url}")
    print(f"status={'encendido' if controller.is_running() else 'apagado'}")


def run_start_stop_test() -> None:
    controller = StreamlitController()
    was_running = controller.is_running()
    if was_running:
        print("Streamlit ya estaba encendido; se valida estado sin reiniciarlo.")
        print(f"url={controller.url}")
        print("status=encendido")
        return

    controller.start()
    if not controller.wait_until_running(timeout_seconds=25):
        controller.stop()
        raise SystemExit("Streamlit no respondio durante la prueba.")
    print(f"Streamlit respondio en {controller.url}")
    controller.stop()
    if controller.is_running():
        raise SystemExit("Streamlit sigue encendido despues de apagarlo.")
    print("Start/stop test OK")


def main(argv: Iterable[str] | None = None) -> None:
    args = parse_args(argv)
    if args.smoke_test:
        run_smoke_test()
        return
    if args.start_stop_test:
        run_start_stop_test()
        return
    ControlSistemaApp().run()


if __name__ == "__main__":
    main()
