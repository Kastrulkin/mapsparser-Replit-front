"""Compiled claims recheck access and release their read transaction before execution."""
import os
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest


@pytest.mark.parametrize("membership_kind", ["direct", "network"])
def test_compiled_claim_rechecks_actor_and_releases_transaction(monkeypatch, membership_kind):
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
        cursor.execute("INSERT INTO businesses VALUES ('biz','owner','network',TRUE)")
        cursor.execute("INSERT INTO networks VALUES ('network','network-owner')")
        if membership_kind == "direct":
            membership_table = "business_members"
            membership_id = "biz"
        else:
            membership_table = "network_members"
            membership_id = "network"
        cursor.execute(f"INSERT INTO {membership_table} VALUES (%s,'user','active')", (membership_id,))
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
        validated_artifacts = []

        def validate_artifact(artifact):
            validated_artifacts.append(artifact)
            return {"valid": True, "manifest": {}}

        monkeypatch.setattr(agent_run_queue, "validate_compiled_script_artifact", validate_artifact)
        monkeypatch.setattr("services.compiled_pilot_access.compiled_pilot_allowed", lambda *_args, **_kwargs: True)

        prepared = agent_run_queue.compiled_run_claim({"id": "run", "lease_token": "lease"})
        assert prepared and not prepared.get("error")

        probe = second.cursor()
        probe.execute("SELECT id FROM agent_runs WHERE id='run' FOR UPDATE NOWAIT")
        assert probe.fetchone()["id"] == "run"
        second.rollback()

        # The queued actor was valid at admission. A later membership change
        # must be observed before its artifact/input can reach the sandbox.
        for revoke_sql in (
            f"UPDATE {membership_table} SET status='inactive' WHERE user_id='user'",
            f"DELETE FROM {membership_table} WHERE user_id='user'",
        ):
            validated_before = len(validated_artifacts)
            cursor.execute(revoke_sql)
            first.commit()
            assert agent_run_queue.compiled_run_claim({"id": "run", "lease_token": "lease"}) == {
                "error": "compiled_actor_access_revoked"
            }
            assert len(validated_artifacts) == validated_before
            cursor.execute(f"DELETE FROM {membership_table} WHERE user_id='user'")
            cursor.execute(f"INSERT INTO {membership_table} VALUES (%s,'user','active')", (membership_id,))
            first.commit()
            restored = agent_run_queue.compiled_run_claim({"id": "run", "lease_token": "lease"})
            assert restored and not restored.get("error")
            assert len(validated_artifacts) == validated_before + 1

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
