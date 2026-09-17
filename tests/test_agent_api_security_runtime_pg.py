"""Security request paths use the existing Alembic schema with DML-only rights."""
import importlib.util
import os
from pathlib import Path
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from core import agent_api_security


@pytest.fixture
def security_schema():
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("requires isolated PostgreSQL")
    params = psycopg2.extensions.parse_dsn(dsn)
    assert "test" in params.get("dbname", "")
    assert params.get("host", "").startswith(("/tmp/", "/private/tmp/")) or params.get("host") in {"localhost", "127.0.0.1", "postgres"}
    connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_agent_security_" + uuid.uuid4().hex
    cursor = connection.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    path = Path(__file__).parents[1] / "alembic_migrations/versions/20260514_add_agent_api_security.py"
    spec = importlib.util.spec_from_file_location("security_schema_migration", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)

    class Operations:
        def execute(self, query):
            cursor.execute(query)

    migration.op = Operations()
    migration.upgrade()
    migration.upgrade()
    connection.commit()
    try:
        yield connection, schema
    finally:
        connection.rollback()
        cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
        connection.commit()
        connection.close()


def test_existing_migration_has_all_ten_runtime_indexes(security_schema):
    connection, _schema = security_schema
    cursor = connection.cursor()
    cursor.execute("SELECT indexname FROM pg_indexes WHERE schemaname=current_schema() AND indexname NOT LIKE %s", ("%_pkey",))
    assert {row["indexname"] for row in cursor.fetchall()} == {
        "uq_agent_clients_key_hash", "idx_agent_clients_owner", "idx_agent_clients_status",
        "idx_agent_action_ledger_client_created", "idx_agent_action_ledger_business_created",
        "idx_agent_action_ledger_risk", "idx_agent_action_ledger_status",
        "idx_agent_discovery_events_created", "idx_agent_discovery_events_family_created",
        "idx_agent_discovery_events_type_created",
    }


def test_security_client_discovery_and_ledger_work_with_dml_only_role(security_schema):
    connection, schema = security_schema
    cursor = connection.cursor()
    role = "test_agent_security_dml_" + uuid.uuid4().hex
    cursor.execute(f'CREATE ROLE "{role}" NOLOGIN')
    cursor.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
    cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"')
    connection.commit()
    try:
        cursor.execute(f'SET ROLE "{role}"')
        cursor.execute("SAVEPOINT caller_transaction")
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cursor.execute("CREATE TABLE forbidden_runtime_table(id TEXT)")
        cursor.execute("ROLLBACK TO SAVEPOINT caller_transaction")
        client = agent_api_security.create_agent_client(cursor, owner_user_id="synthetic-user", organization_name="Test", contact_email="test@example.invalid")
        loaded = agent_api_security.load_agent_client_by_key(cursor, client["agent_key"])
        assert loaded["id"] == client["client_id"]
        agent_api_security.mark_agent_seen(cursor, loaded["id"])
        event_id = agent_api_security.log_agent_discovery_event(cursor, "/llms.txt", "GET", 200, "test", "127.0.0.1", "")
        ledger_id = agent_api_security.log_agent_action(cursor, agent_client_id=loaded["id"], business_id="synthetic-business", action_type="test_read")
        cursor.execute("SELECT id FROM agent_discovery_events")
        assert cursor.fetchone()["id"] == event_id
        cursor.execute("SELECT id FROM agent_action_ledger")
        assert cursor.fetchone()["id"] == ledger_id
        cursor.execute("ROLLBACK TO SAVEPOINT caller_transaction")
        cursor.execute("SELECT COUNT(*) total FROM agent_action_ledger")
        assert cursor.fetchone()["total"] == 0
        cursor.execute("SELECT COUNT(*) total FROM agent_clients")
        assert cursor.fetchone()["total"] == 0
    finally:
        connection.rollback()
        cursor.execute("RESET ROLE")
        cursor.execute(f'DROP OWNED BY "{role}"')
        cursor.execute(f'DROP ROLE "{role}"')
        connection.commit()


@pytest.mark.parametrize("statement, expected", [
    ("DROP TABLE agent_discovery_events", "agent_discovery_events: id"),
    ("ALTER TABLE agent_action_ledger DROP COLUMN approval_id", "agent_action_ledger: approval_id"),
])
def test_missing_schema_fails_clearly_without_ddl_or_commit(security_schema, statement, expected):
    connection, _schema = security_schema
    cursor = connection.cursor()
    cursor.execute(statement)
    cursor.execute("SAVEPOINT caller_transaction")
    with pytest.raises(RuntimeError, match=expected):
        agent_api_security.ensure_agent_security_tables(cursor)
    cursor.execute("ROLLBACK TO SAVEPOINT caller_transaction")
