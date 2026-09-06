"""PostgreSQL proof for the durable agent-run admission boundary."""
import os
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from core.auth_context import AuthContext
from services.agent_run_admission import AgentRunAdmissionService


@pytest.fixture
def admission_db(monkeypatch):
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires isolated PostgreSQL")
    first = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    second = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_agent_admission_" + uuid.uuid4().hex
    setup = first.cursor()
    setup.execute(f'CREATE SCHEMA "{schema}"')
    setup.execute(f'SET search_path TO "{schema}"')
    second.cursor().execute(f'SET search_path TO "{schema}"')
    setup.execute("""CREATE TABLE businesses(
        id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, network_id TEXT, is_active BOOLEAN
    )""")
    setup.execute("""CREATE TABLE business_members(
        business_id TEXT, user_id TEXT, status TEXT
    )""")
    setup.execute("""CREATE TABLE network_members(
        network_id TEXT, user_id TEXT, status TEXT
    )""")
    setup.execute("CREATE TABLE networks(id TEXT PRIMARY KEY, owner_id TEXT)")
    setup.execute("""CREATE TABLE agent_blueprints(
        id TEXT PRIMARY KEY, business_id TEXT NOT NULL, status TEXT NOT NULL,
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb
    )""")
    setup.execute("""CREATE TABLE agent_blueprint_versions(
        id TEXT PRIMARY KEY, blueprint_id TEXT NOT NULL, execution_mode TEXT,
        compiled_state TEXT, required_integration_bindings_json JSONB
    )""")
    setup.execute("""CREATE TABLE agent_runs(
        id TEXT PRIMARY KEY, blueprint_id TEXT NOT NULL, blueprint_version_id TEXT NOT NULL,
        business_id TEXT NOT NULL, status TEXT NOT NULL, input_json JSONB NOT NULL,
        output_json JSONB NOT NULL, created_by_user_id TEXT NOT NULL,
        idempotency_key TEXT NOT NULL, queued_at TIMESTAMPTZ, started_at TIMESTAMPTZ,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        attempt_count INTEGER NOT NULL, max_attempts INTEGER NOT NULL,
        billing_reservation_id TEXT, input_snapshot_id TEXT, input_snapshot_hash TEXT
    )""")
    setup.execute("""CREATE TABLE agent_artifacts(
        id TEXT PRIMARY KEY, run_id TEXT NOT NULL, step_id TEXT, artifact_type TEXT NOT NULL,
        title TEXT NOT NULL, payload_json JSONB NOT NULL
    )""")
    setup.execute("CREATE TABLE test_credit_reservations(id TEXT PRIMARY KEY, run_id TEXT NOT NULL)")
    setup.execute("INSERT INTO businesses(id,owner_id,is_active) VALUES ('biz','owner',TRUE)")
    setup.execute("INSERT INTO business_members(business_id,user_id,status) VALUES ('biz','user','active')")
    setup.execute("""INSERT INTO agent_blueprints(id,business_id,status,metadata_json)
        VALUES ('bp','biz','active','{"active_version_id":"v1","execution_mode":"manual"}'::jsonb)""")
    setup.execute("INSERT INTO agent_blueprint_versions(id,blueprint_id,execution_mode,compiled_state) VALUES ('v1','bp','manual','legacy')")
    first.commit()

    from services import agent_run_queue

    class Runner:
        def __init__(self, cursor):
            self.cursor = cursor

        def _supersede_pending_runs(self, _blueprint_id):
            return None

        def load_run(self, run_id, _user_data=None):
            self.cursor.execute("SELECT * FROM agent_runs WHERE id=%s", (run_id,))
            row = self.cursor.fetchone()
            return dict(row) if row else None

    def reserve(cursor, *, run_id, **_kwargs):
        reservation_id = "reservation-" + run_id
        cursor.execute(
            "INSERT INTO test_credit_reservations(id,run_id) VALUES (%s,%s)",
            (reservation_id, run_id),
        )
        return {"status": "reserved", "reservation_id": reservation_id, "reserved_credits": 2}

    monkeypatch.setattr(agent_run_queue, "AgentBlueprintRunner", Runner)
    monkeypatch.setattr(agent_run_queue, "reserve_agent_run_credits", reserve)
    monkeypatch.setattr(
        agent_run_queue,
        "build_agent_integration_preflight",
        lambda *_args, **_kwargs: {"ready": True, "items": []},
    )

    class Database:
        def __init__(self):
            self.conn = first

        def rollback_and_close(self):
            self.conn.rollback()

    try:
        yield first, second, Database
    finally:
        second.rollback()
        first.rollback()
        cleanup = first.cursor()
        cleanup.execute(f'DROP SCHEMA "{schema}" CASCADE')
        first.commit()
        second.close()
        first.close()


def _admit(database_factory, key="intent-1"):
    return AgentRunAdmissionService.admit_atomically(
        auth=AuthContext(user_id="user"),
        blueprint={"id": "bp", "business_id": "biz"},
        version={"id": "v1", "blueprint_id": "bp"},
        input_payload={"preview_mode": False},
        idempotency_key=key,
        require_execution_mode_confirmation=True,
        database_factory=database_factory,
    )


def test_audit_failure_rolls_back_reservation_and_run(admission_db):
    first, second, database = admission_db
    cursor = first.cursor()
    cursor.execute("""CREATE FUNCTION reject_admission_audit() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'audit intentionally rejected'; END;
    $$""")
    cursor.execute("""CREATE TRIGGER reject_admission_audit_trigger BEFORE INSERT ON agent_artifacts
        FOR EACH ROW EXECUTE FUNCTION reject_admission_audit()""")
    first.commit()

    with pytest.raises(psycopg2.Error):
        _admit(database)

    verify = second.cursor()
    for table_name in ("test_credit_reservations", "agent_runs", "agent_artifacts"):
        verify.execute(f"SELECT COUNT(*) AS count FROM {table_name}")
        assert verify.fetchone()["count"] == 0


def test_retry_reuses_one_audit_after_pause_and_new_intent_is_rejected(admission_db):
    first, second, database = admission_db
    first_result = _admit(database)
    assert first_result["success"] is True, first_result
    run_id = first_result["run"]["id"]

    cursor = first.cursor()
    cursor.execute(
        "UPDATE agent_blueprints SET status='paused', metadata_json=%s::jsonb WHERE id='bp'",
        ('{"active_version_id":"v2","execution_mode":"manual"}',),
    )
    cursor.execute("INSERT INTO agent_blueprint_versions(id,blueprint_id,execution_mode,compiled_state) VALUES ('v2','bp','manual','legacy')")
    first.commit()

    retry = _admit(database)
    assert retry["success"] is True
    assert retry["reused"] is True
    assert retry["run"]["id"] == run_id
    rejected = _admit(database, "new-intent")
    assert rejected["success"] is False
    assert rejected["code"] == "AGENT_RUN_BLUEPRINT_NOT_ACTIVE"

    verify = second.cursor()
    verify.execute("SELECT COUNT(*) AS count FROM agent_runs")
    assert verify.fetchone()["count"] == 1
    verify.execute("SELECT COUNT(*) AS count FROM test_credit_reservations")
    assert verify.fetchone()["count"] == 1
    verify.execute("SELECT COUNT(*) AS count FROM agent_artifacts WHERE artifact_type='run_admission_audit'")
    assert verify.fetchone()["count"] == 1


def test_async_endpoint_defers_stale_state_to_admission_but_sync_keeps_early_gate(monkeypatch):
    """Only the durable async route may pass an old pinned version to replay."""
    from flask import Flask
    from api import agent_blueprints_api
    from services.agent_run_admission import AgentRunAdmissionService

    class Cursor:
        pass

    class Connection:
        def cursor(self):
            return Cursor()

        def commit(self):
            return None

        def rollback(self):
            return None

    class Database:
        def __init__(self):
            self.conn = Connection()

        def rollback_and_close(self):
            return None

        def close(self):
            return None

    blueprint = {
        "id": "bp",
        "business_id": "biz",
        "status": "paused",
        "metadata_json": {"execution_mode": "manual", "active_version_id": "v2"},
    }
    version = {"id": "v1", "blueprint_id": "bp", "execution_mode": "manual", "inputs_schema_json": {}, "steps_json": []}
    admitted_keys = []

    def admit(_self, **kwargs):
        admitted_keys.append(kwargs["idempotency_key"])
        if kwargs["idempotency_key"] == "retry":
            return {"success": True, "reused": True, "run": {"id": "old-run"}}
        return {"success": False, "code": "AGENT_RUN_BLUEPRINT_NOT_ACTIVE", "error": "paused"}

    monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", Database)
    monkeypatch.setattr(agent_blueprints_api, "_require_auth", lambda: ({"user_id": "user"}, None))
    monkeypatch.setattr(agent_blueprints_api, "_require_blueprint_access", lambda *_args: (dict(blueprint), None))
    monkeypatch.setattr(agent_blueprints_api, "_load_blueprint_version_for_blueprint", lambda *_args: dict(version))
    monkeypatch.setattr(agent_blueprints_api, "validate_agent_run_input", lambda *_args: {"valid": True, "input": {}, "public_schema": {}})
    monkeypatch.setattr(AgentRunAdmissionService, "admit", admit)
    app = Flask(__name__)

    monkeypatch.setattr(agent_blueprints_api, "async_agent_runs_enabled", lambda _business_id: True)
    with app.test_request_context("/api/agent-blueprints/bp/runs", method="POST", json={"blueprint_version_id": "v1", "idempotency_key": "retry", "input": {}}):
        response, status = agent_blueprints_api.start_agent_blueprint_run("bp")
    assert status == 200
    assert response.get_json()["reused"] is True
    with app.test_request_context("/api/agent-blueprints/bp/runs", method="POST", json={"blueprint_version_id": "v1", "idempotency_key": "new", "input": {}}):
        response, status = agent_blueprints_api.start_agent_blueprint_run("bp")
    assert status == 400
    assert response.get_json()["code"] == "AGENT_RUN_BLUEPRINT_NOT_ACTIVE"
    assert admitted_keys == ["retry", "new"]

    monkeypatch.setattr(agent_blueprints_api, "async_agent_runs_enabled", lambda _business_id: False)
    with app.test_request_context("/api/agent-blueprints/bp/runs", method="POST", json={"blueprint_version_id": "v1", "idempotency_key": "sync", "input": {}}):
        response, status = agent_blueprints_api.start_agent_blueprint_run("bp")
    assert status == 400
    assert response.get_json()["code"] == "AGENT_VERSION_NOT_ACTIVE"
    assert admitted_keys == ["retry", "new"]


def test_shared_admission_rejects_compiled_impersonation_before_enqueue(monkeypatch):
    from services import agent_run_admission

    class Cursor:
        def __init__(self):
            self.rows = [
                {"id": "bp", "business_id": "biz", "status": "draft", "metadata_json": {}},
                {"id": "version", "blueprint_id": "bp", "compiled_state": "approved"},
            ]

        def execute(self, *_args):
            return None

        def fetchone(self):
            return self.rows.pop(0)

    monkeypatch.setattr(agent_run_admission, "verify_business_access", lambda *_args: (True, "owner"))
    monkeypatch.setattr(
        agent_run_admission,
        "enqueue_agent_run",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("compiled impersonation must not enqueue")),
    )
    result = agent_run_admission.AgentRunAdmissionService(Cursor()).admit(
        auth=AuthContext(user_id="user", impersonating=True),
        blueprint={"id": "bp", "business_id": "biz"},
        version={"id": "version"},
        input_payload={},
        idempotency_key="intent",
    )
    assert result["code"] == "COMPILED_SESSION_NOT_ALLOWED"
