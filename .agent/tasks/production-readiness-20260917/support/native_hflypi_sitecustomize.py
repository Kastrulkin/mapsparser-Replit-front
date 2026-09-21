"""DRAFT / UNEXECUTED fail-closed guard source for the ``hfLYPi`` aggregate.

Copy these bytes to frozen ``source/src/sitecustomize.py`` and put that path
first in ``PYTHONPATH``.  That preserves the guard in Alembic children whose
``tests/conftest.py`` replaces PYTHONPATH with ``<archive>/src:<archive>``.
The wrapper must set a literal Docker socket, disable Ryuk, use the literal
Testcontainers host override, blank providers, and clean exact labels itself.
Do not use this draft until the launcher-level child-environment propagation
policy has been independently reviewed.
"""

from __future__ import annotations

import os
from pathlib import Path
import re
import socket
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
AGGREGATE_GUARD_ACTIVE_PID = os.getpid()
DOCKER_SOCKET = ""
_testcontainer_ports: set[int] = set()
_owned_listener_ports: set[int] = set()


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
    if os.environ.get("TESTCONTAINERS_RYUK_DISABLED", "").lower() not in {"1", "true"}:
        raise RuntimeError("TESTCONTAINERS_RYUK_DISABLED=true is required; wrapper owns exact labelled cleanup")
    if os.environ.get("TESTCONTAINERS_HOST_OVERRIDE", "") != "127.0.0.1":
        raise RuntimeError("TESTCONTAINERS_HOST_OVERRIDE must be literal 127.0.0.1")
    network_name = _testcontainers_network()
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.labels import SESSION_ID

    original = DockerContainer.start
    if getattr(original, "_hflypi_guarded", False):
        return

    def guarded_start(container: object, *arguments, **keywords):
        if str(getattr(container, "image", "")) != POSTGRES_IMAGE:
            _deny("only approved PostgreSQL 16 testcontainers may start")
        current = getattr(container, "_kwargs", {})
        updated = dict(current) if isinstance(current, dict) else {}
        raw_labels = updated.get("labels", {})
        labels = dict(raw_labels) if isinstance(raw_labels, dict) else {}
        labels.update({AUDIT_LABEL: AUDIT_LABEL_VALUE, NONCE_LABEL: NONCE})
        updated["labels"] = labels
        updated["network"] = network_name
        with_kwargs = getattr(container, "with_kwargs", None)
        if not callable(with_kwargs):
            _deny("testcontainer does not support labelled startup")
        with_kwargs(**updated)
        ports = getattr(container, "ports", {})
        if not isinstance(ports, dict):
            _deny("testcontainer PostgreSQL port map is invalid")
        postgres_keys = [key for key in ports if str(key).split("/", 1)[0] == "5432"]
        if not postgres_keys:
            postgres_keys = ["5432/tcp"]
        for key in postgres_keys:
            ports[key] = ("127.0.0.1", 0)
        result = original(container, *arguments, **keywords)
        _register_postgres(getattr(container, "get_wrapped_container")(), str(SESSION_ID))
        os.environ[PARENT_SESSION_ENV] = str(SESSION_ID)
        return result

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
    _patch_psycopg2()
    _patch_testcontainers()


try:
    _initialize()
except BaseException:
    # CPython otherwise reports a sitecustomize error and continues unguarded.
    os._exit(78)
