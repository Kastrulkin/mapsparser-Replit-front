"""Real PostgreSQL regression checks for runtime leases and trigger admission."""
import importlib.util
import os
from pathlib import Path
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from services.operator_async_jobs import claim_next_operator_async_job, update_operator_async_job


@pytest.fixture
def queue_db(monkeypatch):
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        if os.getenv("CI"):
            pytest.fail("LOCALOS_TEST_DATABASE_URL is mandatory for the isolated CI gate")
        pytest.skip("Set LOCALOS_TEST_DATABASE_URL to an isolated PostgreSQL database")
    parameters = psycopg2.extensions.parse_dsn(dsn)
    assert "test" in parameters.get("dbname", "")
    assert parameters.get("host", "").startswith(("/tmp/", "/private/tmp/", "localhost", "127.0.0.1", "postgres"))
    connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    connection.set_client_encoding("UTF8")
    schema = "test_runtime_queue_" + uuid.uuid4().hex
    cursor = connection.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    cursor.execute("CREATE TABLE operator_async_jobs(id TEXT PRIMARY KEY,user_id TEXT NOT NULL,business_id TEXT,kind TEXT NOT NULL,status TEXT NOT NULL,progress INTEGER NOT NULL DEFAULT 0,stage TEXT NOT NULL,payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,result_json JSONB NOT NULL DEFAULT '{}'::jsonb,error_text TEXT,idempotency_key TEXT NOT NULL,attempt_count INTEGER NOT NULL DEFAULT 0,max_attempts INTEGER NOT NULL DEFAULT 3,heartbeat_at TIMESTAMPTZ,next_attempt_at TIMESTAMPTZ,created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),completed_at TIMESTAMPTZ)")
    path = Path(__file__).parents[1] / "alembic_migrations/versions/20260905_add_runtime_job_leases.py"
    spec = importlib.util.spec_from_file_location("runtime_lease_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    monkeypatch.setattr(migration.op, "execute", cursor.execute)
    migration.upgrade()
    connection.commit()
    yield connection
    connection.rollback()
    cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
    connection.commit()
    connection.close()


def test_operator_lease_fences_stale_completion(queue_db):
    cursor = queue_db.cursor()
    cursor.execute("INSERT INTO operator_async_jobs(id,user_id,business_id,kind,status,stage,payload_json,idempotency_key,next_attempt_at) VALUES ('job-1','user-1','business-1','content_plan_generate','queued','queued','{}','key',NOW())")
    claimed = claim_next_operator_async_job(cursor)
    assert claimed["lease_token"]
    assert update_operator_async_job(cursor, job_id="job-1", status="completed", progress=100, stage="done", lease_token=claimed["lease_token"])
    assert not update_operator_async_job(cursor, job_id="job-1", status="completed", progress=100, stage="stale", lease_token="wrong")
