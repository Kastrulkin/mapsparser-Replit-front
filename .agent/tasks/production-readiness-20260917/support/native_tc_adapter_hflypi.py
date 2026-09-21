"""One allowlisted test module/lifecycle, internal-only PostgreSQL.

Support code only: installs transport/lifecycle hooks, never changes product
code, migration logic, fixtures or assertions. Not a general Testcontainers
adapter. The guarded launcher owns timeout and abnormal-process cleanup.
"""

from __future__ import annotations

import atexit
import json
import os
from pathlib import Path
import re
import sys
import time
from types import SimpleNamespace

import native_tc_relay_hflypi


PREFIX = "LOCALOS_HFLYPI_TC_"
TAG = "pgvector/pgvector:0.8.0-pg16-trixie"
IMAGE = "sha256:4f26f01433671ee540195bff27f4890acca58cb49cf6d61ea12008d842ec0699"
NETWORK = "localos-readiness-hflypi-tc-internal"
NETWORK_ID = "6fc9dbcb68ce40e46030cec829ed4613840327eda4109cd09de4ada422a4a0b4"
OWNER = "production-readiness-20260917-hfLYPi"
EVIDENCE = Path("/private/tmp/localos-readiness-20260921.hfLYPi/native/evidence")
PROFILE_PREFIXES = {
    "card-growth-v1": "native-tc-one",
    "client-info-v1": "native-tc-client-info",
    "capabilities-phase1-v1": "native-tc-capabilities-phase1",
    "operator-service-creation-v1": "native-tc-operator-service-creation",
    "work-review-rollback-v1": "native-tc-work-review-rollback",
}
PARENT_DATABASE_PROFILES = frozenset({"client-info-v1", "capabilities-phase1-v1"})
OPERATOR_VOICE_TEST_DSN_PROFILES = frozenset({"operator-service-creation-v1"})
WORK_REVIEW_ROLLBACK_PROFILE = "work-review-rollback-v1"
WORK_REVIEW_DATABASE_PATTERN = re.compile(r"work_review_rollback_[0-9a-f]{32}")
_active = None
_relay = None
_started = False
_events = []
_original_stop = None
_session = ""
_journal = None
_database_url = None
_operator_voice_test_dsn = None


def deny(reason: str) -> None:
    raise PermissionError(f"hfLYPi Testcontainers adapter: {reason}")


def record(event: str, **fields) -> None:
    _events.append({"event": event, "pid": os.getpid(), "time": time.time(), **fields})
    if _journal is not None:
        descriptor = os.open(_journal, os.O_WRONLY | os.O_CREAT | os.O_APPEND | os.O_NOFOLLOW, 0o600)
        try:
            os.write(descriptor, (json.dumps(_events[-1], sort_keys=True) + "\n").encode())
        finally:
            os.close(descriptor)


def validate_dsn(parsed: dict[str, str]) -> None:
    database = parsed.get("dbname")
    profile = os.environ.get(PREFIX + "MODE", "")
    allowed_database = database == "test"
    if profile == WORK_REVIEW_ROLLBACK_PROFILE:
        allowed_database = database == "postgres" or isinstance(database, str) and WORK_REVIEW_DATABASE_PATTERN.fullmatch(database) is not None
    if parsed.get("host") != "127.0.0.1" or not allowed_database or parsed.get("user") != "test" or parsed.get("password") != "test":
        deny("DSN is outside the single synthetic test database")
    port = parsed.get("port", "")
    if not port.isdigit():
        deny("missing literal relay port")
    path = os.environ.get(PREFIX + "CAPABILITY", "")
    result = native_tc_relay_hflypi.validate_capability(Path(path), int(port))
    if result.get("session_id") != os.environ.get("LOCALOS_HFLYPI_TESTCONTAINERS_SESSION_ID"):
        deny("capability session differs from parent Testcontainers session")
    record("dsn_admitted", port=int(port), database=database, container_id=result.get("container_id"))


def bind_parent_database(port: int) -> None:
    """Supply required Flask import config only for this owned test lifecycle."""
    global _database_url
    if os.environ.get(PREFIX + "MODE") not in PARENT_DATABASE_PROFILES:
        return
    if os.environ.get(PREFIX + "OWNER_PID") != str(os.getpid()) or "DATABASE_URL" in os.environ or _database_url is not None:
        deny("refusing to replace parent database configuration")
    validate_dsn({"host": "127.0.0.1", "port": str(port), "dbname": "test", "user": "test", "password": "test"})
    _database_url = f"postgresql://test:test@127.0.0.1:{port}/test"
    os.environ["DATABASE_URL"] = _database_url
    record("parent_database_bound", port=port, database="test")


def unbind_parent_database() -> None:
    global _database_url
    if _database_url is None:
        return
    if os.environ.get("DATABASE_URL") != _database_url:
        deny("parent database configuration changed during test")
    del os.environ["DATABASE_URL"]
    _database_url = None
    record("parent_database_unbound")


def bind_operator_voice_test_dsn(port: int) -> None:
    """Supply the owned relay DSN for the frozen operator voice fixture only."""
    global _operator_voice_test_dsn
    if os.environ.get(PREFIX + "MODE") not in OPERATOR_VOICE_TEST_DSN_PROFILES:
        return
    if os.environ.get(PREFIX + "OWNER_PID") != str(os.getpid()) or "OPERATOR_VOICE_TEST_DSN" in os.environ or _operator_voice_test_dsn is not None:
        deny("refusing to replace operator voice test DSN")
    validate_dsn({"host": "127.0.0.1", "port": str(port), "dbname": "test", "user": "test", "password": "test"})
    _operator_voice_test_dsn = f"postgresql://test:test@127.0.0.1:{port}/test"
    os.environ["OPERATOR_VOICE_TEST_DSN"] = _operator_voice_test_dsn
    record("operator_voice_test_dsn_bound", port=port, database="test")


def unbind_operator_voice_test_dsn() -> None:
    global _operator_voice_test_dsn
    if _operator_voice_test_dsn is None:
        return
    if os.environ.get("OPERATOR_VOICE_TEST_DSN") != _operator_voice_test_dsn:
        deny("operator voice test DSN changed during test")
    del os.environ["OPERATOR_VOICE_TEST_DSN"]
    _operator_voice_test_dsn = None
    record("operator_voice_test_dsn_unbound")


def check_network(client) -> None:
    network = client.networks.get(NETWORK_ID)
    network.reload()
    attrs = network.attrs
    labels = attrs.get("Labels", {})
    if attrs.get("Name") != NETWORK or attrs.get("Id") != NETWORK_ID or attrs.get("Internal") is not True or attrs.get("Driver") != "bridge":
        deny("retained internal network identity differs")
    if labels.get("localos.audit.owner") != OWNER or labels.get("localos.audit.nonce") != "hfLYPi" or labels.get("localos.audit.scope") != "native-tc-internal-probe":
        deny("retained internal network labels differ")
    if attrs.get("Containers"):
        deny("retained internal network is not empty")
    if client.images.get(IMAGE).id != IMAGE:
        deny("approved local PostgreSQL image missing")


def install() -> None:
    global _original_stop, _session, _journal
    from testcontainers.core.container import DockerContainer
    from testcontainers.core.labels import SESSION_ID
    from testcontainers.community.postgres import PostgresContainer

    owner = os.environ.setdefault(PREFIX + "OWNER_PID", str(os.getpid()))
    if not owner.isdigit():
        deny("invalid adapter owner pid")
    raw_journal = os.environ.get(PREFIX + "JOURNAL", "")
    _journal = Path(raw_journal)
    profile = os.environ.get(PREFIX + "MODE", "")
    journal_prefix = PROFILE_PREFIXES.get(profile)
    if journal_prefix is None:
        deny("unsupported Testcontainers profile")
    if _journal.parent != EVIDENCE or not re.fullmatch(re.escape(journal_prefix) + r"-v[1-9][0-9]*-events.jsonl", _journal.name) or _journal.is_symlink():
        deny("journal path is outside this experiment")
    _session = os.environ.get("LOCALOS_HFLYPI_TESTCONTAINERS_SESSION_ID", str(SESSION_ID))
    if owner == str(os.getpid()):
        if _session != str(SESSION_ID):
            deny("parent session conflicts with the actual Testcontainers library session")
        os.environ["LOCALOS_HFLYPI_TESTCONTAINERS_SESSION_ID"] = _session
    original_start = DockerContainer.start
    _original_stop = DockerContainer.stop
    original_host = DockerContainer.get_container_host_ip
    original_port = DockerContainer.get_exposed_port

    def start(instance, *arguments, **keywords):
        global _active, _relay, _started
        if owner != str(os.getpid()) or _started or arguments or keywords:
            deny("only one parent-owned Testcontainers start is permitted")
        if type(instance) is not PostgresContainer or instance.image != TAG:
            deny("only the exact approved PostgresContainer may start")
        if instance._kwargs or instance._command is not None or instance._name is not None or instance._network is not None or instance._network_aliases or instance._transferable_specs or instance._wait_strategy is not None or instance.volumes or instance.tmpfs or instance.ports != {"5432": None}:
            deny("unexpected Testcontainers configuration")
        if instance.username != "test" or instance.password != "test" or instance.dbname != "test" or instance.env != {"POSTGRES_USER": "test", "POSTGRES_PASSWORD": "test", "POSTGRES_DB": "test"}:
            deny("unexpected synthetic PostgreSQL credentials or environment")
        if profile in PARENT_DATABASE_PROFILES and "DATABASE_URL" in os.environ:
            deny("parent database configuration must be absent before owned start")
        if profile in OPERATOR_VOICE_TEST_DSN_PROFILES and "OPERATOR_VOICE_TEST_DSN" in os.environ:
            deny("operator voice test DSN must be absent before owned start")
        client = instance.get_docker_client().client
        check_network(client)
        # Testcontainers otherwise pulls if the image disappears between its
        # own lookup and create. This experiment is strictly local-image-only.
        def refuse_pull(*pull_arguments, **pull_keywords):
            deny("image pulls are outside this local integration experiment")
        client.api.pull = refuse_pull
        _started = True
        _active = instance
        instance.image = IMAGE
        instance.ports = {}
        instance._network = SimpleNamespace(name=NETWORK)
        instance.tmpfs = {"/var/lib/postgresql/data": "rw,noexec,nosuid,size=512m"}
        instance._kwargs = {
            "labels": {
                "localos.audit.owner": OWNER,
                "localos.audit.nonce": "hfLYPi",
                "localos.audit.scope": "native-tc-integration",
            },
            "platform": "linux/arm64", "mem_limit": "768m", "pids_limit": 128,
        }
        record("start_requested", session_id=_session, image=IMAGE, network_id=NETWORK_ID)
        result = original_start(instance)
        container_id = instance.get_container_id()
        native_tc_relay_hflypi.verify_container(container_id, _session)
        record("container_created", container_id=container_id, session_id=_session)
        _relay = native_tc_relay_hflypi.Relay(container_id, _session, _journal.with_name(_journal.stem.replace("-events", "-relay") + ".json"), profile)
        port = _relay.start()
        os.environ[PREFIX + "CAPABILITY"] = str(_relay.capability_path)
        record("relay_started", container_id=container_id, port=port, capability_path=str(_relay.capability_path))
        checks = native_tc_relay_hflypi.negative_capability_checks(_relay.capability_path, port)
        if not checks or not all(item.get("denied") is True for item in checks):
            deny("negative capability checks did not all fail closed")
        record("capability_denials", checks=checks)
        bind_parent_database(port)
        bind_operator_voice_test_dsn(port)
        return result

    def stop(instance, force=True, delete_volume=True):
        global _active, _relay
        if instance is not _active:
            if instance._container is not None:
                deny("refusing cleanup of an unowned container")
            instance.get_docker_client().client.close()
            return
        failures = []
        try:
            unbind_operator_voice_test_dsn()
        except BaseException:
            failures.append(type(sys.exception()).__name__)
        try:
            unbind_parent_database()
        except BaseException:
            failures.append(type(sys.exception()).__name__)
        if profile == WORK_REVIEW_ROLLBACK_PROFILE and instance._container is not None:
            try:
                result = instance._container.exec_run(
                    [
                        "psql",
                        "-U",
                        "test",
                        "-d",
                        "postgres",
                        "-At",
                        "-c",
                        "SELECT COUNT(*) FROM pg_database WHERE datname ~ '^work_review_rollback_[0-9a-f]{32}$'",
                    ]
                )
                output = result.output.decode().strip() if isinstance(result.output, bytes) else str(result.output).strip()
                if result.exit_code != 0 or output != "0":
                    deny("work-review disposable database remains before container cleanup")
                record("work_review_database_cleanup_checked", remaining=0)
            except BaseException:
                failures.append(type(sys.exception()).__name__)
        if _relay is not None:
            try:
                _relay.close()
            except BaseException:
                failures.append(type(sys.exception()).__name__)
        os.environ.pop(PREFIX + "CAPABILITY", None)
        try:
            if instance._container is not None:
                container_id = instance.get_container_id()
                native_tc_relay_hflypi.verify_container(container_id, _session, require_running=False)
                # Only this newly-created, freshly verified tmpfs test container.
                # Never request deletion of Docker volumes.
                _original_stop(instance, force=True, delete_volume=False)
                record("container_removed", container_id=container_id)
            else:
                instance.get_docker_client().client.close()
        except BaseException:
            failures.append(type(sys.exception()).__name__)
        _active = None
        _relay = None
        record("cleanup", errors=failures)
        if failures:
            raise RuntimeError("owned Testcontainers cleanup failed: " + ",".join(failures))

    def host(instance):
        if instance is _active and _relay is not None:
            return "127.0.0.1"
        return original_host(instance)

    def port(instance, number):
        if instance is _active and _relay is not None:
            if number != 5432:
                deny("only PostgreSQL relay port is available")
            return _relay.port
        return original_port(instance, number)

    DockerContainer.start = start
    DockerContainer.stop = stop
    DockerContainer.get_container_host_ip = host
    DockerContainer.get_exposed_port = port
    atexit.register(lambda: stop(_active) if _active is not None else None)
