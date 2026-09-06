"""PostgreSQL proof that growth schema setup runs only in Alembic."""

import importlib.util
import os
from pathlib import Path
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from core.growth_schema import ensure_growth_schema


ROOT = Path(__file__).parents[1]


def _upgrade(cursor, module_name: str) -> None:
    path = ROOT / "alembic_migrations/versions/20260906_move_growth_runtime_ddl.py"
    spec = importlib.util.spec_from_file_location(module_name, path)
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
def growth_schema_connection():
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("LOCALOS_TEST_DATABASE_URL is required")
    connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_growth_schema_" + uuid.uuid4().hex
    cursor = connection.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    cursor.execute("CREATE TABLE businesstypes(id TEXT PRIMARY KEY, type_key TEXT UNIQUE NOT NULL, label TEXT NOT NULL)")
    cursor.execute("INSERT INTO businesstypes(id, type_key, label) VALUES ('legacy-type', 'beauty_salon', 'Legacy salon')")
    _upgrade(cursor, "growth_schema_upgrade")
    _upgrade(cursor, "growth_schema_upgrade_repeat")
    connection.commit()
    yield connection, schema
    connection.rollback()
    cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
    connection.commit()
    connection.close()


def test_growth_migration_is_idempotent_preserves_existing_type_and_seeds_defaults(growth_schema_connection):
    connection, _schema = growth_schema_connection
    cursor = connection.cursor()
    cursor.execute("SELECT label, alert_threshold_news_days FROM businesstypes WHERE id = 'legacy-type'")
    assert cursor.fetchone() == {"label": "Legacy salon", "alert_threshold_news_days": 30}
    cursor.execute("SELECT COUNT(*) AS count FROM businesstypes")
    assert cursor.fetchone()["count"] == 10
    cursor.execute(
        """
        SELECT column_name FROM information_schema.columns
        WHERE table_schema = current_schema() AND table_name = 'growthtasks'
        """
    )
    assert {"check_logic", "reward_value", "reward_type", "tooltip", "link_url", "link_text", "is_auto_verifiable"}.issubset(
        {row["column_name"] for row in cursor.fetchall()}
    )


def test_growth_schema_check_and_dml_work_with_dml_only_role(growth_schema_connection):
    connection, schema = growth_schema_connection
    cursor = connection.cursor()
    role = "test_growth_dml_" + uuid.uuid4().hex
    cursor.execute(f'CREATE ROLE "{role}" NOLOGIN')
    cursor.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
    cursor.execute(f'GRANT SELECT, INSERT, UPDATE, DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"')
    connection.commit()
    try:
        cursor.execute(f'SET ROLE "{role}"')
        cursor.execute("SAVEPOINT ddl_denial")
        with pytest.raises(psycopg2.errors.InsufficientPrivilege):
            cursor.execute("CREATE TABLE forbidden_growth_ddl(id INTEGER)")
        cursor.execute("ROLLBACK TO SAVEPOINT ddl_denial")
        ensure_growth_schema(_Database(connection))
        cursor.execute(
            """
            INSERT INTO businessoptimizationwizard(id, business_id, step, data, completed)
            VALUES ('wizard-1', 'business-1', 2, '{}', 0)
            """
        )
        connection.commit()
    finally:
        connection.rollback()
        cursor.execute("RESET ROLE")
        cursor.execute(f'DROP OWNED BY "{role}"')
        cursor.execute(f'DROP ROLE "{role}"')
        connection.commit()


def test_growth_schema_check_reports_missing_column(growth_schema_connection):
    connection, _schema = growth_schema_connection
    cursor = connection.cursor()
    cursor.execute("ALTER TABLE growthtasks DROP COLUMN check_logic")
    connection.commit()
    with pytest.raises(RuntimeError, match="growthtasks: check_logic"):
        ensure_growth_schema(_Database(connection))
