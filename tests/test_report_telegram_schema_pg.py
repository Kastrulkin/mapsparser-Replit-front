"""Run the actual schema helpers without importing the live Flask/bot singleton."""
import ast
import importlib.util
import os
from pathlib import Path
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from core.db_helpers import assert_schema_columns


ROOT = Path(__file__).parents[1]
HELPERS = {
    "src/telegram_bot.py": ["_ensure_callback_recovery_history_table", "_ensure_support_export_send_history_table"],
    "src/legacy_routes/report_pipeline.py": ["_ensure_public_report_requests_table"],
}


def load_helpers():
    namespace = {"assert_schema_columns": assert_schema_columns}
    for filename, names in HELPERS.items():
        tree = ast.parse((ROOT / filename).read_text())
        nodes = [node for node in tree.body if isinstance(node, ast.FunctionDef) and node.name in names]
        assert len(nodes) == len(names)
        exec(compile(ast.Module(body=nodes, type_ignores=[]), filename, "exec"), namespace)
    return namespace


def upgrade(cursor):
    path = ROOT / "alembic_migrations/versions/20260906_move_report_telegram_runtime_ddl.py"
    spec = importlib.util.spec_from_file_location("history_schema_upgrade", path)
    migration = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(migration)
    original = migration.op.execute
    try:
        migration.op.execute = cursor.execute
        migration.upgrade()
    finally:
        migration.op.execute = original


@pytest.fixture
def database():
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("LOCALOS_TEST_DATABASE_URL is required")
    connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_report_history_" + uuid.uuid4().hex
    cursor = connection.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    upgrade(cursor)
    cursor.execute("INSERT INTO publicreportrequests(slug,email,source_url,page_json) VALUES ('preserved','owner@example.test','https://example.test','{}')")
    cursor.execute("INSERT INTO callback_recovery_history(id,tenant_id,triggered_by,report_text) VALUES ('preserved','tenant','owner','original')")
    upgrade(cursor)
    connection.commit()
    yield connection, schema
    connection.rollback()
    cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
    connection.commit()
    connection.close()


def test_history_migration_defaults_indexes_and_existing_rows_survive_repeat(database):
    connection, _schema = database
    cursor = connection.cursor()
    cursor.execute("SELECT status,source FROM publicreportrequests WHERE slug='preserved'")
    assert cursor.fetchone() == {"status": "queued", "source": "apify_yandex"}
    cursor.execute("SELECT include_retry,send_telegram_report,action_ids_json,report_text FROM callback_recovery_history WHERE id='preserved'")
    assert cursor.fetchone() == {"include_retry": True, "send_telegram_report": False, "action_ids_json": [], "report_text": "original"}
    cursor.execute("SELECT indexname FROM pg_indexes WHERE schemaname=current_schema()")
    names = {row["indexname"] for row in cursor.fetchall()}
    assert {"idx_callback_recovery_history_tenant_created", "idx_support_export_send_history_tenant_created"} <= names


def test_runtime_history_helpers_and_writes_work_without_ddl_and_do_not_commit(database):
    connection, schema = database
    cursor = connection.cursor()
    role = "test_report_history_dml_" + uuid.uuid4().hex
    cursor.execute(f'CREATE ROLE "{role}" NOLOGIN')
    cursor.execute(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"')
    cursor.execute(f'GRANT SELECT,INSERT,UPDATE,DELETE ON ALL TABLES IN SCHEMA "{schema}" TO "{role}"')
    connection.commit()
    try:
        cursor.execute(f'SET ROLE "{role}"')
        for query in ("CREATE TABLE forbidden_history(id INT)", "ALTER TABLE publicreportrequests ADD COLUMN forbidden INT", "DROP TABLE publicreportrequests"):
            cursor.execute("SAVEPOINT ddl_denied")
            with pytest.raises(psycopg2.errors.InsufficientPrivilege):
                cursor.execute(query)
            cursor.execute("ROLLBACK TO SAVEPOINT ddl_denied")
        cursor.execute("SAVEPOINT caller_transaction")
        helpers = load_helpers()
        helpers["_ensure_callback_recovery_history_table"](cursor)
        helpers["_ensure_support_export_send_history_table"](cursor)
        helpers["_ensure_public_report_requests_table"](connection)
        cursor.execute("INSERT INTO support_export_send_history(id,tenant_id,triggered_by,report_text) VALUES ('new','tenant','owner','draft report')")
        cursor.execute("ROLLBACK TO SAVEPOINT caller_transaction")
        cursor.execute("SELECT COUNT(*) AS count FROM support_export_send_history")
        assert cursor.fetchone()["count"] == 0
    finally:
        connection.rollback()
        cursor.execute("RESET ROLE")
        cursor.execute(f'DROP OWNED BY "{role}"')
        cursor.execute(f'DROP ROLE "{role}"')
        connection.commit()


def test_runtime_history_missing_column_fails_with_migration_guidance(database):
    connection, _schema = database
    cursor = connection.cursor()
    cursor.execute("ALTER TABLE support_export_send_history DROP COLUMN target_ids_json")
    with pytest.raises(RuntimeError, match="support_export_send_history: target_ids_json"):
        load_helpers()["_ensure_support_export_send_history_table"](cursor)


def test_telegram_runtime_no_longer_contains_a_usernews_bootstrap():
    tree = ast.parse((ROOT / "src/telegram_bot.py").read_text())
    ddl = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
           and isinstance(node.value, str) and "CREATE TABLE" in node.value.upper()]
    assert ddl == []
