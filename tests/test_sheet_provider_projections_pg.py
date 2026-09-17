"""Real PostgreSQL checks for user-visible unresolved sheet work."""
from datetime import datetime, timezone
import importlib.util
import os
from pathlib import Path
import uuid

from flask import Flask
import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from services.today_workspace import automation_work, section_items


@pytest.fixture
def projection_db():
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires isolated PostgreSQL")
    parameters = psycopg2.extensions.parse_dsn(dsn)
    assert "test" in parameters.get("dbname", "")
    assert parameters.get("host", "").startswith(("/tmp/", "/private/tmp/")) or parameters.get("host") in {"localhost", "127.0.0.1", "postgres"}
    connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_sheet_projection_" + uuid.uuid4().hex
    cursor = connection.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    cursor.execute("CREATE TABLE agent_blueprints(id TEXT PRIMARY KEY, name TEXT, status TEXT DEFAULT 'active')")
    cursor.execute("""CREATE TABLE agent_runs(id TEXT PRIMARY KEY,blueprint_id TEXT,business_id TEXT,
        status TEXT,updated_at TIMESTAMPTZ DEFAULT NOW(),input_json JSONB DEFAULT '{}'::jsonb)""")
    cursor.execute("CREATE TABLE agent_artifacts(run_id TEXT,artifact_type TEXT)")
    class Operations:
        def execute(self, query):
            cursor.execute(query)

    for filename in ("20260609_add_custom_agent_integration_tables.py", "20260907_add_sheet_provider_fences.py"):
        spec = importlib.util.spec_from_file_location("projection_migration", Path(__file__).parents[1] / "alembic_migrations/versions" / filename)
        migration = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(migration)
        migration.op = Operations()
        migration.upgrade()
        migration.upgrade()
    cursor.execute("ALTER TABLE agent_sheet_operation_requests ALTER COLUMN action_id SET DEFAULT gen_random_uuid()::text")
    cursor.execute("ALTER TABLE agent_sheet_operation_requests ALTER COLUMN operation SET DEFAULT 'append_row'")
    cursor.execute("ALTER TABLE agent_sheet_operation_requests ALTER COLUMN status SET DEFAULT 'provider_pending'")
    cursor.execute("INSERT INTO agent_blueprints(id,name) VALUES ('agent','Проверка таблицы')")
    connection.commit()
    try:
        yield connection
    finally:
        connection.rollback()
        cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
        connection.commit()
        connection.close()


def test_today_separates_provider_wait_from_uncertain_result_and_scope(projection_db):
    cursor = projection_db.cursor()
    for name, state in (("queued", "provider_request_queued"), ("writing", "provider_executing"),
                        ("unknown", "provider_reconciliation_required"), ("revoked", "approval_invalid")):
        cursor.execute("INSERT INTO agent_runs(id,blueprint_id,business_id,status) VALUES (%s,'agent','business','waiting_provider')", (name,))
        cursor.execute("INSERT INTO agent_sheet_operation_requests(id,bound_run_id,business_id,apply_state) VALUES (%s,%s,'business',%s)", (name, name, state))
    cursor.execute("INSERT INTO agent_runs(id,blueprint_id,business_id,status) VALUES ('done','agent','business','completed'),('foreign','agent','other','waiting_provider')")
    # Even an inconsistent request row from another business cannot change this run's projection.
    cursor.execute("INSERT INTO agent_sheet_operation_requests(id,bound_run_id,business_id,apply_state) VALUES ('cross-scope','queued','other','provider_reconciliation_required')")
    items = automation_work(cursor, {"business_ids": ["business"]}, datetime.now(timezone.utc))
    sections = section_items(items, "automation")
    assert {item["entity_id"] for item in sections["continue_work"]} == {"queued", "writing"}
    assert {item["entity_id"] for item in sections["needs_decision"]} == {"unknown", "revoked"}
    assert {item["entity_id"] for item in sections["results"]} == {"done"}
    uncertain = next(item for item in items if item["entity_id"] == "unknown")
    assert "Сверьте таблицу" in uncertain["description"]
    assert uncertain["urgency"] == "urgent"
    assert "run_id=unknown" in uncertain["action"]["url"]
    assert "business_id=business" in uncertain["action"]["url"]


def test_provider_migration_prepares_binding_and_claim_indexes(projection_db):
    cursor = projection_db.cursor()
    cursor.execute("SELECT indexname FROM pg_indexes WHERE schemaname=current_schema() AND tablename='agent_sheet_operation_requests'")
    assert {"idx_agent_sheet_provider_binding", "idx_agent_sheet_provider_claim"}.issubset({row["indexname"] for row in cursor.fetchall()})
    cursor.execute("INSERT INTO agent_sheet_operation_requests(id,business_id,status,apply_state) VALUES ('legacy','other','approved_for_execution','provider_request_queued')")
    cursor.execute("SELECT bound_run_id,provider_lease_token,provider_attempt_count,provider_result_json FROM agent_sheet_operation_requests WHERE id='legacy'")
    assert cursor.fetchone() == {"bound_run_id": None, "provider_lease_token": None, "provider_attempt_count": 0, "provider_result_json": {}}


@pytest.mark.parametrize("provider_state", ["provider_request_queued", "provider_executing", "provider_reconciliation_required"])
def test_archive_cannot_hide_unresolved_sheet_effect(projection_db, monkeypatch, provider_state):
    from api import agent_blueprints_api

    cursor = projection_db.cursor()
    cursor.execute("INSERT INTO agent_runs(id,blueprint_id,business_id,status) VALUES ('run','agent','business','waiting_provider')")
    cursor.execute("INSERT INTO agent_sheet_operation_requests(id,bound_run_id,business_id,apply_state) VALUES ('request','run','business',%s)", (provider_state,))
    projection_db.commit()

    class Database:
        def __init__(self):
            self.conn = projection_db

        def close(self):
            self.conn.rollback()

    monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", Database)
    monkeypatch.setattr(agent_blueprints_api, "_require_auth", lambda: ({"user_id": "user"}, None))
    monkeypatch.setattr(agent_blueprints_api, "_require_blueprint_access", lambda *_args: ({"id": "agent", "status": "active"}, None))
    app = Flask(__name__)
    context = app.test_request_context("/api/agent-blueprints/agent", method="DELETE", json={})
    context.push()
    try:
        response, status = agent_blueprints_api.archive_agent_blueprint("agent")
    finally:
        context.pop()
    assert status == 409
    assert response.get_json()["code"] == "AGENT_RUN_ALREADY_IN_PROGRESS"
    cursor.execute("SELECT status FROM agent_runs WHERE id='run'")
    assert cursor.fetchone()["status"] == "waiting_provider"
    cursor.execute("SELECT status FROM agent_blueprints WHERE id='agent'")
    assert cursor.fetchone()["status"] == "active"
