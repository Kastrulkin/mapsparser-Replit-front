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
import uuid

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
    "operator-voice-pg-v1": "native-tc-operator-voice-pg",
    "operator-editorial-pg-v1": "native-tc-operator-editorial-pg",
    "work-review-rollback-v1": "native-tc-work-review-rollback",
    "creator-portal-rollback-v1": "native-tc-creator-portal-rollback",
    "creator-offer-rollback-v1": "native-tc-creator-offer-rollback",
    "author-daily-gate-pg-v1": "native-tc-author-daily-gate-pg",
    "knowledge-schema-pg-v1": "native-tc-knowledge-schema-pg",
    "outreach-pain-library-pg-v1": "native-tc-outreach-pain-library-pg",
    "riderra-template-pg-v1": "native-tc-riderra-template-pg",
    "sales-room-proposal-race-pg-v1": "native-tc-sales-room-proposal-race-pg",
    "sales-room-deadlock-pg-v1": "native-tc-sales-room-deadlock-pg",
    "telegram-shared-audience-pg-v1": "native-tc-telegram-shared-audience-pg",
    "web-tracking-pg-v1": "native-tc-web-tracking-pg",
    "worker-captcha-pg-v1": "native-tc-worker-captcha-pg",
    "worker-expired-pg-v1": "native-tc-worker-expired-pg",
    "worker-resume-pg-v1": "native-tc-worker-resume-pg",
    "finance-import-transaction-pg-v1": "native-tc-finance-import-transaction-pg",
    "service-compression-race-pg-v1": "native-tc-service-compression-race-pg",
    "callback-recovery-pg-v1": "native-tc-callback-recovery-pg",
}
PROFILE_JOURNAL_ALIASES = {
    "callback-recovery-pg-v1": ("native-tc-google-oauth-current-access-pg",),
}
PARENT_DATABASE_PROFILES = frozenset({"client-info-v1", "capabilities-phase1-v1"})
OPERATOR_VOICE_TEST_DSN_PROFILES = frozenset({"operator-service-creation-v1", "operator-voice-pg-v1", "operator-editorial-pg-v1"})
CALLBACK_RECOVERY_DSN_PROFILES = frozenset({"callback-recovery-pg-v1"})
OWNED_DATABASE_PATTERNS = {
    "work-review-rollback-v1": re.compile(r"work_review_rollback_[0-9a-f]{32}"),
    "creator-portal-rollback-v1": re.compile(r"creator_portal_rollback_[0-9a-f]{32}"),
    "creator-offer-rollback-v1": re.compile(r"creator_offer_rollback_[0-9a-f]{32}"),
    "finance-import-transaction-pg-v1": re.compile(r"localos_data_fin_01_[0-9a-f]{32}"),
    "service-compression-race-pg-v1": re.compile(r"service_compression_race_[0-9a-f]{32}"),
}
OWNED_CLEANUP_SQL_PATTERNS = {
    "work-review-rollback-v1": r"^work_review_rollback_[0-9a-f]{32}$",
    "creator-portal-rollback-v1": r"^creator_portal_rollback_[0-9a-f]{32}$",
    "creator-offer-rollback-v1": r"^creator_offer_rollback_[0-9a-f]{32}$",
    "finance-import-transaction-pg-v1": r"^localos_data_fin_01_[0-9a-f]{32}$",
    "service-compression-race-pg-v1": r"^service_compression_race_[0-9a-f]{32}$",
}
OWNED_CLEANUP_EVENTS = {
    "work-review-rollback-v1": "work_review_database_cleanup_checked",
    "creator-portal-rollback-v1": "creator_portal_database_cleanup_checked",
    "creator-offer-rollback-v1": "creator_offer_database_cleanup_checked",
    "finance-import-transaction-pg-v1": "finance_import_database_cleanup_checked",
    "service-compression-race-pg-v1": "service_compression_database_cleanup_checked",
}
OWNED_SCHEMA_CLEANUP_SQL_PATTERNS = {
    "operator-voice-pg-v1": r"^voice_[0-9a-f]{32}$",
    "operator-editorial-pg-v1": r"^voice_[0-9a-f]{32}$",
    "callback-recovery-pg-v1": r"^callback_recovery_[0-9a-f]{32}$",
}
OWNED_SCHEMA_CLEANUP_EVENTS = {
    "operator-voice-pg-v1": "operator_voice_schema_cleanup_checked",
    "operator-editorial-pg-v1": "operator_voice_schema_cleanup_checked",
    "callback-recovery-pg-v1": "callback_recovery_schema_cleanup_checked",
}
INHERITED_DATABASE_URL_REFUSAL_PROFILES = frozenset({
    "author-daily-gate-pg-v1", "knowledge-schema-pg-v1", "outreach-pain-library-pg-v1",
    "riderra-template-pg-v1", "sales-room-proposal-race-pg-v1", "sales-room-deadlock-pg-v1",
    "telegram-shared-audience-pg-v1", "web-tracking-pg-v1", "worker-captcha-pg-v1",
    "worker-expired-pg-v1", "worker-resume-pg-v1", "finance-import-transaction-pg-v1",
    "service-compression-race-pg-v1",
    "operator-voice-pg-v1",
    "operator-editorial-pg-v1",
    "callback-recovery-pg-v1",
})
_active = None
_callback_recovery_test_dsn = None
_relay = None
_started = False
_events = []
_original_stop = None
_session = ""
_journal = None
_database_url = None
_operator_voice_test_dsn = None
_callback_recovery_database = None
_callback_recovery_relay_port = None
_callback_recovery_database_created = False


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


def _callback_recovery_binding() -> tuple[str, int]:
    database = os.environ.get(PREFIX + "CALLBACK_RECOVERY_DATABASE", "")
    port = os.environ.get(PREFIX + "CALLBACK_RECOVERY_RELAY_PORT", "")
    if re.fullmatch(r"readiness_full_test_[a-z0-9]{32}", database) is None or not port.isdigit():
        deny("callback recovery binding is invalid")
    return database, int(port)


def _callback_recovery_physical_dsn(database: str, port: int) -> str:
    return f"postgresql://test:test@127.0.0.1:{port}/{database}"


def validate_dsn(parsed: dict[str, str]) -> str | None:
    database = parsed.get("dbname")
    profile = os.environ.get(PREFIX + "MODE", "")
    if profile in CALLBACK_RECOVERY_DSN_PROFILES:
        expected_database, relay_port = _callback_recovery_binding()
        if set(parsed) - {"host", "port", "dbname", "user", "password"}:
            deny("callback recovery DSN carries unsupported options")
        logical = (
            parsed.get("host") == "127.0.0.1"
            and parsed.get("port") == "35418"
            and database == expected_database
            and parsed.get("user") == "test"
            and parsed.get("password") == "test"
        )
        physical = (
            parsed.get("host") == "127.0.0.1"
            and parsed.get("port") == str(relay_port)
            and database == expected_database
            and parsed.get("user") == "test"
            and parsed.get("password") == "test"
        )
        if not logical and not physical:
            deny("callback recovery DSN is outside its generated test database")
        path = os.environ.get(PREFIX + "CAPABILITY", "")
        result = native_tc_relay_hflypi.validate_capability(Path(path), relay_port)
        if result.get("session_id") != os.environ.get("LOCALOS_HFLYPI_TESTCONTAINERS_SESSION_ID"):
            deny("capability session differs from parent Testcontainers session")
        physical_dsn = _callback_recovery_physical_dsn(expected_database, relay_port)
        if physical:
            if os.environ.get(PREFIX + "OWNER_PID") == str(os.getpid()) or os.environ.get(PREFIX + "CALLBACK_RECOVERY_MIGRATION_DSN") != physical_dsn:
                deny("physical callback recovery DSN is reserved for the guarded migration child")
            record("dsn_admitted", port=relay_port, database=database, container_id=result.get("container_id"), purpose="callback_migration")
            return physical_dsn
        record("dsn_admitted", port=relay_port, database=database, container_id=result.get("container_id"), purpose="callback_logical_rewrite")
        return physical_dsn
    allowed_database = database == "test"
    owned_pattern = OWNED_DATABASE_PATTERNS.get(profile)
    if owned_pattern is not None:
        allowed_database = database == "postgres" or isinstance(database, str) and owned_pattern.fullmatch(database) is not None
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
    return None


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


def bind_callback_recovery_test_dsn(port: int) -> None:
    global _callback_recovery_test_dsn, _callback_recovery_database, _callback_recovery_relay_port
    if os.environ.get(PREFIX + "MODE") not in CALLBACK_RECOVERY_DSN_PROFILES:
        return
    if os.environ.get(PREFIX + "OWNER_PID") != str(os.getpid()) or "LOCALOS_CALLBACK_RECOVERY_TEST_DATABASE_URL" in os.environ or _callback_recovery_test_dsn is not None:
        deny("refusing to replace callback recovery test DSN")
    database = "readiness_full_test_" + uuid.uuid4().hex
    if _callback_recovery_database is not None or _callback_recovery_relay_port is not None:
        deny("callback recovery database was already bound")
    _callback_recovery_database = database
    _callback_recovery_relay_port = port
    os.environ[PREFIX + "CALLBACK_RECOVERY_DATABASE"] = database
    os.environ[PREFIX + "CALLBACK_RECOVERY_RELAY_PORT"] = str(port)
    result = native_tc_relay_hflypi.validate_capability(Path(os.environ.get(PREFIX + "CAPABILITY", "")), port)
    if result.get("session_id") != os.environ.get("LOCALOS_HFLYPI_TESTCONTAINERS_SESSION_ID"):
        deny("callback recovery capability session differs from parent")
    record("dsn_admitted", port=port, database=database, container_id=result.get("container_id"), purpose="callback_binding")
    # The fixture validates this literal logical address. The guarded psycopg2
    # boundary rewrites it only after capability validation to the private relay.
    _callback_recovery_test_dsn = f"postgresql://test:test@127.0.0.1:35418/{database}"
    os.environ["LOCALOS_CALLBACK_RECOVERY_TEST_DATABASE_URL"] = _callback_recovery_test_dsn
    os.environ["LOCALOS_CALLBACK_RECOVERY_GUARD_SHA256"] = os.environ[PREFIX + "GUARD_SHA256"]
    record("callback_recovery_test_dsn_bound", logical_port=35418, relay_port=port, database=database)


def prepare_callback_recovery_database() -> str:
    """Create only this lifecycle's named database before its guarded migration."""
    global _callback_recovery_database_created
    if os.environ.get(PREFIX + "MODE") not in CALLBACK_RECOVERY_DSN_PROFILES or _active is None or _active._container is None:
        deny("callback recovery database preparation is outside the owned lifecycle")
    database, port = _callback_recovery_binding()
    if _callback_recovery_database != database or _callback_recovery_relay_port != port or _callback_recovery_database_created:
        deny("callback recovery database preparation identity differs")
    result = _active._container.exec_run(["psql", "-v", "ON_ERROR_STOP=1", "-U", "test", "-d", "postgres", "-c", f"CREATE DATABASE {database}"])
    output = result.output.decode().strip() if isinstance(result.output, bytes) else str(result.output).strip()
    if result.exit_code != 0 or "CREATE DATABASE" not in output:
        deny("owned callback recovery database creation failed")
    _callback_recovery_database_created = True
    physical_dsn = _callback_recovery_physical_dsn(database, port)
    record("callback_recovery_database_created", database=database, relay_port=port)
    return physical_dsn


def verify_callback_recovery_migration() -> None:
    if not _callback_recovery_database_created or _active is None or _active._container is None:
        deny("callback recovery migration verification is outside the owned lifecycle")
    database, _ = _callback_recovery_binding()
    result = _active._container.exec_run(["psql", "-v", "ON_ERROR_STOP=1", "-U", "test", "-d", database, "-At", "-c", "SELECT to_regclass('public.businesses'), to_regclass('public.action_callback_outbox'), to_regclass('public.action_callback_attempts')"])
    output = result.output.decode().strip() if isinstance(result.output, bytes) else str(result.output).strip()
    if result.exit_code != 0 or output != "businesses|action_callback_outbox|action_callback_attempts":
        deny("callback recovery migration did not create required public tables")
    record("callback_recovery_database_migrated", database=database)


def unbind_callback_recovery_test_dsn() -> None:
    global _callback_recovery_test_dsn, _callback_recovery_database, _callback_recovery_relay_port, _callback_recovery_database_created
    if _callback_recovery_test_dsn is None:
        return
    if os.environ.get("LOCALOS_CALLBACK_RECOVERY_TEST_DATABASE_URL") != _callback_recovery_test_dsn:
        deny("callback recovery test DSN changed during test")
    del os.environ["LOCALOS_CALLBACK_RECOVERY_TEST_DATABASE_URL"]
    del os.environ["LOCALOS_CALLBACK_RECOVERY_GUARD_SHA256"]
    os.environ.pop(PREFIX + "CALLBACK_RECOVERY_DATABASE", None)
    os.environ.pop(PREFIX + "CALLBACK_RECOVERY_RELAY_PORT", None)
    os.environ.pop(PREFIX + "CALLBACK_RECOVERY_MIGRATION_DSN", None)
    _callback_recovery_test_dsn = None
    _callback_recovery_database = None
    _callback_recovery_relay_port = None
    _callback_recovery_database_created = False
    record("callback_recovery_test_dsn_unbound")


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
    journal_prefixes = (journal_prefix, *PROFILE_JOURNAL_ALIASES.get(profile, ()))
    if _journal.parent != EVIDENCE or not any(re.fullmatch(re.escape(prefix) + r"-v[1-9][0-9]*-events.jsonl", _journal.name) for prefix in journal_prefixes) or _journal.is_symlink():
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
        if profile in INHERITED_DATABASE_URL_REFUSAL_PROFILES and "DATABASE_URL" in os.environ:
            deny("inherited database configuration must be absent before owned start")
        if profile in OPERATOR_VOICE_TEST_DSN_PROFILES and "OPERATOR_VOICE_TEST_DSN" in os.environ:
            deny("operator voice test DSN must be absent before owned start")
        if profile in CALLBACK_RECOVERY_DSN_PROFILES and (
            "LOCALOS_CALLBACK_RECOVERY_TEST_DATABASE_URL" in os.environ
            or "LOCALOS_CALLBACK_RECOVERY_GUARD_SHA256" in os.environ
            or "DATABASE_URL" in os.environ
            or PREFIX + "CALLBACK_RECOVERY_DATABASE" in os.environ
            or PREFIX + "CALLBACK_RECOVERY_RELAY_PORT" in os.environ
            or PREFIX + "CALLBACK_RECOVERY_MIGRATION_DSN" in os.environ
        ):
            deny("callback recovery configuration must be absent before owned start")
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
        bind_callback_recovery_test_dsn(port)
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
        cleanup_pattern = OWNED_CLEANUP_SQL_PATTERNS.get(profile)
        cleanup_event = OWNED_CLEANUP_EVENTS.get(profile)
        if cleanup_pattern is not None and cleanup_event is not None and instance._container is not None:
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
                        f"SELECT COUNT(*) FROM pg_database WHERE datname ~ '{cleanup_pattern}'",
                    ]
                )
                output = result.output.decode().strip() if isinstance(result.output, bytes) else str(result.output).strip()
                if result.exit_code != 0 or output != "0":
                    deny("owned disposable database remains before container cleanup")
                record(cleanup_event, remaining=0)
            except BaseException:
                failures.append(type(sys.exception()).__name__)
        schema_cleanup_pattern = OWNED_SCHEMA_CLEANUP_SQL_PATTERNS.get(profile)
        schema_cleanup_event = OWNED_SCHEMA_CLEANUP_EVENTS.get(profile)
        if schema_cleanup_pattern is not None and schema_cleanup_event is not None and instance._container is not None:
            try:
                if profile in CALLBACK_RECOVERY_DSN_PROFILES and not _callback_recovery_database_created:
                    record(schema_cleanup_event, remaining=0, database=_callback_recovery_binding()[0], created=False)
                    schema_database = None
                else:
                    schema_database = _callback_recovery_binding()[0] if profile in CALLBACK_RECOVERY_DSN_PROFILES else "test"
                if schema_database is None:
                    raise StopIteration
                result = instance._container.exec_run(
                    [
                        "psql",
                        "-U",
                        "test",
                        "-d",
                        schema_database,
                        "-At",
                        "-c",
                        f"SELECT COUNT(*) FROM pg_namespace WHERE nspname ~ '{schema_cleanup_pattern}'",
                    ]
                )
                output = result.output.decode().strip() if isinstance(result.output, bytes) else str(result.output).strip()
                if result.exit_code != 0 or output != "0":
                    deny("owned disposable schema remains before container cleanup")
                record(schema_cleanup_event, remaining=0)
            except StopIteration:
                pass
            except BaseException:
                failures.append(type(sys.exception()).__name__)
        if profile in CALLBACK_RECOVERY_DSN_PROFILES and instance._container is not None:
            try:
                database, _ = _callback_recovery_binding()
                if not _callback_recovery_database_created:
                    remaining = instance._container.exec_run(["psql", "-v", "ON_ERROR_STOP=1", "-U", "test", "-d", "postgres", "-At", "-c", f"SELECT COUNT(*) FROM pg_database WHERE datname = '{database}'"])
                    output = remaining.output.decode().strip() if isinstance(remaining.output, bytes) else str(remaining.output).strip()
                    if remaining.exit_code != 0 or output != "0":
                        deny("uncreated callback recovery database unexpectedly exists")
                    record("callback_recovery_database_cleanup_checked", database=database, remaining=0, created=False)
                    raise StopIteration
                terminate = instance._container.exec_run(["psql", "-v", "ON_ERROR_STOP=1", "-U", "test", "-d", "postgres", "-c", f"SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname = '{database}' AND pid <> pg_backend_pid()"])
                drop = instance._container.exec_run(["psql", "-v", "ON_ERROR_STOP=1", "-U", "test", "-d", "postgres", "-c", f"DROP DATABASE {database}"])
                remaining = instance._container.exec_run(["psql", "-v", "ON_ERROR_STOP=1", "-U", "test", "-d", "postgres", "-At", "-c", f"SELECT COUNT(*) FROM pg_database WHERE datname = '{database}'"])
                output = remaining.output.decode().strip() if isinstance(remaining.output, bytes) else str(remaining.output).strip()
                if terminate.exit_code != 0 or drop.exit_code != 0 or remaining.exit_code != 0 or output != "0":
                    deny("owned callback recovery database remains before container cleanup")
                record("callback_recovery_database_cleanup_checked", database=database, remaining=0)
            except StopIteration:
                pass
            except BaseException:
                failures.append(type(sys.exception()).__name__)
        try:
            unbind_callback_recovery_test_dsn()
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
