"""PostgreSQL proof for ActionOrchestrator's Alembic-owned schema."""

import importlib.util
import os
from pathlib import Path
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from core.action_ledger import ensure_ledger_tables, write_ledger_entry
from core.action_orchestrator import ActionOrchestrator


ROOT = Path(__file__).parents[1]


def _upgrade(cursor, module_name: str) -> None:
    path = ROOT / "alembic_migrations/versions/20260906_move_action_orchestrator_runtime_ddl.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    previous_execute = migration.op.execute
    try:
        migration.op.execute = cursor.execute
        migration.upgrade()
    finally:
        migration.op.execute = previous_execute


@pytest.fixture
def action_schema_connection():
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("LOCALOS_TEST_DATABASE_URL is required")
    connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_action_schema_" + uuid.uuid4().hex
    cursor = connection.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    # This is the pre-deduplication outbox shape created by the old runtime.
    cursor.execute(
        """
        CREATE TABLE action_callback_outbox (
            id TEXT PRIMARY KEY, action_id TEXT NOT NULL, tenant_id TEXT NOT NULL,
            callback_url TEXT NOT NULL, event_type TEXT NOT NULL, payload_json JSONB NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending', attempts INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 5,
            next_attempt_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            last_error TEXT, locked_at TIMESTAMP, sent_at TIMESTAMP,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    cursor.execute(
        """
        INSERT INTO action_callback_outbox
            (id, action_id, tenant_id, callback_url, event_type, payload_json)
        VALUES ('legacy-outbox', 'legacy-action', 'tenant-1', 'https://example.com/callback', 'completed', '{}')
        """
    )
    _upgrade(cursor, "action_schema_upgrade")
    _upgrade(cursor, "action_schema_upgrade_repeat")
    connection.commit()
    yield connection, schema
    connection.rollback()
    cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
    connection.commit()
    connection.close()


def test_action_schema_migration_is_idempotent_and_preserves_legacy_outbox(action_schema_connection):
    connection, _schema = action_schema_connection
    cursor = connection.cursor()
    cursor.execute("SELECT id, action_id, dedupe_key FROM action_callback_outbox WHERE id = 'legacy-outbox'")
    assert cursor.fetchone() == {"id": "legacy-outbox", "action_id": "legacy-action", "dedupe_key": None}
    cursor.execute(
        """
        SELECT indexname FROM pg_indexes
        WHERE schemaname = current_schema() AND tablename = 'action_callback_outbox'
        """
    )
    assert {
        "idx_action_callback_outbox_status_next",
        "idx_action_callback_outbox_action_id",
        "uq_action_callback_outbox_dedupe_key",
    }.issubset({row["indexname"] for row in cursor.fetchall()})


def test_runtime_schema_checks_and_ledger_write_work_with_dml_only_role(action_schema_connection):
    connection, schema = action_schema_connection
    cursor = connection.cursor()
    role = "test_action_dml_" + uuid.uuid4().hex
    cursor.execute(f'CREATE ROLE "{role}" NOLOGIN')
    cursor.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
    cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"')
    connection.commit()
    try:
        cursor.execute(f'SET ROLE "{role}"')
        cursor.execute("SAVEPOINT ddl_denial")
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cursor.execute("CREATE TABLE forbidden_action_ddl(id INTEGER)")
        cursor.execute("ROLLBACK TO SAVEPOINT ddl_denial")

        orchestrator = ActionOrchestrator({})
        orchestrator.ensure_tables(cursor)
        ensure_ledger_tables(cursor)
        entry_id = write_ledger_entry(
            cursor,
            action_id="action-1",
            tenant_id="tenant-1",
            entry_type="reserve",
            tokens_out=42,
        )
        cursor.execute("SELECT tokens_out FROM billing_ledger WHERE id = %s", (entry_id,))
        assert cursor.fetchone()["tokens_out"] == 42
        connection.commit()
    finally:
        connection.rollback()
        cursor.execute("RESET ROLE")
        cursor.execute(f'DROP OWNED BY "{role}"')
        cursor.execute(f'DROP ROLE "{role}"')
        connection.commit()


def test_runtime_schema_check_fails_with_actionable_missing_column(action_schema_connection):
    connection, _schema = action_schema_connection
    cursor = connection.cursor()
    cursor.execute("ALTER TABLE action_requests DROP COLUMN capability")
    connection.commit()
    with pytest.raises(RuntimeError, match="action_requests: capability"):
        ActionOrchestrator({}).ensure_tables(cursor)
