import os
import signal
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import urlopen


REPO_ROOT = Path(__file__).resolve().parents[2]


def _available_loopback_port() -> int:
    for _ in range(20):
        reservation = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            reservation.bind(("127.0.0.1", 0))
            port = int(reservation.getsockname()[1])
        finally:
            reservation.close()
        if port >= 32768:
            return port
    raise RuntimeError("Could not reserve an isolated loopback port for Vite")


def _require_frontend_dependencies() -> None:
    vite_binary = REPO_ROOT / "frontend" / "node_modules" / ".bin" / "vite"
    if not vite_binary.is_file():
        raise RuntimeError("frontend dependencies are missing; run npm --prefix frontend ci explicitly before E2E tests")


class IsolatedViteApp:
    def __init__(self, path: str):
        self.path = path
        self.port = 0
        self.url = ""
        self._process = None
        self._diagnostics = None

    def _startup_diagnostics(self) -> str:
        if self._diagnostics is None:
            return ""
        self._diagnostics.flush()
        self._diagnostics.seek(0)
        output = self._diagnostics.read()
        return output[-1_500:].strip()

    def start(self) -> None:
        _require_frontend_dependencies()
        self.port = _available_loopback_port()
        self.url = f"http://127.0.0.1:{self.port}{self.path}"
        self._diagnostics = tempfile.TemporaryFile(mode="w+t", encoding="utf-8")
        try:
            self._process = subprocess.Popen(
                [
                    "npm", "--prefix", "frontend", "run", "dev", "--",
                    "--host", "127.0.0.1", "--port", str(self.port), "--strictPort",
                ],
                cwd=REPO_ROOT,
                stdout=self._diagnostics,
                stderr=subprocess.STDOUT,
                start_new_session=True,
            )
            deadline = time.monotonic() + 15
            while time.monotonic() < deadline:
                exit_code = self._process.poll()
                if exit_code is not None:
                    detail = self._startup_diagnostics()
                    raise RuntimeError(f"Vite exited before readiness (exit code {exit_code}): {detail}")
                try:
                    response = urlopen(self.url, timeout=0.25)
                    try:
                        ready = response.status == 200
                    finally:
                        response.close()
                    if ready:
                        exit_code = self._process.poll()
                        if exit_code is not None:
                            detail = self._startup_diagnostics()
                            raise RuntimeError(f"Vite exited after readiness response (exit code {exit_code}): {detail}")
                        return
                except OSError:
                    time.sleep(0.1)
            detail = self._startup_diagnostics()
            raise AssertionError(f"Vite did not become ready on its isolated loopback port: {detail}")
        except BaseException:
            self.stop()
            raise

    def stop(self) -> None:
        if self._process is not None and self._process.poll() is None:
            try:
                os.killpg(self._process.pid, signal.SIGTERM)
                self._process.wait(timeout=10)
            except ProcessLookupError:
                self._process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(self._process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                self._process.wait(timeout=10)
        if self._diagnostics is not None:
            self._diagnostics.close()


def guard_browser_requests(page, port: int, api_handler) -> None:
    own_origin = f"127.0.0.1:{port}"

    def handle_request(route):
        target = urlparse(route.request.url)
        is_mock_api = (
            target.scheme == "http"
            and target.path.startswith("/api/")
            and target.netloc in {own_origin, "localhost:8000"}
        )
        if is_mock_api:
            api_handler(route)
            return
        if target.scheme == "http" and target.netloc == own_origin:
            route.continue_()
            return
        route.abort(error_code="blockedbyclient")

    page.route("**/*", handle_request)
