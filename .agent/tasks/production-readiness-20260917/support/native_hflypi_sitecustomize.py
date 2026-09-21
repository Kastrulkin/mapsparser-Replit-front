"""Fail-closed guard source for the ``hfLYPi`` frozen-source audit.

Copy these bytes to frozen ``source/src/sitecustomize.py`` and put that path
first in ``PYTHONPATH``.  That preserves the guard in Alembic children whose
``tests/conftest.py`` replaces PYTHONPATH with ``<archive>/src:<archive>``.
The wrapper must set a literal Docker socket, disable Ryuk, use the literal
Testcontainers host override, blank providers, and clean exact labels itself.
The default mode still denies Testcontainers. A separately hash-pinned adapter
can enable only named internal-only card-growth, client-info, capabilities,
operator-service, rollback or exact shared-fixture PostgreSQL experiments.
This is a trusted-test safety guard, not a sandbox for hostile native code.
"""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys


NONCE = "hfLYPi"
NATIVE_HOSTS = {"127.0.0.1", "::1"}
NATIVE_PORT = 35418
AUDIT_LABEL = "localos.audit"
AUDIT_LABEL_VALUE = "production-readiness-20260917"
NONCE_LABEL = "localos.audit.nonce"
POSTGRES_IMAGE = "pgvector/pgvector:0.8.0-pg16-trixie"
PARENT_SESSION_ENV = "LOCALOS_HFLYPI_TESTCONTAINERS_SESSION_ID"
TESTCONTAINERS_NETWORK_ENV = "LOCALOS_HFLYPI_TESTCONTAINERS_NETWORK"
TESTCONTAINERS_NETWORK = "localos-readiness-hflypi_internal"
FROZEN_SOURCE_ROOT = Path("/private/tmp/localos-readiness-20260921.hfLYPi/source")
GUARD_HASH_ENVIRONMENTS = (
    "LOCALOS_READINESS_ENDPOINT_GUARD_SHA256",
    "LOCALOS_CALLBACK_RECOVERY_GUARD_SHA256",
    "LOCALOS_AGENT_FINANCE_UNTRUSTED_ROWS_GUARD_SHA256",
    "LOCALOS_VIEWER_MUTATION_GUARD_SHA256",
    "LOCALOS_SOCIAL_VIEWER_GUARD_SHA256",
)
LIBPQ_OVERRIDE_ENVIRONMENTS = ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")
AGGREGATE_GUARD_ACTIVE_PID = os.getpid()
DOCKER_SOCKET = ""
_testcontainer_ports: set[int] = set()
_owned_listener_ports: set[int] = set()
_tc_adapter = None
TC_ENVIRONMENTS = (
    "LOCALOS_HFLYPI_TC_MODE", "LOCALOS_HFLYPI_TC_ADAPTER_SHA256",
    "LOCALOS_HFLYPI_TC_RELAY_SHA256", "LOCALOS_HFLYPI_TC_OWNER_PID",
    "LOCALOS_HFLYPI_TC_CAPABILITY", "LOCALOS_HFLYPI_TC_JOURNAL",
)


def _deny(message: str) -> None:
    raise PermissionError(f"hfLYPi native aggregate guard: {message}")


def _docker_socket() -> str:
    value = os.environ.get("LOCALOS_HFLYPI_DOCKER_SOCKET", "").strip()
    if not value or not Path(value).is_absolute() or Path(value).name != "docker.sock":
        raise RuntimeError("LOCALOS_HFLYPI_DOCKER_SOCKET must be an absolute docker.sock path")
    return value


def _testcontainers_network() -> str:
    if os.environ.get(TESTCONTAINERS_NETWORK_ENV, "") != TESTCONTAINERS_NETWORK:
        raise RuntimeError(f"{TESTCONTAINERS_NETWORK_ENV} must name the owned internal network")
    return TESTCONTAINERS_NETWORK


def _child_kind(command: object, uses_shell: object) -> str:
    """Classify only direct Python invocations; shell Python is refused."""
    if isinstance(command, (list, tuple)) and command:
        executable = Path(str(command[0])).name.lower()
        words = [str(value) for value in command]
        if executable in {"sh", "bash", "zsh"} and any("python" in value.lower() for value in words[1:]):
            _deny("shell-launched Python child is not covered by the native guard")
        if executable.startswith("python"):
            if uses_shell:
                _deny("Python child may not use shell execution")
            options = [value[1:] for value in words[1:] if value.startswith("-") and not value.startswith("--")]
            if any(any(flag in {"E", "I", "S"} for flag in value) for value in options):
                _deny("Python child may not disable site initialization")
            return "python"
        return "other"
    if isinstance(command, str) and not uses_shell:
        pieces = command.split()
        if pieces and Path(pieces[0]).name.lower().startswith("python"):
            if len(pieces) != 1:
                _deny("string Python command must use an argv sequence")
            return "python"
    if uses_shell and isinstance(command, str) and "python" in command.lower():
        _deny("shell-launched Python child is not covered by the native guard")
    return "other"


def _child_environment(requested: dict[str, str], source_root: Path, guard_sha256: str) -> dict[str, str]:
    """Return the only safe environment for a direct guarded Python child."""
    if source_root.resolve() != FROZEN_SOURCE_ROOT or not re.fullmatch(r"[0-9a-f]{64}", guard_sha256):
        _deny("child guard source or hash is not pinned")
    environment = dict(requested)
    required = {
        "LOCALOS_HFLYPI_DOCKER_SOCKET": DOCKER_SOCKET,
        "LOCALOS_HFLYPI_SOURCE_ROOT": str(source_root),
        "DOCKER_HOST": f"unix://{DOCKER_SOCKET}",
        "TESTCONTAINERS_RYUK_DISABLED": "true",
        "TESTCONTAINERS_HOST_OVERRIDE": "127.0.0.1",
        TESTCONTAINERS_NETWORK_ENV: TESTCONTAINERS_NETWORK,
        "PYTHON_DOTENV_DISABLED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONNOUSERSITE": "1",
        "LOCALOS_HFLYPI_EXPECTED_GUARD_SHA256": guard_sha256,
    }
    for key in (PARENT_SESSION_ENV, *TC_ENVIRONMENTS):
        if os.environ.get(key):
            required[key] = os.environ[key]
        else:
            if environment.get(key):
                _deny(f"child may not enable parent-disabled {key}")
            environment.pop(key, None)
    for key, value in required.items():
        supplied = environment.get(key)
        if supplied is not None and supplied != value:
            _deny(f"child environment conflicts with guarded {key}")
        environment[key] = value
    for key in GUARD_HASH_ENVIRONMENTS:
        supplied = environment.get(key)
        if supplied is not None and supplied != guard_sha256:
            _deny(f"child environment conflicts with pinned {key}")
        environment[key] = guard_sha256
    for key in LIBPQ_OVERRIDE_ENVIRONMENTS:
        if environment.get(key):
            _deny(f"child environment carries forbidden {key}")
        environment.pop(key, None)
    environment["PYTHONPATH"] = os.pathsep.join((str(source_root / "src"), str(source_root)))
    return environment


def _safe_container_kwargs(current: object) -> dict[str, object]:
    """Admit only Testcontainers options demonstrated harmless in this draft."""
    if not isinstance(current, dict):
        _deny("testcontainer startup kwargs are invalid")
    unsupported = set(current) - {"labels", "platform"}
    if unsupported:
        _deny("testcontainer startup options exceed the native draft policy")
    labels = current.get("labels", {})
    if not isinstance(labels, dict) or not all(isinstance(key, str) and isinstance(value, str) for key, value in labels.items()):
        _deny("testcontainer labels are invalid")
    platform = current.get("platform")
    if platform is not None and not isinstance(platform, str):
        _deny("testcontainer platform is invalid")
    return dict(current)


def _patch_subprocess() -> None:
    """Keep direct Python subprocesses guarded when tests pass a small env."""
    original = subprocess.Popen
    if getattr(original, "_hflypi_guarded", False):
        return
    guard_file = Path(__file__).resolve()
    if guard_file != FROZEN_SOURCE_ROOT / "src" / "sitecustomize.py":
        raise RuntimeError("native guard is not loaded from the frozen source archive")
    guard_sha256 = hashlib.sha256(guard_file.read_bytes()).hexdigest()

    def guarded_popen(*arguments, **keywords):
        command = arguments[0] if arguments else keywords.get("args")
        if len(arguments) > 1:
            _deny("Popen positional options are not permitted")
        if keywords.get("executable") is not None:
            _deny("Popen executable override is not permitted")
        if _child_kind(command, keywords.get("shell", False)) == "python":
            requested = keywords.get("env")
            source = os.environ if requested is None else requested
            try:
                source_environment = dict(source)
            except (TypeError, ValueError):
                _deny("Python child environment must be a string dictionary")
            updated = dict(keywords)
            updated["env"] = _child_environment(source_environment, FROZEN_SOURCE_ROOT, guard_sha256)
            keywords = updated
        return original(*arguments, **keywords)

    setattr(guarded_popen, "_hflypi_guarded", True)
    subprocess.Popen = guarded_popen


def _host(value: object) -> str:
    return str(value).split("%", 1)[0]


def _port_allowed(port: object) -> bool:
    return isinstance(port, int) and port in ({NATIVE_PORT} | _testcontainer_ports | _owned_listener_ports)


def _allow_inet(address: object) -> None:
    if not isinstance(address, tuple) or len(address) < 2:
        _deny("network address must be an IP tuple")
    if _host(address[0]) not in NATIVE_HOSTS or not _port_allowed(address[1]):
        _deny(f"TCP destination is not owned literal loopback: {_host(address[0])}:{address[1]}")


def _allow_connect(instance: socket.socket, address: object) -> None:
    if instance.family == socket.AF_UNIX:
        if not isinstance(address, (str, bytes, os.PathLike)) or os.fsdecode(address) != DOCKER_SOCKET:
            _deny("Unix socket is not the configured Docker daemon")
    elif instance.family in {socket.AF_INET, socket.AF_INET6}:
        _allow_inet(address)
    else:
        _deny(f"socket family {instance.family} is not permitted")


class _GuardedSocket(socket.socket):
    """Register only a loopback port-zero reservation made by this process.

    Browser helpers may close this reservation before Node binds it, so a local
    TOCTOU remains.  The wrapper must record the child process/port; this is
    not a general loopback permission.
    """

    def bind(self, address):
        if self.family not in {socket.AF_INET, socket.AF_INET6}:
            _deny("non-IP listener is forbidden")
        if not isinstance(address, tuple) or len(address) < 2 or _host(address[0]) not in NATIVE_HOSTS or address[1] != 0:
            _deny("only literal loopback port-zero listener reservation is permitted")
        result = super().bind(address)
        resolved = self.getsockname()
        if not isinstance(resolved, tuple) or len(resolved) < 2 or not isinstance(resolved[1], int):
            _deny("could not register owned loopback listener")
        _owned_listener_ports.add(resolved[1])
        return result


def _audit(event: str, arguments: tuple[object, ...]) -> None:
    if event == "socket.connect":
        if len(arguments) != 2 or not isinstance(arguments[0], socket.socket):
            _deny("malformed socket.connect audit event")
        _allow_connect(arguments[0], arguments[1])
    elif event == "socket.sendto":
        _deny("UDP and datagram sends are forbidden")
    elif event == "socket.getaddrinfo":
        if len(arguments) < 2:
            _deny("malformed getaddrinfo audit event")
        _allow_inet((arguments[0], arguments[1]))
    elif event in {"socket.gethostbyname", "socket.gethostbyname_ex", "socket.gethostbyaddr", "socket.getnameinfo"}:
        _deny("DNS and hostname resolution are forbidden")


def _validate_dsn(dsn: object, kwargs: dict[str, object]) -> None:
    import psycopg2

    if any(os.environ.get(key) for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")):
        _deny("inherited libpq host, service or options override")
    parsed = psycopg2.extensions.parse_dsn(psycopg2.extensions.make_dsn(dsn, **kwargs))
    host, port, database = str(parsed.get("host") or ""), str(parsed.get("port") or ""), str(parsed.get("dbname") or "")
    if parsed.get("hostaddr") or parsed.get("service") or parsed.get("options") or host not in NATIVE_HOSTS or not port.isdigit():
        _deny("PostgreSQL DSN is not explicit literal loopback")
    number = int(port)
    if _tc_adapter is not None:
        try:
            _tc_adapter.validate_dsn(parsed)
        except PermissionError:
            _deny("Testcontainers relay capability or DSN is not authorized")
        return
    if number in _testcontainer_ports or _verified_testcontainer_port(number):
        return
    if number != NATIVE_PORT:
        _deny("PostgreSQL port is not owned by this aggregate")
    allowed = (
        database == "postgres"
        or database == "readiness_hflypi"
        or database == "readiness_full_test_hflypi"
        or re.fullmatch(r"readiness_full_test_[a-z0-9_]+", database)
        or re.fullmatch(r"localos_readiness_(endpoint|benchmark|measure|load|queryproof)_[0-9a-f]{32}", database)
    )
    if not allowed:
        _deny("PostgreSQL database is outside hfLYPi owned namespace")


def _verified_testcontainer_port(port: int) -> bool:
    """Recover a parent-created port in a conftest migration child.

    The parent stores the Testcontainers library session it actually used.  A
    child does not trust a port environment variable: it re-inspects Docker
    through the only admitted Unix socket and checks image, library session,
    aggregate labels, running state and loopback-only published binding.
    """
    session = os.environ.get(PARENT_SESSION_ENV, "")
    if not session:
        return False
    import docker

    client = docker.DockerClient(base_url=f"unix://{DOCKER_SOCKET}")
    try:
        matches = client.containers.list(
            all=False,
            filters={"label": [f"{AUDIT_LABEL}={AUDIT_LABEL_VALUE}", f"{NONCE_LABEL}={NONCE}"]},
        )
        for candidate in matches:
            candidate.reload()
            labels, attrs = _labels(candidate)
            config = attrs.get("Config", {}) if isinstance(attrs, dict) else {}
            image = str(config.get("Image", "")) if isinstance(config, dict) else ""
            if image != POSTGRES_IMAGE or labels.get("org.testcontainers") != "true" or labels.get("org.testcontainers.session-id") != session or not _container_is_internal(candidate, attrs):
                continue
            network = attrs.get("NetworkSettings", {}) if isinstance(attrs, dict) else {}
            ports = network.get("Ports", {}) if isinstance(network, dict) else {}
            bindings = ports.get("5432/tcp") if isinstance(ports, dict) else None
            if not isinstance(bindings, list):
                continue
            for binding in bindings:
                host = str(binding.get("HostIp", "")) if isinstance(binding, dict) else ""
                value = str(binding.get("HostPort", "")) if isinstance(binding, dict) else ""
                if host == "127.0.0.1" and value == str(port):
                    _testcontainer_ports.add(port)
                    return True
    finally:
        client.close()
    return False


def _container_is_internal(container: object, attrs: dict[str, object]) -> bool:
    settings = attrs.get("NetworkSettings", {}) if isinstance(attrs, dict) else {}
    networks = settings.get("Networks", {}) if isinstance(settings, dict) else {}
    if not isinstance(networks, dict) or set(networks) != {TESTCONTAINERS_NETWORK}:
        return False
    client = getattr(container, "client", None)
    networks_api = getattr(client, "networks", None)
    get_network = getattr(networks_api, "get", None)
    if not callable(get_network):
        return False
    internal = getattr(get_network(TESTCONTAINERS_NETWORK), "attrs", {})
    return isinstance(internal, dict) and internal.get("Internal") is True


def _patch_psycopg2() -> None:
    import psycopg2

    original = psycopg2.connect
    if getattr(original, "_hflypi_guarded", False):
        return

    def guarded_connect(dsn=None, connection_factory=None, cursor_factory=None, **kwargs):
        _validate_dsn(dsn, kwargs)
        return original(dsn, connection_factory=connection_factory, cursor_factory=cursor_factory, **kwargs)

    setattr(guarded_connect, "_hflypi_guarded", True)
    psycopg2.connect = guarded_connect


def _labels(container: object) -> tuple[dict[str, str], dict[str, object]]:
    reload_method = getattr(container, "reload", None)
    if callable(reload_method):
        reload_method()
    attrs = getattr(container, "attrs", {})
    config = attrs.get("Config", {}) if isinstance(attrs, dict) else {}
    raw = config.get("Labels", {}) if isinstance(config, dict) else {}
    labels = {str(key): str(value) for key, value in raw.items()} if isinstance(raw, dict) else {}
    return labels, attrs if isinstance(attrs, dict) else {}


def _register_postgres(container: object, session: str) -> None:
    labels, attrs = _labels(container)
    config = attrs.get("Config", {}) if isinstance(attrs, dict) else {}
    image = str(config.get("Image", "")) if isinstance(config, dict) else ""
    if image != POSTGRES_IMAGE or labels.get("org.testcontainers") != "true" or labels.get("org.testcontainers.session-id") != session or labels.get(AUDIT_LABEL) != AUDIT_LABEL_VALUE or labels.get(NONCE_LABEL) != NONCE:
        _deny("testcontainer failed image/library-session/aggregate-label validation")
    if not _container_is_internal(container, attrs):
        _deny("testcontainer PostgreSQL is not attached only to the owned internal network")
    network = attrs.get("NetworkSettings", {}) if isinstance(attrs, dict) else {}
    ports = network.get("Ports", {}) if isinstance(network, dict) else {}
    bindings = ports.get("5432/tcp") if isinstance(ports, dict) else None
    if not isinstance(bindings, list) or not bindings:
        _deny("testcontainer PostgreSQL has no published 5432/tcp binding")
    for binding in bindings:
        host = str(binding.get("HostIp", "")) if isinstance(binding, dict) else ""
        value = str(binding.get("HostPort", "")) if isinstance(binding, dict) else ""
        if host != "127.0.0.1" or not value.isdigit() or not 1 <= int(value) <= 65535:
            _deny("testcontainer PostgreSQL binding is not valid literal loopback")
        _testcontainer_ports.add(int(value))


def _patch_testcontainers() -> None:
    global _tc_adapter
    if os.environ.get("TESTCONTAINERS_RYUK_DISABLED", "").lower() not in {"1", "true"}:
        raise RuntimeError("TESTCONTAINERS_RYUK_DISABLED=true is required; wrapper owns exact labelled cleanup")
    if os.environ.get("TESTCONTAINERS_HOST_OVERRIDE", "") != "127.0.0.1":
        raise RuntimeError("TESTCONTAINERS_HOST_OVERRIDE must be literal 127.0.0.1")
    _testcontainers_network()
    mode = os.environ.get("LOCALOS_HFLYPI_TC_MODE", "")
    if mode:
        if mode not in {"card-growth-v1", "client-info-v1", "capabilities-phase1-v1", "operator-service-creation-v1", "work-review-rollback-v1", "creator-portal-rollback-v1", "creator-offer-rollback-v1", "author-daily-gate-pg-v1", "knowledge-schema-pg-v1", "outreach-pain-library-pg-v1", "riderra-template-pg-v1", "sales-room-proposal-race-pg-v1", "sales-room-deadlock-pg-v1", "telegram-shared-audience-pg-v1", "web-tracking-pg-v1", "worker-captcha-pg-v1", "worker-expired-pg-v1", "worker-resume-pg-v1", "finance-import-transaction-pg-v1", "service-compression-race-pg-v1"}:
            _deny("unsupported Testcontainers adapter mode")
        for module, key in (
            ("native_tc_adapter_hflypi", "LOCALOS_HFLYPI_TC_ADAPTER_SHA256"),
            ("native_tc_relay_hflypi", "LOCALOS_HFLYPI_TC_RELAY_SHA256"),
        ):
            path = FROZEN_SOURCE_ROOT / "src" / f"{module}.py"
            expected = os.environ.get(key, "")
            if not re.fullmatch(r"[0-9a-f]{64}", expected) or not path.is_file() or path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
                _deny("Testcontainers adapter source is not pinned")
        import native_tc_adapter_hflypi
        _tc_adapter = native_tc_adapter_hflypi
        _tc_adapter.install()
        return
    from testcontainers.core.container import DockerContainer

    original = DockerContainer.start
    if getattr(original, "_hflypi_guarded", False):
        return

    def guarded_start(container: object, *arguments, **keywords):
        if str(getattr(container, "image", "")) != POSTGRES_IMAGE:
            _deny("only approved PostgreSQL 16 testcontainers may start")
        current = getattr(container, "_kwargs", {})
        _safe_container_kwargs(current)
        _deny("Testcontainers launch is disabled pending dual-owned-network review")

    setattr(guarded_start, "_hflypi_guarded", True)
    DockerContainer.start = guarded_start


def guard_provenance() -> dict[str, object]:
    return {
        "nonce": NONCE,
        "pid": AGGREGATE_GUARD_ACTIVE_PID,
        "docker_socket": DOCKER_SOCKET,
        "native_port": NATIVE_PORT,
        "testcontainer_ports": sorted(_testcontainer_ports),
        "owned_listener_ports": sorted(_owned_listener_ports),
        "ryuk": "disabled; wrapper cleans exact labels",
    }


def _initialize() -> None:
    global DOCKER_SOCKET
    DOCKER_SOCKET = _docker_socket()
    socket.socket = _GuardedSocket
    sys.addaudithook(_audit)
    _patch_subprocess()
    _patch_psycopg2()
    _patch_testcontainers()


def _report_initialization_failure(error: BaseException) -> None:
    frames = []
    current = error.__traceback__
    while current is not None and len(frames) < 20:
        frames.append({
            "file": current.tb_frame.f_code.co_filename,
            "function": current.tb_frame.f_code.co_name,
            "line": current.tb_lineno,
        })
        current = current.tb_next
    payload = {"schema": "hflypi-guard-init-v2", "nonce": NONCE, "exception_type": type(error).__name__, "frames": frames}
    rendered = (json.dumps(payload, sort_keys=True) + "\n").encode()
    while len(rendered) > 8192 and frames:
        frames.pop(0)
        rendered = (json.dumps(payload, sort_keys=True) + "\n").encode()
    while rendered:
        written = os.write(2, rendered)
        if written <= 0:
            break
        rendered = rendered[written:]


try:
    _initialize()
except BaseException:
    # CPython otherwise reports a sitecustomize error and continues unguarded.
    try:
        _report_initialization_failure(sys.exception())
    except BaseException:
        pass
    finally:
        os._exit(78)
