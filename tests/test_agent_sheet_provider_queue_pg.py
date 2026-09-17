"""PostgreSQL fencing checks for the Google Sheets provider boundary."""
import os
import uuid
import json

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from services.agent_sheet_provider_executor import claim_next_sheet_provider_request, recover_expired_sheet_provider_attempts, sheet_request_hash


@pytest.fixture
def sheet_queue_db():
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires isolated PostgreSQL")
    first = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_sheet_provider_" + uuid.uuid4().hex
    cursor = first.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    cursor.execute("CREATE TABLE agent_blueprints(id TEXT PRIMARY KEY,status TEXT NOT NULL)")
    cursor.execute("CREATE TABLE agent_runs(id TEXT PRIMARY KEY,blueprint_id TEXT NOT NULL,business_id TEXT NOT NULL,status TEXT NOT NULL,input_json JSONB NOT NULL DEFAULT '{}'::jsonb,lease_token TEXT,heartbeat_at TIMESTAMPTZ,next_attempt_at TIMESTAMPTZ,updated_at TIMESTAMPTZ DEFAULT NOW())")
    cursor.execute("CREATE TABLE agent_run_steps(id TEXT PRIMARY KEY,run_id TEXT NOT NULL,status TEXT NOT NULL,output_json JSONB NOT NULL DEFAULT '{}'::jsonb,completed_at TIMESTAMPTZ)")
    cursor.execute("CREATE TABLE agent_approvals(id TEXT PRIMARY KEY,run_id TEXT NOT NULL,status TEXT NOT NULL,approval_type TEXT NOT NULL,payload_json JSONB NOT NULL DEFAULT '{}'::jsonb)")
    cursor.execute("""CREATE TABLE agent_sheet_operation_requests(
        id TEXT PRIMARY KEY,action_id TEXT UNIQUE,business_id TEXT,user_id TEXT,integration_id TEXT,spreadsheet_id TEXT,sheet_name TEXT,operation TEXT,
        status TEXT,approval_state TEXT,apply_state TEXT,row_values_json JSONB,mapping_json JSONB,source_event_json JSONB,limits_json JSONB,
        provider_write_performed BOOLEAN NOT NULL DEFAULT FALSE,bound_run_id TEXT,bound_step_id TEXT,bound_approval_id TEXT,request_hash TEXT,
        provider_state TEXT NOT NULL DEFAULT 'not_queued',provider_lease_token TEXT,provider_lease_expires_at TIMESTAMPTZ,
        provider_attempt_count INTEGER NOT NULL DEFAULT 0,provider_result_json JSONB NOT NULL DEFAULT '{}'::jsonb,error_text TEXT,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    first.commit()
    second = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    second.cursor().execute(f'SET search_path TO "{schema}"')
    second.commit()
    try:
        yield first, second
    finally:
        second.rollback()
        first.rollback()
        cursor.execute(f'DROP SCHEMA IF EXISTS "{schema}" CASCADE')
        first.commit()
        second.close()
        first.close()


def _insert_bound_request(cursor, request_id="sheet-1"):
    cursor.execute("INSERT INTO agent_blueprints VALUES ('blueprint','active')")
    cursor.execute("INSERT INTO agent_runs(id,blueprint_id,business_id,status) VALUES ('run','blueprint','biz','waiting_provider')")
    cursor.execute("INSERT INTO agent_run_steps VALUES ('step','run','waiting_provider')")
    row = {"id": request_id, "action_id": "action", "business_id": "biz", "integration_id": "integration", "spreadsheet_id": "sheet", "sheet_name": "Leads", "operation": "append_row", "row_values_json": ["row"], "mapping_json": {}, "source_event_json": {}, "limits_json": {}}
    row.update({"bound_run_id": "run", "bound_step_id": "step", "bound_approval_id": "approval"})
    snapshot_hash = __import__("services.agent_sheet_provider_executor", fromlist=["sheet_snapshot_hash"]).sheet_snapshot_hash(row)
    cursor.execute("INSERT INTO agent_approvals VALUES ('approval','run','approved','sheet_update',%s::jsonb)", (json.dumps({"sheet_write_snapshot": {"hash": snapshot_hash}}),))
    cursor.execute("""INSERT INTO agent_sheet_operation_requests(id,action_id,business_id,integration_id,spreadsheet_id,sheet_name,operation,status,approval_state,apply_state,row_values_json,mapping_json,source_event_json,limits_json,bound_run_id,bound_step_id,bound_approval_id,request_hash)
        VALUES(%s,%s,%s,%s,%s,%s,%s,'provider_pending','approved','provider_request_queued',%s::jsonb,%s::jsonb,%s::jsonb,%s::jsonb,'run','step','approval',%s)""", (row["id"],row["action_id"],row["business_id"],row["integration_id"],row["spreadsheet_id"],row["sheet_name"],row["operation"],"[\"row\"]","{}","{}","{}",sheet_request_hash(row)))


def test_only_one_worker_claims_bound_provider_request(sheet_queue_db):
    first, second = sheet_queue_db
    _insert_bound_request(first.cursor())
    first.commit()
    claimed = claim_next_sheet_provider_request(first.cursor(), business_id="biz")
    first.commit()
    assert claimed and claimed["provider_lease_token"]
    assert claim_next_sheet_provider_request(second.cursor(), business_id="biz") is None
    second.commit()


def test_revoked_or_expired_claim_never_returns_to_send_queue(sheet_queue_db):
    first, second = sheet_queue_db
    _insert_bound_request(first.cursor())
    first.cursor().execute("UPDATE agent_approvals SET status='revoked' WHERE id='approval'")
    first.commit()
    assert claim_next_sheet_provider_request(second.cursor(), business_id="biz") is None
    second.commit()
    verify = second.cursor()
    verify.execute("SELECT apply_state,provider_state FROM agent_sheet_operation_requests WHERE id='sheet-1'")
    held = verify.fetchone()
    assert held["apply_state"] == "approval_invalid"
    assert held["provider_state"] == "approval_invalid"


def test_missing_or_mutated_approval_snapshot_cannot_claim(sheet_queue_db):
    first, second = sheet_queue_db
    _insert_bound_request(first.cursor())
    first.cursor().execute("UPDATE agent_approvals SET payload_json='{}'::jsonb WHERE id='approval'")
    first.commit()
    assert claim_next_sheet_provider_request(second.cursor(), business_id="biz") is None
    second.commit()
    verify = second.cursor()
    verify.execute("SELECT apply_state FROM agent_sheet_operation_requests WHERE id='sheet-1'")
    assert verify.fetchone()["apply_state"] == "approval_invalid"


@pytest.mark.parametrize("input_json", [{"preview_mode": True}, {"external_side_effects_allowed": False}])
def test_preview_or_explicit_no_effect_run_cannot_claim_provider_write(sheet_queue_db, input_json):
    first, second = sheet_queue_db
    _insert_bound_request(first.cursor())
    first.cursor().execute("UPDATE agent_runs SET input_json=%s::jsonb WHERE id='run'", (json.dumps(input_json),))
    first.commit()
    assert claim_next_sheet_provider_request(second.cursor(), business_id="biz") is None
    second.commit()
    verify = second.cursor()
    verify.execute("SELECT apply_state,provider_result_json->>'certainty' AS certainty FROM agent_sheet_operation_requests WHERE id='sheet-1'")
    row = verify.fetchone()
    assert row["apply_state"] == "approval_invalid"
    assert row["certainty"] == "not_sent"


def test_expired_provider_lease_requires_reconciliation(sheet_queue_db):
    first, second = sheet_queue_db
    _insert_bound_request(first.cursor())
    first.cursor().execute("UPDATE agent_sheet_operation_requests SET apply_state='provider_executing',provider_state='executing',provider_lease_token='old',provider_lease_expires_at=NOW()-INTERVAL '1 minute' WHERE id='sheet-1'")
    first.commit()
    assert recover_expired_sheet_provider_attempts(second.cursor()) == 1
    second.commit()
    verify = second.cursor()
    verify.execute("SELECT apply_state,provider_lease_token,provider_result_json->>'certainty' AS certainty FROM agent_sheet_operation_requests WHERE id='sheet-1'")
    held = verify.fetchone()
    assert held["apply_state"] == "provider_reconciliation_required"
    assert held["provider_lease_token"] is None
    assert held["certainty"] == "unknown"


def test_provider_worker_commits_claim_before_fake_write_and_resumes_once(sheet_queue_db, monkeypatch):
    """The production worker path holds neither request nor run locks during I/O."""
    first, second = sheet_queue_db
    _insert_bound_request(first.cursor())
    first.cursor().execute("CREATE TABLE billing_ledger(run_id TEXT PRIMARY KEY)")
    first.commit()
    schema_row = first.cursor()
    schema_row.execute("SELECT current_schema() AS name")
    schema = schema_row.fetchone()["name"]

    import database_manager
    from services import agent_sheet_provider_executor

    class Database:
        def __init__(self):
            self.conn = psycopg2.connect(os.environ["LOCALOS_TEST_DATABASE_URL"], cursor_factory=RealDictCursor)
            cursor = self.conn.cursor()
            cursor.execute(f'SET search_path TO "{schema}"')
            self.conn.commit()

        def close(self):
            self.conn.close()

    class Provider:
        def __init__(self):
            self.calls = 0
            self.locks_released = False

        def append_row(self, request):
            self.calls += 1
            probe = second.cursor()
            probe.execute("SELECT id FROM agent_sheet_operation_requests WHERE id=%s FOR UPDATE NOWAIT", (request["request_id"],))
            probe.execute("SELECT id FROM agent_runs WHERE id='run' FOR UPDATE NOWAIT")
            second.rollback()
            self.locks_released = True
            return {"success": True, "updated_rows": 1, "access_token": "must-not-persist"}

        def update_cells(self, request):
            raise AssertionError("unexpected operation")

    provider = Provider()
    monkeypatch.setattr(database_manager, "DatabaseManager", Database)
    monkeypatch.setattr(agent_sheet_provider_executor, "log_agent_action", lambda *_args, **_kwargs: "ledger")
    result = agent_sheet_provider_executor.process_next_sheet_provider_request(adapter=provider)
    assert result and result["success"] is True
    assert provider.calls == 1
    assert provider.locks_released is True
    assert agent_sheet_provider_executor.process_next_sheet_provider_request(adapter=provider) is None
    assert provider.calls == 1
    verify = first.cursor()
    verify.execute("SELECT status,apply_state,provider_write_performed,provider_result_json FROM agent_sheet_operation_requests WHERE id='sheet-1'")
    request = verify.fetchone()
    assert request["status"] == "applied"
    assert request["apply_state"] == "applied"
    assert request["provider_write_performed"] is True
    assert request["provider_result_json"]["access_token"] == "[redacted]"
    verify.execute("SELECT status FROM agent_run_steps WHERE id='step'")
    assert verify.fetchone()["status"] == "completed"
    verify.execute("SELECT status FROM agent_runs WHERE id='run'")
    assert verify.fetchone()["status"] == "queued"
    verify.execute("SELECT COUNT(*) AS count FROM billing_ledger")
    assert verify.fetchone()["count"] == 0


def test_old_executor_selector_cannot_claim_new_provider_pending_handoff(sheet_queue_db):
    first, _second = sheet_queue_db
    _insert_bound_request(first.cursor())
    first.commit()
    cursor = first.cursor()
    cursor.execute("""SELECT id FROM agent_sheet_operation_requests
        WHERE status='approved_for_execution' AND approval_state='approved' AND apply_state='provider_request_queued'""")
    assert cursor.fetchall() == []


def test_mutated_bound_payload_is_held_without_provider_claim(sheet_queue_db):
    first, second = sheet_queue_db
    _insert_bound_request(first.cursor())
    first.cursor().execute("UPDATE agent_sheet_operation_requests SET mapping_json='{\"range\":\"A1\"}'::jsonb WHERE id='sheet-1'")
    first.commit()
    assert claim_next_sheet_provider_request(second.cursor(), business_id="biz") is None
    second.commit()
    verify = second.cursor()
    verify.execute("SELECT apply_state,provider_result_json->>'certainty' AS certainty FROM agent_sheet_operation_requests WHERE id='sheet-1'")
    row = verify.fetchone()
    assert row["apply_state"] == "provider_reconciliation_required"
    assert row["certainty"] == "not_sent"


@pytest.mark.parametrize(
    ("capability", "payload"),
    [
        ("sheets.append_row_request", {"google_sheets_integration_id": "integration", "google_spreadsheet_id": "sheet", "tab": "Leads", "row_template": ["{{input.name}}"], "trigger_event_id": "event"}),
        ("google_sheets.update_cells", {"google_sheets_integration_id": "integration", "google_spreadsheet_id": "sheet", "tab": "Leads", "range_name": "A1", "values": [["Anna"]], "expected_values": [[""]], "trigger_event_id": "event"}),
    ],
)
def test_actual_runner_snapshot_handler_binder_and_provider_resume(sheet_queue_db, monkeypatch, capability, payload):
    first, second = sheet_queue_db
    cursor = first.cursor()
    cursor.execute("ALTER TABLE agent_approvals ADD COLUMN decided_at TIMESTAMPTZ")
    cursor.execute("CREATE TABLE agent_blueprint_versions(id TEXT PRIMARY KEY,steps_json JSONB NOT NULL)")
    cursor.execute("CREATE TABLE agent_artifacts(id TEXT PRIMARY KEY,run_id TEXT,artifact_type TEXT,payload_json JSONB,created_at TIMESTAMPTZ DEFAULT NOW())")
    cursor.execute("INSERT INTO agent_blueprints VALUES ('blueprint','active')")
    steps = [{"key": "approve", "type": "approval", "approval_type": "sheet_update"}, {"key": "write", "type": "capability", "capability": capability, "payload": payload}]
    cursor.execute("INSERT INTO agent_blueprint_versions VALUES ('version',%s::jsonb)", (json.dumps(steps),))
    cursor.execute("INSERT INTO agent_runs(id,blueprint_id,business_id,status) VALUES ('run','blueprint','biz','waiting_provider')")
    cursor.execute("INSERT INTO agent_run_steps VALUES ('step','run','waiting_provider')")
    first.commit()
    schema_cursor = first.cursor()
    schema_cursor.execute("SELECT current_schema() AS name")
    schema = schema_cursor.fetchone()["name"]

    import database_manager
    from services import agent_capability_handlers, agent_domain_request_executors, agent_sheet_provider_executor
    from services.agent_blueprint_runner import AgentBlueprintRunner

    class Database:
        def __init__(self):
            self.conn = psycopg2.connect(os.environ["LOCALOS_TEST_DATABASE_URL"], cursor_factory=RealDictCursor)
            current = self.conn.cursor()
            current.execute(f'SET search_path TO "{schema}"')
            self.conn.commit()
        def close(self): self.conn.close()

    monkeypatch.setattr(database_manager, "DatabaseManager", Database)
    monkeypatch.setattr(agent_capability_handlers, "DatabaseManager", Database)
    monkeypatch.setattr(agent_domain_request_executors, "log_agent_action", lambda *_args, **_kwargs: "ledger")
    monkeypatch.setattr(agent_sheet_provider_executor, "log_agent_action", lambda *_args, **_kwargs: "ledger")
    run = {"id": "run", "blueprint_version_id": "version", "business_id": "biz", "input_json": {"name": "Anna"}}
    runner = AgentBlueprintRunner(first.cursor())
    snapshot = runner._build_approval_payload(run, steps[0])["sheet_write_snapshot"]
    assert snapshot["sheet_name"] == "Leads"
    cursor = first.cursor()
    cursor.execute("INSERT INTO agent_approvals VALUES ('approval','run','approved','sheet_update',%s::jsonb,NOW())", (json.dumps({"sheet_write_snapshot": snapshot}),))
    first.commit()
    handler_payload = {**payload, "row_template": ["Anna"]} if capability == "sheets.append_row_request" else payload
    envelope = {"tenant_id": "biz", "action_id": "action", "capability": capability, "payload": handler_payload}
    created = agent_capability_handlers._handle_sheets_append_row_request(envelope, {"user_id": "user"})
    created_result = created.get("result") if isinstance(created.get("result"), dict) else {}
    assert created_result.get("request_id"), created
    bind_cursor = first.cursor()
    result = agent_domain_request_executors._approve_sheet_requests(bind_cursor, "biz", "user", "run", "write", "step", "sheet_update", {"request_ids": [created_result["request_id"]], "action_ids": ["action"]})
    first.commit()
    assert result and result[0]["apply_state"] == "provider_request_queued"
    verify_bound = first.cursor()
    verify_bound.execute("SELECT row_values_json FROM agent_sheet_operation_requests WHERE action_id='action'")
    stored_values = verify_bound.fetchone()["row_values_json"]
    changed = {**envelope, "payload": {**envelope["payload"], "row_template": ["Changed"], "values": [["Changed"]]}}
    rejected = agent_capability_handlers._handle_sheets_append_row_request(changed, {"user_id": "user"})
    rejected_result = rejected.get("result") if isinstance(rejected.get("result"), dict) else {}
    assert rejected_result.get("reason_code") == "SHEET_REQUEST_ALREADY_BOUND"
    verify_bound.execute("SELECT row_values_json FROM agent_sheet_operation_requests WHERE action_id='action'")
    assert verify_bound.fetchone()["row_values_json"] == stored_values
    class Provider:
        def append_row(self, request): return {"success": True, "updated_rows": 1}
        def update_cells(self, request): return {"success": True, "updated_rows": 1}
    applied = agent_sheet_provider_executor.process_next_sheet_provider_request(adapter=Provider())
    assert applied and applied["success"]
    verify = second.cursor()
    verify.execute("SELECT status,apply_state FROM agent_sheet_operation_requests WHERE action_id='action'")
    assert verify.fetchone() == {"status": "applied", "apply_state": "applied"}
