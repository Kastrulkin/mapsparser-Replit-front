"""PostgreSQL proof for the bounded 009 runtime-DDL retirement slice."""

import importlib.util
import os
from pathlib import Path
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from ai_agents_api import _ensure_ai_agents_schema
from api.wordstat_api import _ensure_custom_table, _ensure_excluded_table, _ensure_negative_table, _save_live_wordstat_items
from core.industry_pattern_recalibration import ensure_industry_pattern_tables
from services.agent_capability_handlers import (
    _ensure_communication_request_table,
    _ensure_review_reply_draft_table,
    _ensure_service_optimization_request_table,
    _ensure_sheet_operation_request_table,
)


ROOT = Path(__file__).parents[1]


def _upgrade(cursor, filename: str, module_name: str) -> None:
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "alembic_migrations/versions" / filename)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    previous_execute = migration.op.execute
    try:
        migration.op.execute = cursor.execute
        migration.upgrade()
    finally:
        migration.op.execute = previous_execute


class _Database:
    def __init__(self, connection):
        self.conn = connection


@pytest.fixture
def schema_connection():
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("LOCALOS_TEST_DATABASE_URL is required")
    connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_runtime_ddl_009_" + uuid.uuid4().hex
    cursor = connection.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    cursor.execute("CREATE TABLE businesses(id TEXT PRIMARY KEY)")
    cursor.execute("CREATE TABLE aiagents(id TEXT PRIMARY KEY, name TEXT NOT NULL, type TEXT NOT NULL)")
    cursor.execute("INSERT INTO aiagents(id, name, type) VALUES ('legacy-agent', 'Legacy agent', 'support')")
    _upgrade(cursor, "20260420_add_business_card_automation.py", "card_schema")
    _upgrade(cursor, "20260506_add_industry_pattern_tables.py", "industry_schema")
    _upgrade(cursor, "20260609_add_agent_domain_request_tables.py", "agent_domain_schema")
    _upgrade(cursor, "20260609_add_custom_agent_integration_tables.py", "agent_sheet_schema")
    _upgrade(cursor, "20260609_add_agent_service_optimization_diff.py", "agent_diff_schema")
    _upgrade(cursor, "20260906_move_agent_keyword_pattern_runtime_ddl.py", "runtime_009_schema")
    _upgrade(cursor, "20260906_move_agent_keyword_pattern_runtime_ddl.py", "runtime_009_schema_repeat")
    connection.commit()
    yield connection, schema
    connection.rollback()
    cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
    connection.commit()
    connection.close()


def test_009_migration_is_idempotent_and_preserves_legacy_schema(schema_connection):
    connection, _schema = schema_connection
    cursor = connection.cursor()
    cursor.execute("SELECT name, type FROM aiagents WHERE id = 'booking_agent_default'")
    assert cursor.fetchone() == {"name": "Booking Agent", "type": "booking"}
    cursor.execute("SELECT name, type, is_active FROM aiagents WHERE id = 'legacy-agent'")
    assert cursor.fetchone() == {"name": "Legacy agent", "type": "support", "is_active": 1}
    cursor.execute("SELECT to_regclass('wordstatkeywordscustom') AS table_name")
    assert cursor.fetchone()["table_name"] == "wordstatkeywordscustom"


def test_009_runtime_helpers_work_with_dml_only_role(schema_connection):
    connection, schema = schema_connection
    cursor = connection.cursor()
    role = "test_runtime_009_dml_" + uuid.uuid4().hex
    cursor.execute(f'CREATE ROLE "{role}" NOLOGIN')
    cursor.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
    cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"')
    connection.commit()
    try:
        cursor.execute(f'SET ROLE "{role}"')
        cursor.execute("SAVEPOINT ddl_denial")
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cursor.execute("CREATE TABLE forbidden_runtime_009(id INTEGER)")
        cursor.execute("ROLLBACK TO SAVEPOINT ddl_denial")
        ensure_industry_pattern_tables(connection)
        _ensure_ai_agents_schema(_Database(connection))
        _ensure_excluded_table(cursor)
        _ensure_custom_table(cursor)
        _ensure_negative_table(cursor)
        _save_live_wordstat_items(cursor, [{"keyword": "салон", "views": 12, "category": "beauty"}])
        _ensure_communication_request_table(cursor)
        _ensure_service_optimization_request_table(cursor)
        _ensure_review_reply_draft_table(cursor)
        _ensure_sheet_operation_request_table(cursor)
        connection.commit()
    finally:
        connection.rollback()
        cursor.execute("RESET ROLE")
        cursor.execute(f'DROP OWNED BY "{role}"')
        cursor.execute(f'DROP ROLE "{role}"')
        connection.commit()
