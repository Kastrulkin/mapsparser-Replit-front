#!/usr/bin/env python3
"""Private, bounded Docker-exec relay for the hfLYPi native Testcontainers lane."""

from __future__ import annotations

import json
import os
from pathlib import Path
import re
import socket
import stat
import subprocess
import tempfile
import threading
import time
import sys


NONCE = "hfLYPi"
OWNER = "production-readiness-20260917-hfLYPi"
CONTAINER_SCOPE = "native-tc-integration"
NETWORK_SCOPE = "native-tc-internal-probe"
NETWORK_ID = "6fc9dbcb68ce40e46030cec829ed4613840327eda4109cd09de4ada422a4a0b4"
NETWORK_NAME = "localos-readiness-hflypi-tc-internal"
IMAGE_ID = "sha256:4f26f01433671ee540195bff27f4890acca58cb49cf6d61ea12008d842ec0699"
DOCKER = "/Applications/Docker.app/Contents/Resources/bin/docker"
DOCKER_HOST = "unix:///Users/alexdemyanov/.docker/run/docker.sock"
DOCKER_CONFIG = "/Users/alexdemyanov/.docker"
NATIVE = Path("/private/tmp/localos-readiness-20260921.hfLYPi/native")
CAPABILITY_DIR = NATIVE / "capabilities"
SERVER_SECONDS = 600
CONNECTION_SECONDS = 120
EXEC_GRACE_SECONDS = 4
MAX_CONNECTIONS = 32
MAX_CONCURRENT = 8
STDERR_BYTES = 2048
PROFILE_CONNECTION_BUDGETS = {
    "card-growth-v1": 32,
    "client-info-v1": 32,
    "capabilities-phase1-v1": 1024,
    "operator-service-creation-v1": 32,
    "operator-voice-pg-v1": 512,
    "operator-editorial-pg-v1": 128,
    "work-review-rollback-v1": 512,
    "creator-portal-rollback-v1": 512,
    "creator-offer-rollback-v1": 512,
    "author-daily-gate-pg-v1": 32,
    "knowledge-schema-pg-v1": 32,
    "outreach-pain-library-pg-v1": 32,
    "riderra-template-pg-v1": 32,
    "sales-room-proposal-race-pg-v1": 32,
    "sales-room-deadlock-pg-v1": 32,
    "telegram-shared-audience-pg-v1": 32,
    "web-tracking-pg-v1": 32,
    "worker-captcha-pg-v1": 32,
    "worker-expired-pg-v1": 32,
    "worker-resume-pg-v1": 32,
    "finance-import-transaction-pg-v1": 32,
    "service-compression-race-pg-v1": 512,
}
SESSION_PATTERN = re.compile(r"[A-Za-z0-9_-]{8,128}")
CAPABILITY_KEYS = {
    "version",
    "nonce",
    "parent_pid",
    "expires_at",
    "container_id",
    "session_id",
    "host",
    "port",
    "network_id",
    "network_name",
    "image_id",
}
PROVIDER_ENVIRONMENTS = (
    "ANTHROPIC_API_KEY",
    "APIFY_TOKEN",
    "OPENAI_API_KEY",
    "SMTP_PASSWORD",
    "STRIPE_SECRET_KEY",
    "TELEGRAM_BOT_TOKEN",
)


def _write_all(descriptor: int, payload: bytes) -> None:
    view = memoryview(payload)
    while view:
        written = os.write(descriptor, view)
        if written <= 0:
            raise RuntimeError("private artifact write failed")
        view = view[written:]


def _docker_environment() -> dict[str, str]:
    values = {
        "DOCKER_CONFIG": DOCKER_CONFIG,
        "DOCKER_HOST": DOCKER_HOST,
        "LANG": "C",
        "PATH": "/usr/bin:/bin",
    }
    for key in PROVIDER_ENVIRONMENTS:
        values[key] = ""
    return values


def _session(session_id: str) -> None:
    if SESSION_PATTERN.fullmatch(session_id) is None:
        raise PermissionError("invalid Testcontainers session identifier")


def connection_budget(profile: str) -> int:
    """Return the literal lifetime cap for one reviewed Testcontainers profile."""
    if profile == "":
        return MAX_CONNECTIONS
    budget = PROFILE_CONNECTION_BUDGETS.get(profile)
    if not isinstance(budget, int):
        raise PermissionError("unsupported relay profile")
    return budget


def _tmpfs_is_safe(value: object) -> bool:
    if not isinstance(value, str):
        return False
    tokens = set(value.split(","))
    if not {"rw", "noexec", "nosuid"}.issubset(tokens):
        return False
    sizes = [token for token in tokens if token.startswith("size=")]
    if len(sizes) != 1:
        return False
    match = re.fullmatch(r"size=(\d+)([kKmMgG])", sizes[0])
    if match is None:
        return False
    multiplier = {"k": 1024, "m": 1024**2, "g": 1024**3}[match.group(2).lower()]
    return int(match.group(1)) * multiplier <= 512 * 1024**2


def _sdk_client():
    import docker

    return docker.DockerClient(base_url=DOCKER_HOST, version="auto", timeout=10)


def verify_container(container_id: str, session_id: str, require_running: bool = True) -> dict[str, object]:
    """Read and pin the one permitted Testcontainers PostgreSQL container."""

    _session(session_id)
    client = _sdk_client()
    try:
        try:
            container = client.api.inspect_container(container_id)
            network = client.api.inspect_network(NETWORK_ID)
        except Exception:
            raise PermissionError("Docker does not authorize the relay container")
    finally:
        client.close()
    config = container.get("Config", {})
    state = container.get("State", {})
    host_config = container.get("HostConfig", {})
    network_settings = container.get("NetworkSettings", {})
    if not isinstance(config, dict) or not isinstance(state, dict) or not isinstance(host_config, dict) or not isinstance(network_settings, dict):
        raise PermissionError("Docker inspection shape is unsafe")
    labels = config.get("Labels", {})
    expected_labels = {
        "localos.audit.owner": OWNER,
        "localos.audit.nonce": NONCE,
        "localos.audit.scope": CONTAINER_SCOPE,
        "org.testcontainers": "true",
        "org.testcontainers.session-id": session_id,
    }
    if not isinstance(labels, dict) or any(labels.get(key) != value for key, value in expected_labels.items()):
        raise PermissionError("container labels do not grant relay access")
    if container.get("Id") != container_id or container.get("Image") != IMAGE_ID:
        raise PermissionError("container identity differs from approved image")
    running = state.get("Running")
    if not isinstance(running, bool) or require_running and not running:
        raise PermissionError("container is not running")
    if host_config.get("Privileged") is True or host_config.get("Binds"):
        raise PermissionError("container privilege or bind mounts are unsafe")
    tmpfs = host_config.get("Tmpfs", {})
    if not isinstance(tmpfs, dict) or set(tmpfs) != {"/var/lib/postgresql/data"} or not _tmpfs_is_safe(tmpfs["/var/lib/postgresql/data"]):
        raise PermissionError("container PGDATA tmpfs is unsafe")
    mounts = container.get("Mounts", [])
    if mounts not in (None, []):
        raise PermissionError("container has persistent mounts")
    networks = network_settings.get("Networks", {})
    ports = network_settings.get("Ports", {})
    port_bindings = host_config.get("PortBindings", {})
    if running:
        if not isinstance(networks, dict) or set(networks) != {NETWORK_NAME}:
            raise PermissionError("container is not internal-network-only")
        if not isinstance(ports, dict) or ports not in ({}, {"5432/tcp": None}, {"5432/tcp": []}):
            raise PermissionError("container PostgreSQL port is published")
        if not isinstance(port_bindings, dict) or port_bindings or host_config.get("PublishAllPorts") is True:
            raise PermissionError("container PostgreSQL host bindings are unsafe")
    elif not isinstance(networks, dict) or set(networks) not in (set(), {NETWORK_NAME}):
        raise PermissionError("stopped container network state is unsafe")
    if not isinstance(network, dict) or network.get("Id") != NETWORK_ID or network.get("Name") != NETWORK_NAME or network.get("Driver") != "bridge" or network.get("Internal") is not True:
        raise PermissionError("relay network is not the approved internal bridge")
    network_labels = network.get("Labels", {})
    if not isinstance(network_labels, dict) or network_labels.get("localos.audit.owner") != OWNER or network_labels.get("localos.audit.nonce") != NONCE or network_labels.get("localos.audit.scope") != NETWORK_SCOPE:
        raise PermissionError("relay network labels are unsafe")
    endpoints = network.get("Containers", {})
    if not isinstance(endpoints, dict):
        raise PermissionError("relay network endpoint list is unsafe")
    if running and set(endpoints) != {container_id}:
        raise PermissionError("relay network endpoint set is unsafe")
    if not running and set(endpoints) not in (set(), {container_id}):
        raise PermissionError("stopped relay endpoint set is unsafe")
    return {
        "container_id": container_id,
        "session_id": session_id,
        "running": running,
        "network_id": NETWORK_ID,
        "network_name": NETWORK_NAME,
        "image_id": IMAGE_ID,
    }


def _capability_directory() -> None:
    CAPABILITY_DIR.mkdir(mode=0o700, parents=True, exist_ok=True)
    metadata = CAPABILITY_DIR.lstat()
    if not CAPABILITY_DIR.is_dir() or CAPABILITY_DIR.is_symlink() or CAPABILITY_DIR.resolve(strict=True) != CAPABILITY_DIR or stat.S_IMODE(metadata.st_mode) != 0o700 or metadata.st_uid != os.getuid():
        raise PermissionError("capability directory is not canonical")


def _parent_is_live(parent_pid: int) -> bool:
    try:
        os.kill(parent_pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return False
    return True


def _capability_name(session_id: str, container_id: str, parent_pid: int) -> str:
    return f"native-tc-relay-{session_id}-{container_id}-{parent_pid}.json"


def _owner_pid() -> int:
    raw = os.environ.get("LOCALOS_HFLYPI_TC_OWNER_PID")
    if raw is None or not raw.isdecimal():
        raise PermissionError("relay owner PID is unavailable")
    return int(raw)


def validate_capability(path: Path, port: int) -> dict[str, object]:
    """Authorize a parent or Flask child only from one live private capability."""

    _capability_directory()
    if not isinstance(port, int) or port < 1 or port > 65535:
        raise PermissionError("relay port is invalid")
    try:
        canonical = path.resolve(strict=True)
    except OSError:
        raise PermissionError("capability path cannot be resolved")
    if path.parent != CAPABILITY_DIR or path.is_symlink() or canonical != path:
        raise PermissionError("capability path is not canonical")
    metadata = path.lstat()
    if not stat.S_ISREG(metadata.st_mode) or stat.S_IMODE(metadata.st_mode) != 0o600 or metadata.st_uid != os.getuid() or metadata.st_size > 4096:
        raise PermissionError("capability mode is unsafe")
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise PermissionError("capability cannot be read")
    if not isinstance(payload, dict) or set(payload) != CAPABILITY_KEYS:
        raise PermissionError("capability schema is unsafe")
    if payload.get("version") != 1 or payload.get("nonce") != NONCE or payload.get("host") != "127.0.0.1" or payload.get("network_id") != NETWORK_ID or payload.get("network_name") != NETWORK_NAME or payload.get("image_id") != IMAGE_ID:
        raise PermissionError("capability identity is unsafe")
    parent_pid = payload.get("parent_pid")
    expires_at = payload.get("expires_at")
    container_id = payload.get("container_id")
    session_id = payload.get("session_id")
    if not isinstance(parent_pid, int) or parent_pid != _owner_pid() or not _parent_is_live(parent_pid) or not isinstance(expires_at, (int, float)) or time.time() >= expires_at:
        raise PermissionError("capability parent or expiry is invalid")
    if payload.get("port") != port or not isinstance(container_id, str) or not isinstance(session_id, str):
        raise PermissionError("capability relay target is invalid")
    if path.name != _capability_name(session_id, container_id, parent_pid):
        raise PermissionError("capability filename binding is unsafe")
    return {**verify_container(container_id, session_id), "host": "127.0.0.1", "port": port, "expires_at": expires_at}


def _write_private_capability(path: Path, payload: dict[str, object], mode: int = 0o600) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, mode)
    try:
        _write_all(descriptor, json.dumps(payload, sort_keys=True).encode())
    finally:
        os.close(descriptor)


def negative_capability_checks(path: Path, port: int) -> list[dict[str, object]]:
    """Exercise local denials with isolated copies; never connect a PG client."""

    _capability_directory()
    try:
        original = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        raise PermissionError("cannot prepare capability denials")
    if not isinstance(original, dict) or set(original) != CAPABILITY_KEYS:
        raise PermissionError("cannot prepare capability denials")
    parent_pid = original.get("parent_pid")
    container_id = original.get("container_id")
    session_id = original.get("session_id")
    if not isinstance(parent_pid, int) or not isinstance(container_id, str) or not isinstance(session_id, str):
        raise PermissionError("cannot prepare capability denials")
    results: list[dict[str, object]] = []

    validate_capability(path, port)

    def denied(case: str, expected_reason: str, candidate: Path, candidate_port: int) -> None:
        try:
            validate_capability(candidate, candidate_port)
        except PermissionError:
            error = sys.exception()
            if not isinstance(error, PermissionError) or str(error) != expected_reason:
                raise RuntimeError(f"negative capability reason mismatch: {case}")
            results.append({"case": case, "denied": True, "reason": str(error)})
            return
        raise RuntimeError(f"negative capability case accepted: {case}")

    cases: list[tuple[str, str, dict[str, object], Path, int, int, bool]] = []
    stale = dict(original)
    stale["expires_at"] = 0
    cases.append(("stale_expiry", "capability parent or expiry is invalid", stale, CAPABILITY_DIR / _capability_name(session_id, container_id, parent_pid), port, 0o600, False))
    bad_nonce = dict(original)
    bad_nonce["nonce"] = "wrong"
    cases.append(("nonce", "capability identity is unsafe", bad_nonce, CAPABILITY_DIR / _capability_name(session_id, container_id, parent_pid), port, 0o600, False))
    bad_session = dict(original)
    bad_session["session_id"] = f"{session_id}x"
    cases.append(("session", "container labels do not grant relay access", bad_session, CAPABILITY_DIR / _capability_name(bad_session["session_id"], container_id, parent_pid), port, 0o600, True))
    bad_container = dict(original)
    bad_container["container_id"] = f"{'1' if container_id.startswith('0') else '0'}{container_id[1:]}"
    cases.append(("container", "Docker does not authorize the relay container", bad_container, CAPABILITY_DIR / _capability_name(session_id, bad_container["container_id"], parent_pid), port, 0o600, True))
    cases.append(("wrong_port", "capability relay target is invalid", dict(original), CAPABILITY_DIR / _capability_name(session_id, container_id, parent_pid), port + 1 if port < 65535 else port - 1, 0o600, False))
    cases.append(("world_readable", "capability mode is unsafe", dict(original), CAPABILITY_DIR / _capability_name(session_id, container_id, parent_pid), port, 0o644, False))
    for index, (case, expected_reason, payload, expected_path, candidate_port, mode, canonical_name) in enumerate(cases):
        candidate = expected_path if canonical_name else expected_path.with_name(f".{expected_path.name}.negative-{os.getpid()}-{index}")
        _write_private_capability(candidate, payload, mode)
        if case == "world_readable":
            os.chmod(candidate, 0o644)
        try:
            denied(case, expected_reason, candidate, candidate_port)
        finally:
            candidate.unlink(missing_ok=True)
    foreign = NATIVE / f"native-tc-relay-negative-{os.getpid()}.json"
    _write_private_capability(foreign, dict(original))
    try:
        denied("foreign_path", "capability path is not canonical", foreign, port)
    finally:
        foreign.unlink(missing_ok=True)
    target = CAPABILITY_DIR / f".native-tc-relay-negative-target-{os.getpid()}.json"
    link = CAPABILITY_DIR / f".native-tc-relay-negative-link-{os.getpid()}.json"
    _write_private_capability(target, dict(original))
    try:
        link.symlink_to(target.name)
        denied("symlink", "capability path is not canonical", link, port)
    finally:
        link.unlink(missing_ok=True)
        target.unlink(missing_ok=True)
    return results


class Relay:
    """Bounded multi-connection loopback relay for a verified owned container."""

    def __init__(self, container_id: str, session_id: str, journal_path: Path, profile: str = "") -> None:
        _session(session_id)
        self.container_id = container_id
        self.session_id = session_id
        self.journal_path = journal_path
        self.started_at = time.monotonic()
        self.expires_at = time.time() + SERVER_SECONDS
        self.connection_budget = connection_budget(profile)
        self.stopping = threading.Event()
        self.lock = threading.Lock()
        self.semaphore = threading.BoundedSemaphore(MAX_CONCURRENT)
        self.listener: socket.socket | None = None
        self.accept_thread: threading.Thread | None = None
        self.workers: set[threading.Thread] = set()
        self.bridges: dict[int, dict[str, object]] = {}
        self.total_connections = 0
        self.rejections = 0
        self.failures: list[str] = []
        self.exec_results: list[dict[str, object]] = []
        self.closed = False
        self._capability_path: Path | None = None
        self._port: int | None = None

    @property
    def capability_path(self) -> Path:
        if self._capability_path is None:
            raise RuntimeError("relay capability is not available before start")
        return self._capability_path

    @property
    def port(self) -> int:
        if self._port is None:
            raise RuntimeError("relay port is not available before start")
        return self._port

    def _record_failure(self, detail: str) -> None:
        with self.lock:
            self.failures.append(detail[-500:])

    def _open_capability(self, port: int) -> None:
        _capability_directory()
        path = CAPABILITY_DIR / _capability_name(self.session_id, self.container_id, os.getpid())
        payload = {
            "version": 1,
            "nonce": NONCE,
            "parent_pid": os.getpid(),
            "expires_at": self.expires_at,
            "container_id": self.container_id,
            "session_id": self.session_id,
            "host": "127.0.0.1",
            "port": port,
            "network_id": NETWORK_ID,
            "network_name": NETWORK_NAME,
            "image_id": IMAGE_ID,
        }
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        try:
            _write_all(descriptor, json.dumps(payload, sort_keys=True).encode())
        finally:
            os.close(descriptor)
        if stat.S_IMODE(path.lstat().st_mode) != 0o600:
            path.unlink(missing_ok=True)
            raise PermissionError("capability file mode changed")
        self._capability_path = path

    def start(self) -> int:
        if self.listener is not None or self.closed:
            raise RuntimeError("relay cannot be started twice")
        verify_container(self.container_id, self.session_id)
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 0)
        listener.bind(("127.0.0.1", 0))
        listener.listen(MAX_CONCURRENT)
        listener.settimeout(0.2)
        self.listener = listener
        port = int(listener.getsockname()[1])
        try:
            self._open_capability(port)
        except BaseException:
            listener.close()
            self.listener = None
            raise
        self._port = port
        self.accept_thread = threading.Thread(target=self._accept, name="hflypi-tc-relay-accept", daemon=True)
        self.accept_thread.start()
        return port

    def _accept(self) -> None:
        listener = self.listener
        if listener is None:
            return
        while not self.stopping.is_set() and time.time() < self.expires_at:
            try:
                client, _ = listener.accept()
            except TimeoutError:
                continue
            except OSError:
                return
            with self.lock:
                full = self.total_connections >= self.connection_budget
            if full or not self.semaphore.acquire(blocking=False):
                self.rejections += 1
                client.close()
                continue
            with self.lock:
                self.total_connections += 1
            client.settimeout(CONNECTION_SECONDS)
            worker = threading.Thread(target=self._serve, args=(client,), name="hflypi-tc-relay-client", daemon=True)
            with self.lock:
                self.workers.add(worker)
            worker.start()
        self.stopping.set()

    def _new_stderr(self) -> tuple[object, Path]:
        descriptor, name = tempfile.mkstemp(prefix="native-tc-relay-", suffix=".stderr", dir=CAPABILITY_DIR)
        return os.fdopen(descriptor, "wb"), Path(name)

    def _serve(self, client: socket.socket) -> None:
        process: subprocess.Popen[bytes] | None = None
        stderr_file = None
        stderr_path: Path | None = None
        bridge: dict[str, object] | None = None
        try:
            if self.stopping.is_set() or time.time() >= self.expires_at:
                return
            verify_container(self.container_id, self.session_id)
            stderr_file, stderr_path = self._new_stderr()
            command = [DOCKER, "--context", "desktop-linux", "exec", "-i", self.container_id, "/bin/bash", "-lc", "exec 3<>/dev/tcp/127.0.0.1/5432; exec 4<&0; writer=; reader=; cleanup(){ [ -n \"$writer\" ] && kill \"$writer\" 2>/dev/null || true; [ -n \"$reader\" ] && kill \"$reader\" 2>/dev/null || true; wait \"$writer\" 2>/dev/null || true; wait \"$reader\" 2>/dev/null || true; }; trap cleanup EXIT INT TERM; cat <&4 >&3 & writer=$!; cat <&3 & reader=$!; wait -n \"$writer\" \"$reader\" || true"]
            process = subprocess.Popen(command, stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=stderr_file, env=_docker_environment())
            if process.stdin is None or process.stdout is None:
                raise RuntimeError("Docker exec did not provide byte pipes")
            incoming = threading.Thread(target=self._copy_in, args=(client, process.stdin), name="hflypi-tc-relay-in", daemon=True)
            outgoing = threading.Thread(target=self._copy_out, args=(process.stdout, client), name="hflypi-tc-relay-out", daemon=True)
            bridge = {"client": client, "process": process, "incoming": incoming, "outgoing": outgoing, "stderr_file": stderr_file, "stderr_path": stderr_path}
            with self.lock:
                self.bridges[id(process)] = bridge
            incoming.start()
            outgoing.start()
            incoming.join(CONNECTION_SECONDS)
            outgoing.join(CONNECTION_SECONDS)
        except BaseException:
            error = sys.exception()
            self._record_failure(f"relay connection failure: {type(error).__name__}: {error}")
        finally:
            try:
                if bridge is not None:
                    claimed = self._claim_bridge(process)
                    if claimed is not None:
                        self._finish_bridge(claimed)
                elif process is not None:
                    self._finish_prebridge(process, stderr_file, stderr_path)
                elif stderr_file is not None:
                    stderr_file.close()
                    if stderr_path is not None:
                        stderr_path.unlink(missing_ok=True)
            except BaseException:
                error = sys.exception()
                self._record_failure(f"relay connection cleanup failure: {type(error).__name__}: {error}")
            finally:
                client.close()
                with self.lock:
                    self.workers.discard(threading.current_thread())
                self.semaphore.release()

    def _claim_bridge(self, process) -> dict[str, object] | None:
        if process is None:
            return None
        with self.lock:
            return self.bridges.pop(id(process), None)

    def _finish_prebridge(self, process, stderr_file, stderr_path: Path | None) -> None:
        exit_mode = "terminated_without_pipe"
        try:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    exit_mode = "killed_without_pipe"
                    process.kill()
                    process.wait(timeout=2)
        finally:
            if stderr_file is not None:
                stderr_file.close()
            stderr_payload = b""
            if stderr_path is not None:
                try:
                    stderr_payload = stderr_path.read_bytes()
                finally:
                    stderr_path.unlink(missing_ok=True)
            entry = {"returncode": process.poll(), "exit_mode": exit_mode, "stderr_bytes": len(stderr_payload), "stderr_tail": stderr_payload[-STDERR_BYTES:].decode(errors="replace")}
            with self.lock:
                self.exec_results.append(entry)
            self._record_failure(json.dumps(entry, sort_keys=True))

    def _copy_in(self, client: socket.socket, stream) -> None:
        try:
            while not self.stopping.is_set():
                payload = client.recv(65536)
                if not payload:
                    return
                stream.write(payload)
                stream.flush()
        except (OSError, BrokenPipeError):
            return
        finally:
            try:
                stream.close()
            except OSError:
                pass

    def _copy_out(self, stream, client: socket.socket) -> None:
        try:
            while not self.stopping.is_set():
                payload = os.read(stream.fileno(), 65536)
                if not payload:
                    return
                client.sendall(payload)
        except OSError:
            return
        finally:
            try:
                client.shutdown(socket.SHUT_WR)
            except OSError:
                pass

    def _finish_bridge(self, bridge: dict[str, object]) -> None:
        client = bridge["client"]
        process = bridge["process"]
        incoming = bridge["incoming"]
        outgoing = bridge["outgoing"]
        stderr_file = bridge["stderr_file"]
        stderr_path = bridge["stderr_path"]
        if not isinstance(client, socket.socket) or not isinstance(incoming, threading.Thread) or not isinstance(outgoing, threading.Thread) or stderr_file is None or not isinstance(stderr_path, Path) or not all(hasattr(process, name) for name in ("poll", "terminate", "kill", "wait")):
            self._record_failure("relay bridge record is invalid")
            return
        try:
            client.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        client.close()
        incoming.join(EXEC_GRACE_SECONDS)
        exit_mode = "graceful"
        if incoming.is_alive():
            exit_mode = "terminated_after_input_close_timeout"
            process.terminate()
            try:
                process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                exit_mode = "killed_after_input_close_timeout"
                process.kill()
                process.wait(timeout=2)
        elif process.poll() is None:
            try:
                process.wait(timeout=EXEC_GRACE_SECONDS)
            except subprocess.TimeoutExpired:
                exit_mode = "terminated_after_grace"
                process.terminate()
                try:
                    process.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    exit_mode = "killed_after_terminate"
                    process.kill()
                    process.wait(timeout=2)
        outgoing.join(EXEC_GRACE_SECONDS)
        stderr_file.close()
        try:
            stderr_payload = stderr_path.read_bytes()
        finally:
            stderr_path.unlink(missing_ok=True)
        entry = {"returncode": process.poll(), "exit_mode": exit_mode, "stderr_bytes": len(stderr_payload), "stderr_tail": stderr_payload[-STDERR_BYTES:].decode(errors="replace")}
        with self.lock:
            self.exec_results.append(entry)
        if entry["returncode"] != 0 or entry["exit_mode"] != "graceful":
            self._record_failure(json.dumps(entry, sort_keys=True))

    def evidence(self) -> dict[str, object]:
        with self.lock:
            return {
                "container_id": self.container_id,
                "session_id": self.session_id,
                "connections": self.total_connections,
                "connection_budget": self.connection_budget,
                "rejections": self.rejections,
                "active": len(self.bridges),
                "failures": list(self.failures),
                "exec_results": list(self.exec_results),
                "expires_at": self.expires_at,
            }

    def _remove_capability(self) -> None:
        path = self._capability_path
        if path is None or not path.exists() or path.is_symlink():
            return
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return
        if isinstance(payload, dict) and payload.get("nonce") == NONCE and payload.get("parent_pid") == os.getpid() and payload.get("container_id") == self.container_id and payload.get("session_id") == self.session_id:
            path.unlink()

    def _journal_close(self) -> None:
        descriptor = os.open(self.journal_path, os.O_WRONLY | os.O_APPEND | os.O_CREAT, 0o600)
        try:
            _write_all(descriptor, (json.dumps(self.evidence(), sort_keys=True) + "\n").encode())
        finally:
            os.close(descriptor)

    def close(self) -> None:
        if self.closed:
            return
        self.closed = True
        self.stopping.set()
        listener = self.listener
        if listener is not None:
            listener.close()
        if self.accept_thread is not None:
            self.accept_thread.join(2)
        with self.lock:
            bridges = list(self.bridges.values())
            workers = list(self.workers)
        for bridge in bridges:
            client = bridge.get("client")
            if isinstance(client, socket.socket):
                try:
                    client.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                client.close()
        deadline = time.monotonic() + 20
        for worker in workers:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                self._record_failure("relay close budget exhausted")
                break
            worker.join(remaining)
            if worker.is_alive():
                self._record_failure("relay worker did not stop")
        with self.lock:
            leftovers = list(self.bridges.values())
        for bridge in leftovers:
            claimed = self._claim_bridge(bridge.get("process"))
            if claimed is None:
                continue
            try:
                self._finish_bridge(claimed)
            except BaseException:
                error = sys.exception()
                self._record_failure(f"relay leftover cleanup failure: {type(error).__name__}: {error}")
        try:
            self._remove_capability()
        except BaseException:
            error = sys.exception()
            self._record_failure(f"capability cleanup failure: {type(error).__name__}: {error}")
        try:
            self._journal_close()
        except BaseException:
            error = sys.exception()
            self._record_failure(f"close journal failure: {type(error).__name__}: {error}")
        if self.failures:
            raise RuntimeError("relay audit failed; inspect close journal")
