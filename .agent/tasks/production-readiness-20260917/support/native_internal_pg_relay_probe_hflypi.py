#!/usr/bin/env python3
"""DRAFT feasibility proof: relay one owned internal PostgreSQL to loopback.

This is a standalone, manually invoked proof. It never creates networks,
images, containers, volumes, or dependencies. It may start and later stop only
the exact retained tmpfs probe container recorded below; it does not remove it
or its retained internal network.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import platform
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time


NONCE = "hfLYPi"
OWNER = "production-readiness-20260917-hfLYPi"
SCOPE = "native-tc-internal-probe"
CONTAINER_ID = "423858f43fb80952016d98749da9dab11841403b8a76450ce7d6f46f3b2ca318"
CONTAINER_NAME = "localos-readiness-hflypi-tc-postgres-1"
NETWORK_ID = "6fc9dbcb68ce40e46030cec829ed4613840327eda4109cd09de4ada422a4a0b4"
NETWORK_NAME = "localos-readiness-hflypi-tc-internal"
IMAGE_ID = "sha256:4f26f01433671ee540195bff27f4890acca58cb49cf6d61ea12008d842ec0699"
DATABASE = "readiness_tc_hflypi"
USERNAME = "audit_tc"
PASSWORD = "hflypi-tc-local-only"
DOCKER = "/Applications/Docker.app/Contents/Resources/bin/docker"
DOCKER_CONTEXT = "desktop-linux"
DOCKER_HOST = "unix:///Users/alexdemyanov/.docker/run/docker.sock"
DOCKER_CONFIG = "/Users/alexdemyanov/.docker"
MIN_FREE_BYTES = 5 * 1024 * 1024 * 1024
MAX_RUNTIME_SECONDS = 120
READY_TIMEOUT_SECONDS = 60
RELAY_CONNECTION_SECONDS = 20
EXEC_GRACE_SECONDS = 4
STDERR_CAPTURE_BYTES = 2048
LABELS = {
    "localos.audit.owner": OWNER,
    "localos.audit.nonce": NONCE,
    "localos.audit.scope": SCOPE,
}
PROVIDER_ENVIRONMENTS = (
    "ANTHROPIC_API_KEY",
    "APIFY_TOKEN",
    "OPENAI_API_KEY",
    "SMTP_PASSWORD",
    "STRIPE_SECRET_KEY",
    "TELEGRAM_BOT_TOKEN",
)
RESULT_PATH = Path(__file__).resolve().parents[1] / "evidence" / "native-internal-pg-relay-probe-hflypi-v4.json"


def _environment(extra: dict[str, str] | None = None) -> dict[str, str]:
    values = {
        "DOCKER_CONFIG": DOCKER_CONFIG,
        "DOCKER_HOST": DOCKER_HOST,
        "LANG": "C",
        "PATH": "/usr/bin:/bin",
    }
    for key in PROVIDER_ENVIRONMENTS:
        values[key] = ""
    if extra:
        values.update(extra)
    return values


def _docker_command(*arguments: str) -> list[str]:
    return [DOCKER, "--context", DOCKER_CONTEXT, *arguments]


def _redacted(command: list[str]) -> list[str]:
    result: list[str] = []
    for value in command:
        if value == "-c":
            result.extend((value, "<inline-python>"))
            break
        result.append(value)
    return result


def _run(command: list[str], results: dict[str, object], started: float, timeout: int = 20, environment: dict[str, str] | None = None) -> subprocess.CompletedProcess[str]:
    remaining = MAX_RUNTIME_SECONDS - (time.monotonic() - started)
    tearing_down = results.get("tearing_down") is True
    if remaining <= 0 and not tearing_down:
        raise RuntimeError("relay proof runtime budget exhausted")
    command_started = time.monotonic()
    completed = subprocess.run(
        command,
        capture_output=True,
        check=False,
        env=_environment() if environment is None else environment,
        text=True,
        timeout=timeout if tearing_down else min(timeout, max(1, int(remaining))),
    )
    commands = results["commands"]
    if not isinstance(commands, list):
        raise RuntimeError("relay result journal is invalid")
    commands.append({"argv": _redacted(command), "returncode": completed.returncode, "seconds": round(time.monotonic() - command_started, 3)})
    return completed


def _require_success(completed: subprocess.CompletedProcess[str], action: str) -> str:
    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout).strip()[-400:]
        raise RuntimeError(f"{action} failed: {detail}")
    return completed.stdout.strip()


def _inspect(resource: str, name: str, results: dict[str, object], started: float) -> dict[str, object]:
    output = _require_success(_run(_docker_command(resource, "inspect", name), results, started), f"inspect {resource}")
    parsed = json.loads(output)
    if not isinstance(parsed, list) or len(parsed) != 1 or not isinstance(parsed[0], dict):
        raise RuntimeError(f"unexpected {resource} inspect payload")
    return parsed[0]


def _require_labels(labels: object) -> None:
    if not isinstance(labels, dict) or any(labels.get(key) != value for key, value in LABELS.items()):
        raise RuntimeError("resource labels do not prove hfLYPi ownership")


def _verify_context(results: dict[str, object], started: float) -> None:
    output = _require_success(_run(_docker_command("context", "inspect", DOCKER_CONTEXT), results, started), "inspect Docker context")
    parsed = json.loads(output)
    if not isinstance(parsed, list) or len(parsed) != 1 or not isinstance(parsed[0], dict):
        raise RuntimeError("Docker context inspect payload is invalid")
    endpoints = parsed[0].get("Endpoints", {})
    docker_endpoint = endpoints.get("docker", {}) if isinstance(endpoints, dict) else {}
    host = docker_endpoint.get("Host") if isinstance(docker_endpoint, dict) else None
    if host != DOCKER_HOST:
        raise RuntimeError("Docker context endpoint is not the reviewed local Unix socket")
    results["docker_context_endpoint"] = host


def _verify_identity(results: dict[str, object], started: float, require_running: bool | None) -> bool:
    container = _inspect("container", CONTAINER_ID, results, started)
    config = container.get("Config", {})
    state = container.get("State", {})
    network_settings = container.get("NetworkSettings", {})
    host_config = container.get("HostConfig", {})
    if not isinstance(config, dict) or not isinstance(state, dict) or not isinstance(network_settings, dict) or not isinstance(host_config, dict):
        raise RuntimeError("container inspect structure is invalid")
    _require_labels(config.get("Labels"))
    if container.get("Id") != CONTAINER_ID or container.get("Name") != f"/{CONTAINER_NAME}" or container.get("Image") != IMAGE_ID:
        raise RuntimeError("container does not match the retained exact probe identity")
    networks = network_settings.get("Networks", {})
    running = state.get("Running")
    if not isinstance(running, bool):
        raise RuntimeError("container running state is invalid")
    if require_running is not None and running is not require_running:
        raise RuntimeError("container running state differs from relay proof stage")
    if host_config.get("Privileged") is True or host_config.get("Binds"):
        raise RuntimeError("container has privileged mode or bind mounts")
    tmpfs = host_config.get("Tmpfs", {})
    if not isinstance(tmpfs, dict) or set(tmpfs) != {"/var/lib/postgresql/data"}:
        raise RuntimeError("container does not retain the exact PGDATA tmpfs")
    mounts = container.get("Mounts", [])
    if mounts not in (None, []):
        raise RuntimeError("container has unexpected persistent mounts")
    ports = network_settings.get("Ports", {})
    if running:
        if not isinstance(networks, dict) or set(networks) != {NETWORK_NAME}:
            raise RuntimeError("running container is not attached only to the retained internal network")
        if not isinstance(ports, dict) or ports.get("5432/tcp") != []:
            raise RuntimeError("running internal probe must retain an unpublished PostgreSQL port")
    elif (not isinstance(networks, dict) or set(networks) not in (set(), {NETWORK_NAME})) or (not isinstance(ports, dict) or set(ports) not in (set(), {"5432/tcp"})):
        raise RuntimeError("stopped container network state is not an expected empty retained state")
    network = _inspect("network", NETWORK_ID, results, started)
    _require_labels(network.get("Labels"))
    endpoints = network.get("Containers", {})
    if network.get("Id") != NETWORK_ID or network.get("Name") != NETWORK_NAME or network.get("Driver") != "bridge" or network.get("Internal") is not True:
        raise RuntimeError("network does not match the retained exact internal bridge")
    if not isinstance(endpoints, dict):
        raise RuntimeError("internal bridge endpoint inventory is invalid")
    expected_endpoints = {CONTAINER_ID} if running else set()
    if set(endpoints) != expected_endpoints:
        raise RuntimeError("internal bridge has an unexpected endpoint")
    results["identity"] = {
        "container_id": container.get("Id"),
        "container_name": container.get("Name"),
        "container_running": running,
        "image": container.get("Image"),
        "labels": config.get("Labels"),
        "networks": sorted(networks),
        "ports": ports,
        "mounts": mounts,
        "privileged": host_config.get("Privileged"),
        "tmpfs": tmpfs,
        "network_id": network.get("Id"),
        "network_name": network.get("Name"),
        "network_internal": network.get("Internal"),
        "network_endpoint_ids": sorted(endpoints),
    }
    return running


class Relay:
    """One loopback listener and exactly one Docker-exec byte pipe."""

    def __init__(self, results: dict[str, object], started: float) -> None:
        self.results = results
        self.started = started
        self.listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.listener.settimeout(0.2)
        self.port = int(self.listener.getsockname()[1])
        self.stopping = threading.Event()
        self.accept_thread = threading.Thread(target=self._accept_loop, name="hflypi-relay-accept", daemon=True)
        self.worker: threading.Thread | None = None
        self.bridge: tuple[socket.socket, subprocess.Popen[bytes], threading.Thread, threading.Thread] | None = None
        self.connection_count = 0
        self.exec_argv: list[str] | None = None
        self.exec_returncode: int | None = None
        self.exec_exit_mode: str | None = None
        self.exec_stderr_file = None
        self.exec_stderr_path: Path | None = None
        self.exec_stderr_tail = ""
        self.exec_stderr_bytes = 0
        self.stage_seconds: dict[str, float] = {}
        self.lock = threading.Lock()

    def mark(self, stage: str) -> None:
        if stage not in self.stage_seconds:
            self.stage_seconds[stage] = round(time.monotonic() - self.started, 6)

    def start(self) -> None:
        self.accept_thread.start()
        self.results["relay"] = {"host": "127.0.0.1", "port": self.port, "connection_limit": 1}

    def _accept_loop(self) -> None:
        while not self.stopping.is_set():
            try:
                client, _ = self.listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            client.settimeout(RELAY_CONNECTION_SECONDS)
            worker = threading.Thread(target=self._serve, args=(client,), name="hflypi-relay-client", daemon=True)
            with self.lock:
                if self.stopping.is_set() or self.connection_count != 0:
                    client.close()
                    return
                self.connection_count = 1
                self.mark("accepted_client")
                self.worker = worker
            try:
                self.listener.close()
            except OSError:
                pass
            worker.start()
            return

    def _serve(self, client: socket.socket) -> None:
        upstream = "exec 3<>/dev/tcp/127.0.0.1/5432; exec 4<&0; writer=; reader=; cleanup(){ [ -n \"$writer\" ] && kill \"$writer\" 2>/dev/null || true; [ -n \"$reader\" ] && kill \"$reader\" 2>/dev/null || true; wait \"$writer\" 2>/dev/null || true; wait \"$reader\" 2>/dev/null || true; }; trap cleanup EXIT INT TERM; cat <&4 >&3 & writer=$!; cat <&3 & reader=$!; wait -n \"$writer\" \"$reader\" || true"
        command = _docker_command("exec", "-i", CONTAINER_ID, "/bin/bash", "-lc", upstream)
        process: subprocess.Popen[bytes] | None = None
        try:
            if self.stopping.is_set():
                client.close()
                return
            descriptor, stderr_name = tempfile.mkstemp(prefix="native-relay-stderr-v4-", suffix=".log", dir=RESULT_PATH.parent)
            self.exec_stderr_file = os.fdopen(descriptor, "wb")
            self.exec_stderr_path = Path(stderr_name)
            process = subprocess.Popen(
                command,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=self.exec_stderr_file,
                env=_environment(),
            )
            self.mark("exec_client_spawned")
            with self.lock:
                self.exec_argv = command
            if process.stdin is None or process.stdout is None:
                client.close()
                process.terminate()
                try:
                    process.wait(timeout=3)
                    self.exec_exit_mode = "terminated_without_pipe"
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=2)
                    self.exec_exit_mode = "killed_without_pipe"
                self.exec_returncode = process.poll()
                self._collect_stderr()
                self.mark("exec_client_exited")
                return
            to_upstream = threading.Thread(target=self._copy_to_upstream, args=(client, process.stdin), name="hflypi-relay-in", daemon=True)
            from_upstream = threading.Thread(target=self._copy_to_client, args=(process.stdout, client), name="hflypi-relay-out", daemon=True)
            with self.lock:
                self.bridge = (client, process, to_upstream, from_upstream)
            to_upstream.start()
            from_upstream.start()
            if self.stopping.is_set():
                bridge = self._take_bridge()
                if bridge is not None:
                    self._close_bridge(*bridge)
                return
            to_upstream.join(RELAY_CONNECTION_SECONDS)
            from_upstream.join(RELAY_CONNECTION_SECONDS)
            bridge = self._take_bridge()
            if bridge is not None:
                self._close_bridge(*bridge)
        finally:
            with self.lock:
                if process is not None:
                    self.exec_returncode = process.poll()

    def _take_bridge(self) -> tuple[socket.socket, subprocess.Popen[bytes], threading.Thread, threading.Thread] | None:
        with self.lock:
            bridge = self.bridge
            self.bridge = None
            return bridge

    def _copy_to_upstream(self, client: socket.socket, stream) -> None:
        try:
            while not self.stopping.is_set():
                payload = client.recv(65536)
                if not payload:
                    break
                self.mark("first_client_bytes")
                stream.write(payload)
                stream.flush()
        except (OSError, BrokenPipeError):
            pass
        finally:
            try:
                stream.close()
            except OSError:
                pass

    def _copy_to_client(self, stream, client: socket.socket) -> None:
        try:
            while not self.stopping.is_set():
                payload = os.read(stream.fileno(), 65536)
                if not payload:
                    break
                self.mark("first_upstream_bytes")
                client.sendall(payload)
        except OSError:
            pass
        finally:
            try:
                client.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    def _collect_stderr(self) -> None:
        stderr_file = self.exec_stderr_file
        stderr_path = self.exec_stderr_path
        self.exec_stderr_file = None
        self.exec_stderr_path = None
        if stderr_file is not None:
            stderr_file.close()
        if stderr_path is None:
            return
        try:
            payload = stderr_path.read_bytes()
            self.exec_stderr_bytes = len(payload)
            self.exec_stderr_tail = payload[-STDERR_CAPTURE_BYTES:].decode(errors="replace")
        finally:
            stderr_path.unlink(missing_ok=True)

    def _close_bridge(self, client: socket.socket, process: subprocess.Popen[bytes], incoming: threading.Thread, outgoing: threading.Thread) -> None:
        try:
            client.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        client.close()
        try:
            incoming.join(EXEC_GRACE_SECONDS)
            if incoming.is_alive():
                self.exec_exit_mode = "terminated_after_input_close_timeout"
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    self.exec_exit_mode = "killed_after_input_close_timeout"
                    process.kill()
                    process.wait(timeout=2)
            elif process.poll() is None:
                try:
                    process.wait(timeout=EXEC_GRACE_SECONDS)
                    self.exec_exit_mode = "graceful"
                except subprocess.TimeoutExpired:
                    self.exec_exit_mode = "terminated_after_grace"
                    process.terminate()
                    try:
                        process.wait(timeout=3)
                    except subprocess.TimeoutExpired:
                        self.exec_exit_mode = "killed_after_terminate"
                        process.kill()
                        process.wait(timeout=2)
            else:
                self.exec_exit_mode = "graceful"
        finally:
            outgoing.join(EXEC_GRACE_SECONDS)
            self.exec_returncode = process.poll()
            self._collect_stderr()
            self.mark("exec_client_exited")

    def close(self) -> None:
        self.stopping.set()
        try:
            self.listener.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        self.listener.close()
        self.accept_thread.join(2)
        with self.lock:
            worker = self.worker
        bridge = self._take_bridge()
        if bridge is not None:
            self._close_bridge(*bridge)
        if worker is not None:
            worker.join(RELAY_CONNECTION_SECONDS + 5)
            if worker.is_alive():
                raise RuntimeError("relay worker did not stop within its bounded teardown")
        bridge = self._take_bridge()
        if bridge is not None:
            self._close_bridge(*bridge)
        if self.exec_stderr_file is not None:
            self._collect_stderr()
        if self.exec_argv is not None:
            self.results["relay_exec"] = {
                "argv": self.exec_argv,
                "returncode": self.exec_returncode,
                "exit_mode": self.exec_exit_mode,
                "stderr_bytes": self.exec_stderr_bytes,
                "stderr_tail": self.exec_stderr_tail,
            }
        self.results["relay_connection_count"] = self.connection_count
        self.results["relay_stage_seconds"] = self.stage_seconds
        select = self.results.get("select")
        if isinstance(select, dict) and select.get("verified") is True and (self.exec_returncode != 0 or self.exec_exit_mode != "graceful"):
            raise RuntimeError("relay Docker exec did not end with a clean successful exit")


def _wait_ready(results: dict[str, object], started: float) -> None:
    deadline = min(started + MAX_RUNTIME_SECONDS, time.monotonic() + READY_TIMEOUT_SECONDS)
    while time.monotonic() < deadline:
        completed = _run(_docker_command("exec", CONTAINER_ID, "pg_isready", "-U", USERNAME, "-d", DATABASE), results, started, timeout=5)
        if completed.returncode == 0:
            return
        time.sleep(1)
    raise RuntimeError("owned internal PostgreSQL did not become ready")


def _native_select(port: int, results: dict[str, object], started: float) -> None:
    dsn = f"postgresql://{USERNAME}:{PASSWORD}@127.0.0.1:{port}/{DATABASE}"
    source = """
import os
import platform
if platform.machine() != 'arm64':
    raise RuntimeError('native relay child must be ARM64')
import psycopg2
dsn = os.environ[\"LOCALOS_HFLYPI_RELAY_DSN\"]
connection = psycopg2.connect(dsn, connect_timeout=15)
try:
    connection.set_session(readonly=True, autocommit=True)
    cursor = connection.cursor()
    try:
        cursor.execute(\"SELECT current_database(), current_user, 1\")
        observed = cursor.fetchone()
    finally:
        cursor.close()
finally:
    connection.close()
if observed != (\"readiness_tc_hflypi\", \"audit_tc\", 1):
    raise RuntimeError(\"unexpected read-only identity result\")
"""
    environment = _environment({"LOCALOS_HFLYPI_RELAY_DSN": dsn})
    _require_success(_run([sys.executable, "-I", "-B", "-c", source], results, started, timeout=25, environment=environment), "native relay psycopg SELECT")
    results["select"] = {"readonly": True, "query": "identity-and-select-1", "verified": True}


def _stop_owned(results: dict[str, object], started: float) -> None:
    running = _verify_identity(results, started, require_running=None)
    if running:
        stopped = _run(_docker_command("container", "stop", "--timeout", "5", CONTAINER_ID), results, started, timeout=10)
        _require_success(stopped, "stop owned probe container")
    _verify_identity(results, started, require_running=False)
    results["teardown"] = {"container_stopped": True, "network_retained": NETWORK_ID}


def main() -> int:
    started = time.monotonic()
    results: dict[str, object] = {
        "kind": "native_internal_pg_relay_feasibility_probe",
        "nonce": NONCE,
        "status": "running",
        "commands": [],
        "limits": {"max_runtime_seconds": MAX_RUNTIME_SECONDS, "relay_connection_seconds": RELAY_CONNECTION_SECONDS},
    }
    relay: Relay | None = None
    start_attempted = False
    exit_code = 1
    try:
        if RESULT_PATH.exists():
            raise RuntimeError(f"refusing to overwrite prior relay artifact: {RESULT_PATH}")
        if platform.machine() != "arm64":
            raise RuntimeError("relay probe requires /usr/bin/arch -arm64 Python")
        results["parent_machine"] = platform.machine()
        free = shutil.disk_usage(Path.cwd()).free
        results["free_bytes"] = free
        if free < MIN_FREE_BYTES:
            raise RuntimeError("at least 5 GiB free disk is required")
        if not Path(DOCKER).is_file():
            raise RuntimeError("reviewed Docker CLI path is unavailable")
        _verify_context(results, started)
        _verify_identity(results, started, require_running=False)
        start_attempted = True
        _require_success(_run(_docker_command("container", "start", CONTAINER_ID), results, started), "start owned tmpfs probe PostgreSQL")
        results["start"] = {"container_started": True}
        _verify_identity(results, started, require_running=True)
        _wait_ready(results, started)
        relay = Relay(results, started)
        relay.start()
        _native_select(relay.port, results, started)
        results["status"] = "passed"
        exit_code = 0
    except BaseException:
        error = sys.exception()
        results["status"] = "failed"
        results["error"] = f"{type(error).__name__}: {error}"
    finally:
        if relay is not None:
            try:
                relay.close()
                results["relay_teardown"] = {"listener_closed": True}
            except BaseException:
                error = sys.exception()
                results["relay_teardown_error"] = f"{type(error).__name__}: {error}"
                results["status"] = "failed"
                exit_code = 1
        if start_attempted:
            try:
                results["tearing_down"] = True
                _stop_owned(results, started)
            except BaseException:
                error = sys.exception()
                results["teardown_error"] = f"{type(error).__name__}: {error}"
                results["status"] = "failed"
                exit_code = 1
        results["elapsed_seconds"] = round(time.monotonic() - started, 3)
        rendered = json.dumps(results, sort_keys=True)
        if not RESULT_PATH.exists():
            artifact = RESULT_PATH.open("x", encoding="utf-8")
            try:
                artifact.write(rendered + "\n")
            finally:
                artifact.close()
        print(rendered)
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
