"""The compiled worker must release its read transaction before sandbox work."""
import os
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest


def test_compiled_claim_closes_its_real_postgres_transaction(monkeypatch):
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires isolated PostgreSQL")
    first = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    second = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_compiled_claim_" + uuid.uuid4().hex
    cursor = first.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    second.cursor().execute(f'SET search_path TO "{schema}"')
    try:
        cursor.execute("CREATE TABLE users(id TEXT PRIMARY KEY,is_superadmin BOOLEAN,is_active BOOLEAN,is_verified BOOLEAN)")
        cursor.execute("CREATE TABLE businesses(id TEXT PRIMARY KEY,owner_id TEXT,network_id TEXT,is_active BOOLEAN)")
        cursor.execute("CREATE TABLE business_members(business_id TEXT,user_id TEXT,status TEXT)")
        cursor.execute("CREATE TABLE network_members(network_id TEXT,user_id TEXT,status TEXT)")
        cursor.execute("CREATE TABLE networks(id TEXT PRIMARY KEY,owner_id TEXT)")
        cursor.execute("CREATE TABLE agent_blueprints(id TEXT PRIMARY KEY,status TEXT,compiled_approved_version_id TEXT)")
        cursor.execute("""CREATE TABLE agent_blueprint_versions(
            id TEXT PRIMARY KEY, compiled_state TEXT, compiled_artifact_json JSONB,
            compiled_artifact_hash TEXT, compiled_preview_json JSONB,
            compiled_approved_at TIMESTAMPTZ, compiled_approved_by_user_id TEXT
        )""")
        cursor.execute("""CREATE TABLE agent_runs(
            id TEXT PRIMARY KEY, blueprint_id TEXT, blueprint_version_id TEXT, status TEXT, lease_token TEXT,
            created_by_user_id TEXT, business_id TEXT, input_json JSONB,
            input_snapshot_id TEXT, input_snapshot_hash TEXT
        )""")
        cursor.execute("""CREATE TABLE agent_artifacts(
            id TEXT PRIMARY KEY,run_id TEXT,artifact_type TEXT,payload_json JSONB,created_at TIMESTAMPTZ
        )""")
        cursor.execute("INSERT INTO users VALUES ('user',FALSE,TRUE,TRUE)")
        cursor.execute("INSERT INTO businesses VALUES ('biz','owner',NULL,TRUE)")
        cursor.execute("INSERT INTO business_members VALUES ('biz','user','active')")
        cursor.execute("INSERT INTO agent_blueprints VALUES ('bp','active','version')")
        cursor.execute("""INSERT INTO agent_blueprint_versions(
            id,compiled_state,compiled_artifact_json,compiled_artifact_hash,
            compiled_preview_json,compiled_approved_at,compiled_approved_by_user_id
        ) VALUES ('version','approved','{}'::jsonb,'',
            '{"status":"passed","fixture_digest":"fixture","fixture_results":[{"passed":true,"source":"user"}],"result":{"artifact_hash":""}}'::jsonb,
            NOW(),'user')""")
        cursor.execute("""INSERT INTO agent_runs VALUES (
            'run','bp','version','running','lease','user','biz','{}'::jsonb,NULL,NULL
        )""")
        cursor.execute("""INSERT INTO agent_artifacts VALUES (
            'audit','run','run_admission_audit',
            '{"actor":{"user_id":"user","session_kind":"standard","impersonating":false}}'::jsonb,NOW()
        )""")
        first.commit()

        from services import agent_run_queue
        import database_manager

        class Database:
            def __init__(self):
                self.conn = first

            def rollback_and_close(self):
                self.conn.rollback()

        monkeypatch.setattr(database_manager, "DatabaseManager", Database)
        monkeypatch.setattr(agent_run_queue, "validate_compiled_script_artifact", lambda _artifact: {"valid": True, "manifest": {}})
        monkeypatch.setattr("services.compiled_pilot_access.compiled_pilot_allowed", lambda *_args, **_kwargs: True)

        prepared = agent_run_queue.compiled_run_claim({"id": "run", "lease_token": "lease"})
        assert prepared and not prepared.get("error")

        probe = second.cursor()
        probe.execute("SELECT id FROM agent_runs WHERE id='run' FOR UPDATE NOWAIT")
        assert probe.fetchone()["id"] == "run"
        second.rollback()

        cursor.execute("UPDATE users SET is_active=FALSE WHERE id='user'")
        first.commit()
        assert agent_run_queue.compiled_run_claim({"id": "run", "lease_token": "lease"}) == {
            "error": "compiled_actor_account_not_active"
        }
        cursor.execute("UPDATE users SET is_active=TRUE WHERE id='user'")
        cursor.execute(
            "UPDATE agent_artifacts SET payload_json=%s::jsonb WHERE id='audit'",
            ('{"actor":{"user_id":"user","session_kind":"demo","impersonating":false}}',),
        )
        first.commit()
        assert agent_run_queue.compiled_run_claim({"id": "run", "lease_token": "lease"}) == {
            "error": "compiled_admission_context_invalid"
        }
    finally:
        second.rollback()
        first.rollback()
        cleanup = first.cursor()
        cleanup.execute(f'DROP SCHEMA "{schema}" CASCADE')
        first.commit()
        second.close()
        first.close()
