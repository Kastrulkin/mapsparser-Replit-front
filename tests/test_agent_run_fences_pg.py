"""Real PostgreSQL fencing checks for the compiled queue finalizer."""
import os
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from services.agent_run_queue import claim_next_agent_run, finish_agent_run_claim


@pytest.fixture
def fenced_db():
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires isolated PostgreSQL")
    first = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_agent_fence_" + uuid.uuid4().hex
    cursor = first.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    cursor.execute("""CREATE TABLE agent_runs(
        id TEXT PRIMARY KEY, status TEXT NOT NULL, heartbeat_at TIMESTAMPTZ,
        next_attempt_at TIMESTAMPTZ, queued_at TIMESTAMPTZ DEFAULT NOW(),
        started_at TIMESTAMPTZ, completed_at TIMESTAMPTZ, updated_at TIMESTAMPTZ DEFAULT NOW(),
        attempt_count INTEGER NOT NULL DEFAULT 0, max_attempts INTEGER NOT NULL DEFAULT 3,
        lease_token TEXT, error_text TEXT)""")
    first.commit()
    second = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    second.cursor().execute(f'SET search_path TO "{schema}"')
    try:
        yield first, second, schema
    finally:
        second.rollback()
        first.rollback()
        cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
        first.commit()
        second.close()
        first.close()


def test_stale_compiled_finisher_cannot_close_reclaimed_run(fenced_db):
    first, second, _schema = fenced_db
    first.cursor().execute("INSERT INTO agent_runs(id,status) VALUES ('run','queued')")
    first.commit()
    original = claim_next_agent_run(first.cursor())
    first.commit()
    assert original["lease_token"]
    first.cursor().execute("UPDATE agent_runs SET heartbeat_at=NOW()-INTERVAL '10 minutes' WHERE id='run'")
    first.commit()
    replacement = claim_next_agent_run(second.cursor())
    second.commit()
    assert replacement["lease_token"] != original["lease_token"]
    assert not finish_agent_run_claim(first.cursor(), run_id="run", lease_token=original["lease_token"], status="completed")
    first.commit()
    verify = second.cursor()
    verify.execute("SELECT status,lease_token FROM agent_runs WHERE id='run'")
    current = verify.fetchone()
    assert current["status"] == "running"
    assert current["lease_token"] == replacement["lease_token"]


def test_compiled_executor_releases_db_before_sandbox_and_fences_billing(fenced_db, monkeypatch):
    first, second, schema = fenced_db
    cursor = first.cursor()
    cursor.execute("ALTER TABLE agent_runs ADD COLUMN output_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    cursor.execute("ALTER TABLE agent_runs ADD COLUMN billing_reservation_id TEXT")
    cursor.execute("ALTER TABLE agent_runs ADD COLUMN business_id TEXT DEFAULT 'biz'")
    cursor.execute("ALTER TABLE agent_runs ADD COLUMN created_by_user_id TEXT DEFAULT 'user'")
    cursor.execute("CREATE TABLE billing_ledger(run_id TEXT PRIMARY KEY)")
    cursor.execute("INSERT INTO agent_runs(id,status) VALUES ('compiled','queued')")
    first.commit()
    claimed = claim_next_agent_run(cursor)
    first.commit()

    from services import agent_run_queue
    import database_manager

    class Database:
        def __init__(self):
            self.conn = first

        def rollback_and_close(self):
            first.rollback()

        def close(self):
            return None

    monkeypatch.setattr(database_manager, "DatabaseManager", Database)
    monkeypatch.setattr(agent_run_queue, "compiled_run_claim", lambda _run: {"run": claimed, "artifact": {"artifact_hash": "x"}, "input": {"rows": []}})

    def sandbox(_artifact, _input):
        probe = second.cursor()
        probe.execute(f'SET search_path TO "{schema}"')
        probe.execute("SELECT id FROM agent_runs WHERE id='compiled' FOR UPDATE NOWAIT")
        second.rollback()
        return {"schema": "result", "artifact_hash": "x", "runtime_ai_calls": 0, "external_effects": []}

    def settle(billing_cursor, *, run, actual_tokens):
        billing_cursor.execute("INSERT INTO billing_ledger(run_id) VALUES (%s) ON CONFLICT DO NOTHING", (run["id"],))
        return {"status": "charged", "charged_credits": 0}

    monkeypatch.setattr(agent_run_queue, "execute_in_attested_sandbox", sandbox)
    monkeypatch.setattr(agent_run_queue, "finalize_agent_run_credits", settle)
    result = agent_run_queue.execute_claimed_compiled_agent_run(claimed)
    assert result["success"] is True
    repeated = agent_run_queue.execute_claimed_compiled_agent_run(claimed)
    assert repeated["code"] == "AGENT_RUN_LEASE_LOST"
    verify = second.cursor()
    verify.execute(f'SET search_path TO "{schema}"')
    verify.execute("SELECT COUNT(*) AS count FROM billing_ledger")
    assert verify.fetchone()["count"] == 1


def test_stale_exhaustion_releases_reservation_once(fenced_db, monkeypatch):
    first, _second, _schema = fenced_db
    cursor = first.cursor()
    cursor.execute("ALTER TABLE agent_runs ADD COLUMN billing_reservation_id TEXT")
    cursor.execute("ALTER TABLE agent_runs ADD COLUMN business_id TEXT DEFAULT 'biz'")
    cursor.execute("ALTER TABLE agent_runs ADD COLUMN created_by_user_id TEXT DEFAULT 'user'")
    cursor.execute("CREATE TABLE operatorcreditreservations(id TEXT PRIMARY KEY,reserved_credits INTEGER)")
    cursor.execute("CREATE TABLE released_reservations(id TEXT PRIMARY KEY)")
    cursor.execute("INSERT INTO operatorcreditreservations VALUES ('reservation',2)")
    cursor.execute("INSERT INTO agent_runs(id,status,attempt_count,max_attempts,heartbeat_at,billing_reservation_id) VALUES ('expired','running',3,3,NOW()-INTERVAL '10 minutes','reservation')")
    first.commit()
    from services import agent_run_queue
    monkeypatch.setattr(agent_run_queue, "finalize_agent_run_credits", lambda billing_cursor, *, run, actual_tokens: billing_cursor.execute("INSERT INTO released_reservations VALUES (%s) ON CONFLICT DO NOTHING", (run["billing_reservation_id"],)) or {"status": "released"})
    assert claim_next_agent_run(cursor) is None
    first.commit()
    assert claim_next_agent_run(cursor) is None
    first.commit()
    cursor.execute("SELECT COUNT(*) AS count FROM released_reservations")
    assert cursor.fetchone()["count"] == 1
