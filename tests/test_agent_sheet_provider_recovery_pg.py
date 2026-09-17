"""External success without a local commit never authorizes an automatic resend."""
import os
import time

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from services import agent_sheet_provider_executor
from tests.test_agent_sheet_provider_queue_pg import sheet_queue_db, _insert_bound_request


@pytest.fixture
def provider_connections(sheet_queue_db, monkeypatch):
    first, _second = sheet_queue_db
    database_url = os.environ["LOCALOS_TEST_DATABASE_URL"]
    cursor = first.cursor()
    cursor.execute("SELECT current_schema() schema")
    schema = cursor.fetchone()["schema"]
    first.commit()
    connections = []

    class Database:
        def __init__(self):
            self.conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
            self.conn.cursor().execute(f'SET search_path TO "{schema}"')
            self.conn.commit()
            connections.append(self.conn)

        def close(self):
            self.conn.close()

    monkeypatch.setattr("database_manager.DatabaseManager", Database)
    monkeypatch.setattr(agent_sheet_provider_executor, "log_agent_action", lambda *_args, **_kwargs: "synthetic-ledger")
    try:
        yield connections
    finally:
        for connection in connections:
            if not connection.closed:
                connection.close()


def test_two_processors_make_one_write_with_no_open_transaction(sheet_queue_db, provider_connections):
    first, second = sheet_queue_db
    _insert_bound_request(first.cursor())
    first.commit()
    calls = []

    class Provider:
        def append_row(self, request):
            calls.append(request["request_id"])
            assert all(connection.closed for connection in provider_connections)
            time.sleep(0.15)
            cursor = second.cursor()
            cursor.execute("SELECT id FROM agent_runs WHERE id='run' FOR UPDATE NOWAIT")
            cursor.execute("SELECT id FROM agent_sheet_operation_requests WHERE id='sheet-1' FOR UPDATE NOWAIT")
            second.rollback()
            assert agent_sheet_provider_executor.process_next_sheet_provider_request(adapter=self) is None
            return {"success": True}

    result = agent_sheet_provider_executor.process_next_sheet_provider_request(adapter=Provider())
    assert result["success"]
    assert calls == ["sheet-1"]
    cursor = second.cursor()
    cursor.execute("SELECT status FROM agent_runs WHERE id='run'")
    assert cursor.fetchone()["status"] == "queued"


def test_expired_finisher_cannot_resume_run_even_before_recovery(sheet_queue_db, provider_connections):
    first, second = sheet_queue_db
    _insert_bound_request(first.cursor())
    first.commit()
    claimed = agent_sheet_provider_executor.claim_next_sheet_provider_request(first.cursor())
    first.commit()
    first.cursor().execute("UPDATE agent_sheet_operation_requests SET provider_lease_expires_at=NOW()-INTERVAL '1 second'")
    first.commit()
    result = agent_sheet_provider_executor._finish_applied(claimed, {}, "user", {"success": True})
    assert result["code"] == "SHEET_PROVIDER_LEASE_LOST"
    cursor = second.cursor()
    cursor.execute("SELECT status FROM agent_runs WHERE id='run'")
    assert cursor.fetchone()["status"] == "waiting_provider"
    assert agent_sheet_provider_executor.recover_expired_sheet_provider_attempts(cursor) == 1
    second.commit()
    assert agent_sheet_provider_executor.claim_next_sheet_provider_request(cursor) is None


def test_provider_timeout_stays_unknown_without_automatic_repeat(sheet_queue_db, provider_connections):
    first, second = sheet_queue_db
    _insert_bound_request(first.cursor())
    first.commit()
    calls = []

    class Provider:
        def append_row(self, request):
            calls.append(request["request_id"])
            raise TimeoutError("synthetic response lost after write")

    result = agent_sheet_provider_executor.process_next_sheet_provider_request(adapter=Provider())
    assert result["apply_state"] == "provider_reconciliation_required"
    assert agent_sheet_provider_executor.process_next_sheet_provider_request(adapter=Provider()) is None
    assert calls == ["sheet-1"]
    cursor = second.cursor()
    cursor.execute("SELECT provider_result_json FROM agent_sheet_operation_requests WHERE id='sheet-1'")
    assert cursor.fetchone()["provider_result_json"]["certainty"] == "unknown"
    cursor.execute("SELECT status FROM agent_run_steps WHERE id='step'")
    assert cursor.fetchone()["status"] == "waiting_provider"


def test_local_commit_failure_after_provider_success_requires_reconciliation(sheet_queue_db, provider_connections, monkeypatch):
    first, second = sheet_queue_db
    _insert_bound_request(first.cursor())
    first.commit()
    calls = []

    class Provider:
        def append_row(self, request):
            calls.append(request["request_id"])
            return {"success": True}

    def unavailable_ledger(*_args, **_kwargs):
        raise RuntimeError("synthetic final transaction failure")

    monkeypatch.setattr(agent_sheet_provider_executor, "log_agent_action", unavailable_ledger)
    with pytest.raises(RuntimeError, match="synthetic final transaction failure"):
        agent_sheet_provider_executor.process_next_sheet_provider_request(adapter=Provider())
    cursor = second.cursor()
    cursor.execute("SELECT apply_state FROM agent_sheet_operation_requests WHERE id='sheet-1'")
    assert cursor.fetchone()["apply_state"] == "provider_executing"
    cursor.execute("SELECT status FROM agent_run_steps WHERE id='step'")
    assert cursor.fetchone()["status"] == "waiting_provider"
    cursor.execute("UPDATE agent_sheet_operation_requests SET provider_lease_expires_at=NOW()-INTERVAL '1 second'")
    second.commit()
    assert agent_sheet_provider_executor.process_next_sheet_provider_request(adapter=Provider()) is None
    assert calls == ["sheet-1"]
    cursor.execute("SELECT provider_result_json FROM agent_sheet_operation_requests WHERE id='sheet-1'")
    assert cursor.fetchone()["provider_result_json"]["certainty"] == "unknown"


def test_resumed_run_preserves_sheet_step_and_finalizes_once(sheet_queue_db, provider_connections, monkeypatch):
    from services import agent_run_queue
    from services.agent_blueprint_runner import AgentBlueprintRunner

    first, second = sheet_queue_db
    cursor = first.cursor()
    _insert_bound_request(cursor)
    cursor.execute("""ALTER TABLE agent_runs
        ADD COLUMN started_at TIMESTAMPTZ, ADD COLUMN completed_at TIMESTAMPTZ,
        ADD COLUMN queued_at TIMESTAMPTZ DEFAULT NOW(), ADD COLUMN error_text TEXT,
        ADD COLUMN attempt_count INTEGER DEFAULT 0, ADD COLUMN max_attempts INTEGER DEFAULT 3,
        ADD COLUMN blueprint_version_id TEXT DEFAULT 'version', ADD COLUMN created_by_user_id TEXT DEFAULT 'user',
        ADD COLUMN output_json JSONB DEFAULT '{}'::jsonb""")
    cursor.execute("ALTER TABLE agent_run_steps ADD COLUMN step_index INTEGER DEFAULT 0")
    cursor.execute("CREATE TABLE users(id TEXT PRIMARY KEY,is_superadmin BOOLEAN)")
    cursor.execute("INSERT INTO users VALUES ('user',FALSE)")
    cursor.execute("CREATE TABLE agent_blueprint_versions(id TEXT PRIMARY KEY,blueprint_id TEXT,steps_json JSONB)")
    cursor.execute("""INSERT INTO agent_blueprint_versions VALUES ('version','blueprint',
        '[{"key":"sheet","type":"capability","capability":"sheets.append_row_request"},
        {"key":"report","type":"artifact","artifact_type":"test_report"}]')""")
    cursor.execute("CREATE TABLE test_billing_finalizations(run_id TEXT PRIMARY KEY)")
    cursor.execute("UPDATE agent_run_steps SET output_json='{\"approval_evidence\":\"retained\"}' WHERE id='step'")
    first.commit()
    writes = []

    class Provider:
        def append_row(self, request):
            writes.append(request["request_id"])
            return {"success": True}

    assert agent_sheet_provider_executor.process_next_sheet_provider_request(adapter=Provider())["success"]
    artifact_calls = []

    def load_run(self, run_id, *_args):
        self.cursor.execute("SELECT * FROM agent_runs WHERE id=%s", (run_id,))
        return dict(self.cursor.fetchone())

    def next_artifact(self, run, step, step_index):
        artifact_calls.append(step["key"])
        self.cursor.execute("INSERT INTO agent_run_steps(id,run_id,status,step_index) VALUES ('report',%s,'completed',%s)", (run["id"], step_index))
        return True

    def settle(billing_cursor, *, run, actual_tokens):
        billing_cursor.execute("INSERT INTO test_billing_finalizations VALUES (%s)", (run["id"],))
        return {"status": "charged", "charged_credits": 0}

    monkeypatch.setattr(AgentBlueprintRunner, "load_run", load_run)
    monkeypatch.setattr(AgentBlueprintRunner, "_create_openclaw_preview_observations", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(AgentBlueprintRunner, "_create_artifact_step", next_artifact)
    monkeypatch.setattr(AgentBlueprintRunner, "_build_run_output", lambda *_args: {"result": "test report"})
    monkeypatch.setattr(agent_run_queue, "finalize_agent_run_credits", settle)
    claimed_run = agent_run_queue.claim_next_agent_run(cursor)
    first.commit()
    result = agent_run_queue.execute_claimed_agent_run(cursor, claimed_run)
    first.commit()
    assert result["run"]["status"] == "completed"
    assert agent_run_queue.execute_claimed_agent_run(cursor, claimed_run)["code"] == "AGENT_RUN_LEASE_LOST"
    first.commit()
    assert artifact_calls == ["report"]
    assert writes == ["sheet-1"]
    verify = second.cursor()
    verify.execute("SELECT output_json FROM agent_run_steps WHERE id='step'")
    assert verify.fetchone()["output_json"]["approval_evidence"] == "retained"
    verify.execute("SELECT COUNT(*) total FROM test_billing_finalizations")
    assert verify.fetchone()["total"] == 1
