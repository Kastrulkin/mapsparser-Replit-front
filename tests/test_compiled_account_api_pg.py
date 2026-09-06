"""Router-level account checks for model-backed compiled commands."""
import os
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest
from flask import Flask


def test_compiled_api_checks_current_account_before_and_after_provider(monkeypatch):
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires isolated PostgreSQL")
    connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_compiled_account_api_" + uuid.uuid4().hex
    cursor = connection.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    cursor.execute("CREATE TABLE users(id TEXT PRIMARY KEY,is_active BOOLEAN,is_verified BOOLEAN)")
    cursor.execute("INSERT INTO users VALUES ('user',FALSE,TRUE)")
    cursor.execute("""CREATE TABLE compiled_generation_requests(
        id TEXT PRIMARY KEY,user_id TEXT,business_id TEXT,blueprint_id TEXT,idempotency_key TEXT,
        input_digest TEXT,state TEXT,result_version_id TEXT,error_code TEXT,
        created_at TIMESTAMPTZ DEFAULT NOW(),updated_at TIMESTAMPTZ DEFAULT NOW(),completed_at TIMESTAMPTZ
    )""")
    cursor.execute("CREATE UNIQUE INDEX account_request_key ON compiled_generation_requests(user_id,business_id,blueprint_id,idempotency_key)")
    connection.commit()
    try:
        from api import agent_blueprints_api

        class Database:
            def __init__(self): self.conn = connection
            def close(self): return None

        calls = []
        def generator(*_args, **_kwargs):
            calls.append("model")
            other_connection = psycopg2.connect(dsn)
            try:
                other_cursor = other_connection.cursor()
                other_cursor.execute(f'SET search_path TO "{schema}"')
                other_cursor.execute("UPDATE users SET is_active=FALSE WHERE id='user'")
                other_connection.commit()
            finally:
                other_connection.close()
            return {"status": "ready", "candidate": {
                "source": "def process(input_payload):\n    return {}\n",
                "manifest": {"kind": "localos.python_transform.v1", "input_schema": {"type": "object"}, "output_schema": {"type": "object"}, "runtime_version": "python-3.12-restricted-v1", "dependencies": []},
                "fixtures": [{"input": {}, "expected": {}, "source": "user"}],
            }}

        monkeypatch.setenv("COMPILED_SCRIPT_ADVANCED_ENABLED", "true")
        monkeypatch.setenv("COMPILED_SCRIPT_PREVIEW_ENABLED", "true")
        monkeypatch.setenv("COMPILED_SCRIPT_PILOT_BUSINESS_IDS", "business")
        monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST", "sha256:" + "a" * 64)
        monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", Database)
        monkeypatch.setattr(agent_blueprints_api, "_require_auth", lambda: ({"user_id": "user", "is_superadmin": True}, None))
        monkeypatch.setattr(agent_blueprints_api, "_require_blueprint_access", lambda *_args: ({"id": "blueprint", "business_id": "business", "metadata_json": {}}, None))
        monkeypatch.setattr(agent_blueprints_api, "_resolve_candidate_version", lambda *_args: {})
        monkeypatch.setattr(agent_blueprints_api, "generate_candidate_from_description", generator)
        monkeypatch.setattr(agent_blueprints_api, "_insert_version", lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("deactivated account must not persist candidate")))
        app = Flask(__name__)
        body = {"description": "x", "fixtures": [{"input": {}, "expected": {}, "source": "user"}], "idempotency_key": "same"}
        with app.test_request_context(method="POST", json=body):
            response, status = agent_blueprints_api.compile_agent_blueprint_script("blueprint")
        assert status == 403
        assert response.get_json()["code"] == "COMPILED_ACCOUNT_NOT_ALLOWED"
        assert calls == []
        connection.cursor().execute("UPDATE users SET is_active=TRUE,is_verified=FALSE WHERE id='user'")
        connection.commit()
        with app.test_request_context(method="POST", json=body):
            response, status = agent_blueprints_api.compile_agent_blueprint_script("blueprint")
        assert status == 403
        assert response.get_json()["code"] == "COMPILED_ACCOUNT_NOT_ALLOWED"
        assert calls == []
        for endpoint in (agent_blueprints_api.create_agent_compiled_snapshot, agent_blueprints_api.approve_agent_blueprint_script):
            with app.test_request_context(method="POST", json={}):
                response, status = endpoint("blueprint")
            assert status == 403
            assert response.get_json()["code"] == "COMPILED_ACCOUNT_NOT_ALLOWED"

        connection.cursor().execute("UPDATE users SET is_active=TRUE,is_verified=TRUE WHERE id='user'")
        connection.commit()
        with app.test_request_context(method="POST", json=body):
            response, status = agent_blueprints_api.compile_agent_blueprint_script("blueprint")
        assert status == 403
        assert response.get_json()["code"] == "COMPILED_ACCOUNT_NOT_ALLOWED"
        assert calls == ["model"]
        cursor.execute("SELECT state,error_code FROM compiled_generation_requests WHERE idempotency_key='same'")
        failed = cursor.fetchone()
        assert failed["state"] == "failed"
        assert failed["error_code"] == "COMPILED_GENERATION_ACCOUNT_CHANGED"

        connection.cursor().execute("UPDATE users SET is_active=TRUE WHERE id='user'")
        connection.commit()
        with app.test_request_context(method="POST", json=body):
            response, status = agent_blueprints_api.compile_agent_blueprint_script("blueprint")
        assert status == 422
        assert calls == ["model"]
    finally:
        connection.rollback()
        cursor = connection.cursor()
        cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
        connection.commit()
        connection.close()
