"""An accepted compiled run remains replayable after its input snapshot expires."""
import os
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest
from flask import Flask


def test_terminal_run_replay_bypasses_expired_snapshot_but_new_intent_does_not(monkeypatch):
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires isolated PostgreSQL")
    connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_compiled_replay_" + uuid.uuid4().hex
    cursor = connection.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    cursor.execute("CREATE TABLE users(id TEXT PRIMARY KEY,is_active BOOLEAN,is_verified BOOLEAN)")
    cursor.execute("INSERT INTO users VALUES ('user',TRUE,TRUE)")
    cursor.execute("""CREATE TABLE agent_runs(
        id TEXT PRIMARY KEY,business_id TEXT,blueprint_id TEXT,blueprint_version_id TEXT,
        input_snapshot_id TEXT,idempotency_key TEXT,status TEXT
    )""")
    cursor.execute("INSERT INTO agent_runs VALUES ('run','business','blueprint','version','purged','same','completed')")
    connection.commit()
    try:
        from api import agent_blueprints_api
        from services.compiled_input_snapshots import SnapshotUnavailable

        class Database:
            def __init__(self):
                self.conn = connection

            def close(self):
                return None

        class Runner:
            def __init__(self, _cursor):
                return None

            def load_run(self, run_id, _user_data):
                return {"id": run_id, "status": "completed"}

        def expired(*_args, **_kwargs):
            raise SnapshotUnavailable("expired")

        monkeypatch.setenv("COMPILED_SCRIPT_EXECUTE_ENABLED", "true")
        monkeypatch.setenv("COMPILED_SCRIPT_PILOT_BUSINESS_IDS", "business")
        monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", Database)
        monkeypatch.setattr(agent_blueprints_api, "AgentBlueprintRunner", Runner)
        monkeypatch.setattr(agent_blueprints_api, "_require_auth", lambda: ({"user_id": "user"}, None))
        monkeypatch.setattr(agent_blueprints_api, "_require_blueprint_access", lambda *_args: ({"id": "blueprint", "business_id": "business"}, None))
        monkeypatch.setattr(agent_blueprints_api, "_load_blueprint_version_for_blueprint", lambda *_args: {"id": "version", "compiled_state": "approved", "compiled_approved_at": True, "compiled_approved_by_user_id": "user"})
        monkeypatch.setattr("services.compiled_input_snapshots.resolve_snapshot", expired)
        app = Flask(__name__)
        with app.test_request_context(method="POST", json={"version_id": "version", "snapshot_id": "purged", "idempotency_key": "same"}):
            response, status = agent_blueprints_api.run_agent_blueprint_script("blueprint")
        assert status == 200
        assert response.get_json()["run"]["id"] == "run"
        with app.test_request_context(method="POST", json={"version_id": "version", "snapshot_id": "other", "idempotency_key": "same"}):
            response, status = agent_blueprints_api.run_agent_blueprint_script("blueprint")
        assert status == 409
        assert response.get_json()["code"] == "COMPILED_RUN_IDEMPOTENCY_CONFLICT"
        with app.test_request_context(method="POST", json={"version_id": "version", "snapshot_id": "purged", "idempotency_key": "new"}):
            response, status = agent_blueprints_api.run_agent_blueprint_script("blueprint")
        assert status == 409
        assert response.get_json()["code"] == "COMPILED_INPUT_SNAPSHOT_UNAVAILABLE"
    finally:
        connection.rollback()
        cursor = connection.cursor()
        cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
        connection.commit()
        connection.close()
