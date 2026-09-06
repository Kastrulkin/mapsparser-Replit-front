"""Isolated PostgreSQL proof for the first runtime-DDL retirement slice."""
import importlib.util
import os
from pathlib import Path
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from core import ai_learning
from services import content_plan_service


@pytest.fixture
def schema_connection(monkeypatch):
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("LOCALOS_TEST_DATABASE_URL is required")
    connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_content_learning_" + uuid.uuid4().hex
    cursor = connection.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    cursor.execute("""CREATE TABLE usernews (
        id TEXT PRIMARY KEY, user_id TEXT NOT NULL, service_id TEXT, source_text TEXT,
        generated_text TEXT NOT NULL, approved INTEGER DEFAULT 0,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, business_id TEXT
    )""")
    cursor.execute("INSERT INTO usernews(id,user_id,generated_text,business_id) VALUES ('old-news','user-1','legacy','business-1')")
    cursor.execute("""CREATE TABLE contentplans (
        id TEXT PRIMARY KEY, business_id TEXT, scope_type TEXT, plan_status TEXT,
        created_at TIMESTAMP, updated_at TIMESTAMP
    )""")
    cursor.execute("""CREATE TABLE contentplanitems (
        id TEXT PRIMARY KEY, plan_id TEXT, business_id TEXT, status TEXT, seo_views INTEGER,
        metadata_json JSONB, created_at TIMESTAMP, updated_at TIMESTAMP
    )""")
    connection.commit()
    monkeypatch.setenv("DATABASE_URL", dsn)
    monkeypatch.setenv("LOCALOS_SCHEMA_NAME", schema)
    yield connection, schema
    connection.rollback()
    cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
    connection.commit()
    connection.close()


def _upgrade(cursor):
    path = Path(__file__).parents[1] / "alembic_migrations/versions/20260906_move_content_learning_runtime_ddl.py"
    spec = importlib.util.spec_from_file_location("content_learning_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    previous_execute = migration.op.execute
    try:
        migration.op.execute = cursor.execute
        migration.upgrade()
    finally:
        migration.op.execute = previous_execute


def test_content_learning_migration_is_idempotent_and_preserves_legacy_data(schema_connection):
    connection, _schema = schema_connection
    cursor = connection.cursor()
    _upgrade(cursor)
    _upgrade(cursor)
    cursor.execute("SELECT generated_text,business_id,edited_before_approve,prompt_key FROM usernews WHERE id='old-news'")
    assert cursor.fetchone() == {"generated_text": "legacy", "business_id": "business-1", "edited_before_approve": False, "prompt_key": None}
    cursor.execute("SELECT indexname FROM pg_indexes WHERE schemaname=current_schema() AND tablename='ailearningevents'")
    assert {"idx_ailearningevents_created_at", "idx_ailearningevents_capability_intent", "idx_ailearningevents_user_business"}.issubset({row["indexname"] for row in cursor.fetchall()})


def test_schema_checker_rejects_missing_required_column(schema_connection):
    connection, schema = schema_connection
    cursor = connection.cursor()
    _upgrade(cursor)
    connection.commit()
    from scripts import check_content_learning_schema
    assert check_content_learning_schema.main() == 0
    cursor.execute("ALTER TABLE usernews DROP COLUMN prompt_version")
    connection.commit()
    assert check_content_learning_schema.main() == 1
    assert schema


class _NoDdlCursor:
    def __init__(self):
        self.queries = []

    def execute(self, query, _params=None):
        self.queries.append(str(query))
        assert "create " not in str(query).lower()
        assert "alter " not in str(query).lower()

    def fetchone(self):
        return {"to_regclass": "ailearningevents"}


class _NoDdlConnection:
    def __init__(self):
        self.cursor_value = _NoDdlCursor()

    def cursor(self):
        return self.cursor_value


def test_runtime_schema_helpers_are_read_only_after_migration():
    connection = _NoDdlConnection()
    ai_learning.ensure_ai_learning_events_table(connection)
    assert connection.cursor_value.queries == ["SELECT to_regclass('ailearningevents')"]
    cursor = _NoDdlCursor()
    cursor.fetchone = lambda: {"has_plans": True, "has_items": True, "has_item_metadata": True}
    content_plan_service.ensure_content_plan_tables(cursor)
    assert len(cursor.queries) == 1


def test_learning_write_and_content_checks_work_with_a_real_dml_role(schema_connection):
    connection, schema = schema_connection
    cursor = connection.cursor()
    _upgrade(cursor)
    role = "test_content_dml_" + uuid.uuid4().hex
    cursor.execute(f'CREATE ROLE "{role}" NOLOGIN')
    cursor.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
    cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"')
    connection.commit()
    try:
        cursor.execute(f'SET ROLE "{role}"')
        cursor.execute("SAVEPOINT ddl_denial")
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cursor.execute("CREATE TABLE forbidden_runtime_ddl(id INTEGER)")
        cursor.execute("ROLLBACK TO SAVEPOINT ddl_denial")
        content_plan_service.ensure_content_plan_tables(cursor)
        content_plan_service._ensure_usernews_table(cursor)
        assert ai_learning.record_ai_learning_event(capability="table_check", event_type="approved", conn=connection)
        cursor.execute("SELECT COUNT(*) FROM ailearningevents")
        assert cursor.fetchone()["count"] == 1
        connection.commit()
    finally:
        connection.rollback()
        cursor.execute("RESET ROLE")
        cursor.execute(f'DROP OWNED BY "{role}"')
        cursor.execute(f'DROP ROLE "{role}"')
        connection.commit()
