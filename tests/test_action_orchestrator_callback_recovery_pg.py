"""Native PostgreSQL regression for callback outbox interrupted-claim recovery.

This proof deliberately models a process interruption after the durable
``pending -> sending`` claim and before the callback result is persisted.  An
unknown delivery result must not be resent automatically: it belongs in the
existing manual DLQ reconciliation path.
"""

import hashlib
import os
import re
import sys
import uuid
from pathlib import Path
from urllib.parse import urlsplit

import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
import pytest

from core import action_orchestrator
from core.action_orchestrator import ActionOrchestrator


TEST_DSN_ENV = "LOCALOS_CALLBACK_RECOVERY_TEST_DATABASE_URL"
GUARD_ENV = "LOCALOS_CALLBACK_RECOVERY_GUARD_SHA256"
TABLES = ("businesses", "action_callback_outbox", "action_callback_attempts")
INTERRUPTED_CLAIM_ERROR = "callback_delivery_uncertain_after_interrupted_claim"


def isolated_test_dsn() -> str:
    database_url = os.getenv(TEST_DSN_ENV, "")
    if not database_url:
        pytest.skip(f"{TEST_DSN_ENV} is required for native callback recovery proof")
    if any(os.getenv(key) for key in ("PGHOSTADDR", "PGSERVICE", "PGSERVICEFILE", "PGOPTIONS")):
        raise RuntimeError("native callback recovery proof refuses inherited libpq overrides")
    parsed = urlsplit(database_url)
    if (
        parsed.scheme not in {"postgresql", "postgres"}
        or parsed.hostname not in {"127.0.0.1", "::1"}
        or parsed.port != 35418
        or not re.fullmatch(r"/readiness_full_test_[a-z0-9_]+", parsed.path)
        or parsed.query
        or parsed.fragment
    ):
        raise RuntimeError("native callback recovery proof requires a migrated owned loopback readiness database")
    pythonpath = os.getenv("PYTHONPATH", "")
    guard_directory = pythonpath.split(os.pathsep)[0] if pythonpath else ""
    guard_path = Path(guard_directory) / "sitecustomize.py"
    loaded_guard = sys.modules.get("sitecustomize")
    expected_hash = os.getenv(GUARD_ENV, "")
    if (
        not guard_path.is_file()
        or loaded_guard is None
        or Path(str(getattr(loaded_guard, "__file__", ""))).resolve() != guard_path.resolve()
        or not re.fullmatch(r"[0-9a-f]{64}", expected_hash)
        or hashlib.sha256(guard_path.read_bytes()).hexdigest() != expected_hash
    ):
        raise RuntimeError("native callback recovery proof requires pinned guard-first sitecustomize")
    return database_url


class ScopedDatabaseManager:
    def __init__(self, database_url: str, schema: str):
        self.conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        cursor = self.conn.cursor()
        try:
            cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
            self.conn.commit()
        finally:
            cursor.close()

    def close(self):
        self.conn.close()


def _schema_identity(cursor, schema: str):
    cursor.execute(
        "SELECT oid, pg_get_userbyid(nspowner) AS owner FROM pg_namespace WHERE nspname = %s",
        (schema,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return (int(row["oid"]), str(row["owner"]))


@pytest.fixture
def callback_recovery_database():
    database_url = isolated_test_dsn()
    schema = "callback_recovery_" + uuid.uuid4().hex
    connection = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    identity = None
    try:
        if _schema_identity(cursor, schema):
            raise RuntimeError("fresh callback recovery schema unexpectedly already exists")
        cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        identity = _schema_identity(cursor, schema)
        cursor.execute("SELECT current_user AS owner")
        expected_owner = str(cursor.fetchone()["owner"])
        if not identity or identity[1] != expected_owner:
            raise RuntimeError("callback recovery schema identity was not created for the current test owner")
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        for table_name in TABLES:
            cursor.execute(
                sql.SQL("CREATE TABLE {} (LIKE public.{} INCLUDING ALL)").format(
                    sql.Identifier(table_name),
                    sql.Identifier(table_name),
                )
            )
        ids = {key: str(uuid.uuid4()) for key in ("tenant", "foreign_tenant", "action", "foreign_action")}
        for tenant_key, action_key, name in (
            ("tenant", "action", "Callback recovery tenant"),
            ("foreign_tenant", "foreign_action", "Foreign callback tenant"),
        ):
            cursor.execute(
                "INSERT INTO businesses (id, owner_id, name, is_active) VALUES (%s, %s, %s, TRUE)",
                (ids[tenant_key], ids[tenant_key], name),
            )
        connection.commit()
        yield {"database_url": database_url, "schema": schema, "ids": ids}
    finally:
        try:
            connection.rollback()
            if identity and _schema_identity(cursor, schema) == identity:
                cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
                connection.commit()
            elif identity:
                raise RuntimeError("refusing callback recovery schema cleanup after identity changed")
        finally:
            cursor.close()
            connection.close()


def _database_factory(fixture):
    return ScopedDatabaseManager(fixture["database_url"], fixture["schema"])


def _query_one(fixture, statement, params=()):
    connection = psycopg2.connect(fixture["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(fixture["schema"])))
        cursor.execute(statement, params)
        return dict(cursor.fetchone())
    finally:
        cursor.close()
        connection.close()


def _query_all(fixture, statement, params=()):
    connection = psycopg2.connect(fixture["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(fixture["schema"])))
        cursor.execute(statement, params)
        return [dict(row) for row in cursor.fetchall()]
    finally:
        cursor.close()
        connection.close()


def _insert_outbox(fixture, *, tenant_key: str, action_key: str, status: str = "pending", max_attempts: int = 5) -> str:
    outbox_id = str(uuid.uuid4())
    ids = fixture["ids"]
    connection = psycopg2.connect(fixture["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(fixture["schema"])))
        cursor.execute(
            """
            INSERT INTO action_callback_outbox
                (id, action_id, tenant_id, callback_url, event_type, payload_json, status,
                 attempts, max_attempts, next_attempt_at, locked_at, dedupe_key)
            VALUES (%s, %s, %s, 'https://callbacks.example.test/localos', 'completed',
                    '{"status":"completed"}'::jsonb, %s, 0, %s, CURRENT_TIMESTAMP,
                    CASE WHEN %s = 'sending' THEN CURRENT_TIMESTAMP ELSE NULL END, %s)
            """,
            (outbox_id, ids[action_key], ids[tenant_key], status, max_attempts, status, f"{outbox_id}:completed"),
        )
        connection.commit()
        return outbox_id
    finally:
        cursor.close()
        connection.close()


def _age_claim(fixture, outbox_id: str):
    connection = psycopg2.connect(fixture["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(fixture["schema"])))
        cursor.execute(
            "UPDATE action_callback_outbox SET locked_at = CURRENT_TIMESTAMP - INTERVAL '2 hours' WHERE id = %s",
            (outbox_id,),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _age_created_at(fixture, outbox_id: str):
    connection = psycopg2.connect(fixture["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(fixture["schema"])))
        cursor.execute(
            "UPDATE action_callback_outbox SET created_at = CURRENT_TIMESTAMP - INTERVAL '2 days' WHERE id = %s",
            (outbox_id,),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _mark_interrupted_dlq(fixture, outbox_id: str):
    connection = psycopg2.connect(fixture["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(fixture["schema"])))
        cursor.execute(
            """
            UPDATE action_callback_outbox
            SET status = 'dlq',
                last_error = %s,
                locked_at = NULL,
                created_at = CURRENT_TIMESTAMP - INTERVAL '2 days'
            WHERE id = %s
            """,
            (INTERRUPTED_CLAIM_ERROR, outbox_id),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _defer_next_attempt(fixture, outbox_id: str):
    connection = psycopg2.connect(fixture["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(fixture["schema"])))
        cursor.execute(
            "UPDATE action_callback_outbox SET next_attempt_at = CURRENT_TIMESTAMP + INTERVAL '1 hour' WHERE id = %s",
            (outbox_id,),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _replace_with_newer_sending_claim(fixture, outbox_id: str):
    connection = psycopg2.connect(fixture["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(fixture["schema"])))
        cursor.execute(
            """
            UPDATE action_callback_outbox
            SET status = 'sending',
                locked_at = CURRENT_TIMESTAMP + INTERVAL '1 minute',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (outbox_id,),
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _make_orchestrator(monkeypatch, fixture, transport):
    monkeypatch.setattr(action_orchestrator, "DatabaseManager", lambda: _database_factory(fixture))
    monkeypatch.setattr(action_orchestrator, "public_pinned_post", transport)
    orchestrator = ActionOrchestrator({})
    monkeypatch.setattr(orchestrator, "ensure_tables", lambda _cursor: None)
    monkeypatch.setattr(orchestrator, "_validate_callback_url", lambda callback_url: callback_url)
    return orchestrator


def _worker_connection(fixture):
    connection = psycopg2.connect(fixture["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(fixture["schema"])))
        connection.commit()
    finally:
        cursor.close()
    return connection


def test_interrupted_stale_sending_claim_is_quarantined_without_resend_or_cross_tenant_effect(
    callback_recovery_database, monkeypatch,
):
    fixture = callback_recovery_database
    interrupted_outbox_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action")
    fresh_outbox_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action", status="sending")
    foreign_outbox_id = _insert_outbox(fixture, tenant_key="foreign_tenant", action_key="foreign_action", status="sending")
    _age_claim(fixture, foreign_outbox_id)
    calls = []

    def interrupted_transport(*args, **kwargs):
        calls.append((args, kwargs))
        raise BaseException("synthetic process interruption after durable callback claim")

    orchestrator = _make_orchestrator(monkeypatch, fixture, interrupted_transport)
    with pytest.raises(BaseException, match="synthetic process interruption"):
        orchestrator.dispatch_callback_outbox(batch_size=1, tenant_id=fixture["ids"]["tenant"])

    claimed = _query_one(
        fixture,
        "SELECT status, attempts, locked_at FROM action_callback_outbox WHERE id = %s",
        (interrupted_outbox_id,),
    )
    assert claimed["status"] == "sending"
    assert claimed["attempts"] == 0
    assert claimed["locked_at"] is not None
    assert _query_all(fixture, "SELECT id FROM action_callback_attempts WHERE outbox_id = %s", (interrupted_outbox_id,)) == []
    _age_claim(fixture, interrupted_outbox_id)

    calls.clear()
    result = orchestrator.dispatch_callback_outbox(batch_size=10, tenant_id=fixture["ids"]["tenant"])

    recovered = _query_one(
        fixture,
        "SELECT status, attempts, last_error, locked_at FROM action_callback_outbox WHERE id = %s",
        (interrupted_outbox_id,),
    )
    assert result["success"] is True
    assert recovered == {
        "status": "dlq",
        "attempts": 0,
        "last_error": INTERRUPTED_CLAIM_ERROR,
        "locked_at": None,
    }
    assert calls == []
    assert _query_all(fixture, "SELECT id FROM action_callback_attempts WHERE outbox_id = %s", (interrupted_outbox_id,)) == []
    assert _query_one(
        fixture,
        "SELECT status, attempts, locked_at FROM action_callback_outbox WHERE id = %s",
        (fresh_outbox_id,),
    )["status"] == "sending"
    assert _query_one(
        fixture,
        "SELECT status, attempts, locked_at FROM action_callback_outbox WHERE id = %s",
        (foreign_outbox_id,),
    )["status"] == "sending"


def test_stale_claim_quarantine_respects_batch_bound(callback_recovery_database, monkeypatch):
    fixture = callback_recovery_database
    first_outbox_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action", status="sending")
    second_outbox_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action", status="sending")
    _age_claim(fixture, first_outbox_id)
    _age_claim(fixture, second_outbox_id)
    network_calls = []
    orchestrator = _make_orchestrator(
        monkeypatch,
        fixture,
        lambda *_args, **_kwargs: network_calls.append(True),
    )

    result = orchestrator.dispatch_callback_outbox(batch_size=1, tenant_id=fixture["ids"]["tenant"])

    assert result == {"success": True, "picked": 0, "sent": 0, "retried": 0, "dlq": 0, "tenant_id": fixture["ids"]["tenant"]}
    rows = _query_all(
        fixture,
        "SELECT id, status, attempts, last_error, locked_at FROM action_callback_outbox ORDER BY id",
    )
    assert len(rows) == 2
    quarantined = [row for row in rows if row["status"] == "dlq"]
    retained = [row for row in rows if row["status"] == "sending"]
    assert len(quarantined) == 1
    assert quarantined[0]["attempts"] == 0
    assert quarantined[0]["last_error"] == INTERRUPTED_CLAIM_ERROR
    assert quarantined[0]["locked_at"] is None
    assert len(retained) == 1
    assert retained[0]["attempts"] == 0
    assert retained[0]["last_error"] is None
    assert retained[0]["locked_at"] is not None
    assert network_calls == []


def test_callback_503_retry_then_sent_keeps_normal_attempt_ledger(callback_recovery_database, monkeypatch):
    fixture = callback_recovery_database
    outbox_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action")
    responses = [(503, "temporarily unavailable"), (200, "accepted")]
    headers_seen = []

    class Response:
        def __init__(self, status_code, text):
            self.status_code = status_code
            self.text = text

    def controlled_transport(_url, _body, headers, **_kwargs):
        headers_seen.append({
            "event_id": headers["X-LocalOS-Event-Id"],
            "dedupe_key": headers["X-LocalOS-Dedupe-Key"],
        })
        return Response(*responses.pop(0))

    orchestrator = _make_orchestrator(monkeypatch, fixture, controlled_transport)
    first = orchestrator.dispatch_callback_outbox(batch_size=1, tenant_id=fixture["ids"]["tenant"])
    assert first == {"success": True, "picked": 1, "sent": 0, "retried": 1, "dlq": 0, "tenant_id": fixture["ids"]["tenant"]}
    assert _query_one(
        fixture,
        "SELECT status, attempts, locked_at FROM action_callback_outbox WHERE id = %s",
        (outbox_id,),
    ) == {"status": "retry", "attempts": 1, "locked_at": None}

    connection = psycopg2.connect(fixture["database_url"], cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(fixture["schema"])))
        cursor.execute("UPDATE action_callback_outbox SET next_attempt_at = CURRENT_TIMESTAMP WHERE id = %s", (outbox_id,))
        connection.commit()
    finally:
        cursor.close()
        connection.close()

    second = orchestrator.dispatch_callback_outbox(batch_size=1, tenant_id=fixture["ids"]["tenant"])
    assert second == {"success": True, "picked": 1, "sent": 1, "retried": 0, "dlq": 0, "tenant_id": fixture["ids"]["tenant"]}
    assert _query_one(
        fixture,
        "SELECT status, attempts, locked_at, sent_at FROM action_callback_outbox WHERE id = %s",
        (outbox_id,),
    )["status"] == "sent"
    assert _query_all(
        fixture,
        "SELECT attempt_no, success, http_status, error_text FROM action_callback_attempts WHERE outbox_id = %s ORDER BY attempt_no",
        (outbox_id,),
    ) == [
        {"attempt_no": 1, "success": False, "http_status": 503, "error_text": "http_503"},
        {"attempt_no": 2, "success": True, "http_status": 200, "error_text": None},
    ]
    assert headers_seen == [
        {"event_id": outbox_id, "dedupe_key": f"{outbox_id}:completed"},
        {"event_id": outbox_id, "dedupe_key": f"{outbox_id}:completed"},
    ]


def test_old_uncertain_delivery_and_stuck_sending_remain_visible_in_metrics(callback_recovery_database, monkeypatch):
    fixture = callback_recovery_database
    stale_sending_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action", status="sending")
    uncertain_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action", status="sending")
    _age_claim(fixture, stale_sending_id)
    _age_created_at(fixture, stale_sending_id)
    _mark_interrupted_dlq(fixture, uncertain_id)
    orchestrator = _make_orchestrator(monkeypatch, fixture, lambda *_args, **_kwargs: None)

    metrics = orchestrator.get_callback_metrics(
        {"user_id": fixture["ids"]["tenant"]},
        tenant_id=fixture["ids"]["tenant"],
        window_minutes=60,
    )

    assert metrics["metrics"]["sending"] == 0
    assert metrics["metrics"]["dlq"] == 0
    assert metrics["metrics"]["stuck_sending"] == 1
    assert metrics["metrics"]["uncertain_delivery"] == 1
    assert {alert["code"] for alert in metrics["alerts"]} >= {"STUCK_SENDING", "UNCERTAIN_DELIVERY"}


def test_callback_replay_is_owner_scoped_and_foreign_dlq_is_unchanged(callback_recovery_database, monkeypatch):
    fixture = callback_recovery_database
    owned_outbox_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action", status="dlq")
    foreign_outbox_id = _insert_outbox(fixture, tenant_key="foreign_tenant", action_key="foreign_action", status="dlq")
    orchestrator = _make_orchestrator(monkeypatch, fixture, lambda *_args, **_kwargs: None)

    denied = orchestrator.replay_callback_outbox(
        {"user_id": fixture["ids"]["tenant"]},
        tenant_id=fixture["ids"]["foreign_tenant"],
    )
    assert denied == {"success": False, "error": "forbidden", "http_code": 403}
    assert _query_one(
        fixture,
        "SELECT status FROM action_callback_outbox WHERE id = %s",
        (foreign_outbox_id,),
    ) == {"status": "dlq"}

    replayed = orchestrator.replay_callback_outbox(
        {"user_id": fixture["ids"]["tenant"]},
        tenant_id=fixture["ids"]["tenant"],
    )
    assert replayed["success"] is True
    assert replayed["replayed_count"] == 1
    assert replayed["replayed"][0]["id"] == owned_outbox_id
    assert _query_one(
        fixture,
        "SELECT status, attempts, locked_at FROM action_callback_outbox WHERE id = %s",
        (owned_outbox_id,),
    ) == {"status": "pending", "attempts": 0, "locked_at": None}


def test_callback_max_attempt_is_dlq_and_batch_size_keeps_fresh_claim(callback_recovery_database, monkeypatch):
    fixture = callback_recovery_database
    max_attempt_outbox_id = _insert_outbox(
        fixture,
        tenant_key="tenant",
        action_key="action",
        max_attempts=1,
    )
    second_pending_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action")
    fresh_claim_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action", status="sending")
    _defer_next_attempt(fixture, second_pending_id)

    class Response:
        status_code = 503
        text = "temporarily unavailable"

    transport_calls = []

    def always_503(*_args, **_kwargs):
        transport_calls.append(True)
        return Response()

    orchestrator = _make_orchestrator(monkeypatch, fixture, always_503)
    result = orchestrator.dispatch_callback_outbox(batch_size=0, tenant_id=fixture["ids"]["tenant"])

    assert result == {"success": True, "picked": 1, "sent": 0, "retried": 0, "dlq": 1, "tenant_id": fixture["ids"]["tenant"]}
    assert len(transport_calls) == 1
    assert _query_one(
        fixture,
        "SELECT status, attempts, locked_at FROM action_callback_outbox WHERE id = %s",
        (max_attempt_outbox_id,),
    ) == {"status": "dlq", "attempts": 1, "locked_at": None}
    assert _query_one(
        fixture,
        "SELECT status FROM action_callback_outbox WHERE id = %s",
        (second_pending_id,),
    ) == {"status": "pending"}
    assert _query_one(
        fixture,
        "SELECT status, attempts, locked_at FROM action_callback_outbox WHERE id = %s",
        (fresh_claim_id,),
    )["status"] == "sending"


def test_late_transport_result_cannot_overwrite_quarantined_claim(callback_recovery_database, monkeypatch):
    fixture = callback_recovery_database
    outbox_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action")

    class Response:
        status_code = 200
        text = "accepted"

    def quarantine_during_transport(*_args, **_kwargs):
        _mark_interrupted_dlq(fixture, outbox_id)
        return Response()

    orchestrator = _make_orchestrator(monkeypatch, fixture, quarantine_during_transport)
    result = orchestrator.dispatch_callback_outbox(batch_size=1, tenant_id=fixture["ids"]["tenant"])

    assert result == {"success": True, "picked": 1, "sent": 0, "retried": 0, "dlq": 0, "tenant_id": fixture["ids"]["tenant"]}
    assert _query_one(
        fixture,
        "SELECT status, attempts, last_error, locked_at FROM action_callback_outbox WHERE id = %s",
        (outbox_id,),
    ) == {
        "status": "dlq",
        "attempts": 0,
        "last_error": INTERRUPTED_CLAIM_ERROR,
        "locked_at": None,
    }
    assert _query_all(fixture, "SELECT id FROM action_callback_attempts WHERE outbox_id = %s", (outbox_id,)) == []


def test_late_finalizer_cannot_overwrite_newer_sending_claim(callback_recovery_database, monkeypatch):
    fixture = callback_recovery_database
    outbox_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action")

    class Response:
        status_code = 200
        text = "accepted"

    def replace_claim_during_transport(*_args, **_kwargs):
        _replace_with_newer_sending_claim(fixture, outbox_id)
        return Response()

    orchestrator = _make_orchestrator(monkeypatch, fixture, replace_claim_during_transport)
    result = orchestrator.dispatch_callback_outbox(batch_size=1, tenant_id=fixture["ids"]["tenant"])

    assert result == {"success": True, "picked": 1, "sent": 0, "retried": 0, "dlq": 0, "tenant_id": fixture["ids"]["tenant"]}
    replacement = _query_one(
        fixture,
        "SELECT status, attempts, last_error, locked_at FROM action_callback_outbox WHERE id = %s",
        (outbox_id,),
    )
    assert replacement["status"] == "sending"
    assert replacement["attempts"] == 0
    assert replacement["last_error"] is None
    assert replacement["locked_at"] is not None
    assert _query_all(fixture, "SELECT id FROM action_callback_attempts WHERE outbox_id = %s", (outbox_id,)) == []


def test_second_cached_batch_claim_is_not_sent_after_it_is_quarantined(callback_recovery_database, monkeypatch):
    fixture = callback_recovery_database
    first_outbox_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action")
    second_outbox_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action")
    _age_created_at(fixture, first_outbox_id)
    network_calls = []

    class Response:
        status_code = 200
        text = "accepted"

    def quarantine_second_claim(_url, _body, headers, **_kwargs):
        network_calls.append(headers["X-LocalOS-Event-Id"])
        _mark_interrupted_dlq(fixture, second_outbox_id)
        return Response()

    orchestrator = _make_orchestrator(monkeypatch, fixture, quarantine_second_claim)
    result = orchestrator.dispatch_callback_outbox(batch_size=2, tenant_id=fixture["ids"]["tenant"])

    assert result == {"success": True, "picked": 2, "sent": 1, "retried": 0, "dlq": 0, "tenant_id": fixture["ids"]["tenant"]}
    assert network_calls == [first_outbox_id]
    assert _query_one(
        fixture,
        "SELECT status, attempts, last_error, locked_at FROM action_callback_outbox WHERE id = %s",
        (second_outbox_id,),
    ) == {
        "status": "dlq",
        "attempts": 0,
        "last_error": INTERRUPTED_CLAIM_ERROR,
        "locked_at": None,
    }
    assert _query_all(fixture, "SELECT id FROM action_callback_attempts WHERE outbox_id = %s", (second_outbox_id,)) == []


def test_worker_alert_scan_includes_old_uncertain_claims_and_incident_actions(callback_recovery_database, monkeypatch):
    fixture = callback_recovery_database
    stale_sending_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action", status="sending")
    uncertain_id = _insert_outbox(fixture, tenant_key="tenant", action_key="action", status="sending")
    _age_claim(fixture, stale_sending_id)
    _age_created_at(fixture, stale_sending_id)
    _mark_interrupted_dlq(fixture, uncertain_id)

    import worker

    notified = []

    class AlertingOrchestrator:
        def get_callback_metrics(self, _user_data, *, tenant_id, window_minutes):
            assert tenant_id == fixture["ids"]["tenant"]
            assert window_minutes == 60
            return {
                "success": True,
                "metrics": {"dlq": 0, "stuck_retry": 0, "uncertain_delivery": 1},
                "alerts": [{"code": "UNCERTAIN_DELIVERY", "severity": "high"}],
            }

    monkeypatch.setattr(worker, "get_db_connection", lambda: _worker_connection(fixture))
    monkeypatch.setattr(worker, "CALLBACK_DISPATCH_ORCHESTRATOR", AlertingOrchestrator())
    monkeypatch.setattr(
        worker,
        "_notify_superadmins_callback_alerts",
        lambda tenant_id, **kwargs: notified.append((tenant_id, kwargs)),
    )
    monkeypatch.setattr(worker, "_LAST_CALLBACK_ALERT_SCAN_AT", 0.0)
    monkeypatch.setattr(worker.time, "time", lambda: 1000.0)
    monkeypatch.setenv("OPENCLAW_CALLBACK_ALERT_NOTIFY_ENABLED", "true")
    monkeypatch.setenv("OPENCLAW_CALLBACK_ALERT_NOTIFY_WINDOW_MINUTES", "60")
    monkeypatch.setenv("OPENCLAW_CALLBACK_ALERT_SCAN_INTERVAL_SEC", "30")

    worker._check_openclaw_callback_alerts_if_due()

    assert [item[0] for item in notified] == [fixture["ids"]["tenant"]]
    assert worker._load_problematic_action_ids_for_tenant(fixture["ids"]["tenant"], limit=5) == [
        fixture["ids"]["action"],
        fixture["ids"]["action"],
    ]
