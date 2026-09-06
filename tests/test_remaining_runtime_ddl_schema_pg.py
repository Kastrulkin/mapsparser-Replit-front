"""PostgreSQL proof that the second retired DDL slice needs only DML rights."""

import importlib.util
import inspect
import os
from pathlib import Path
import uuid

import psycopg2
from psycopg2.extras import RealDictCursor
import pytest

from core import card_automation, parsing_runtime_config
from core.db_helpers import ensure_user_examples_table
from services import agent_domain_request_executors, operator_news_generation
from services.operator_services_optimization import _ensure_service_regeneration_tables


ROOT = Path(__file__).parents[1]


def _apply_migration(cursor, filename: str, module_name: str) -> None:
    path = ROOT / "alembic_migrations/versions" / filename
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
def ddl_free_connection():
    dsn = os.getenv("LOCALOS_TEST_DATABASE_URL")
    if not dsn:
        pytest.skip("LOCALOS_TEST_DATABASE_URL is required")
    connection = psycopg2.connect(dsn, cursor_factory=RealDictCursor)
    schema = "test_runtime_ddl_" + uuid.uuid4().hex
    cursor = connection.cursor()
    cursor.execute(f'CREATE SCHEMA "{schema}"')
    cursor.execute(f'SET search_path TO "{schema}"')
    cursor.execute("CREATE TABLE users(id TEXT PRIMARY KEY)")
    cursor.execute("CREATE TABLE businesses(id TEXT PRIMARY KEY)")
    _apply_migration(cursor, "20260420_add_business_card_automation.py", "card_automation_schema")
    _apply_migration(cursor, "20260505_add_service_regeneration_jobs.py", "service_jobs_schema")
    _apply_migration(cursor, "20260609_add_agent_communication_delivery_journal.py", "delivery_journal_schema")
    _apply_migration(cursor, "20260609_add_agent_review_publish_requests.py", "review_publish_schema")
    _apply_migration(cursor, "20260803_add_content_voice_profiles.py", "user_examples_schema")
    _apply_migration(cursor, "20260906_move_content_learning_runtime_ddl.py", "content_learning_schema")
    _apply_migration(cursor, "20260906_move_remaining_runtime_ddl.py", "remaining_runtime_schema")
    _apply_migration(cursor, "20260906_move_remaining_runtime_ddl.py", "remaining_runtime_schema_repeat")
    connection.commit()
    yield connection, schema
    connection.rollback()
    cursor.execute(f'DROP SCHEMA "{schema}" CASCADE')
    connection.commit()
    connection.close()


def test_runtime_helpers_issue_no_schema_ddl():
    helpers = (
        card_automation.ensure_card_automation_tables,
        parsing_runtime_config._ensure_runtime_settings_table,
        operator_news_generation._ensure_usernews_table,
        ensure_user_examples_table,
        _ensure_service_regeneration_tables,
        agent_domain_request_executors._ensure_communication_delivery_journal,
        agent_domain_request_executors._ensure_review_publish_requests,
    )
    for helper in helpers:
        source = inspect.getsource(helper).lower()
        assert "create table" not in source
        assert "alter table" not in source
        assert "create index" not in source


def test_runtime_helpers_and_parsing_setting_work_with_dml_only_role(ddl_free_connection):
    connection, schema = ddl_free_connection
    cursor = connection.cursor()
    role = "test_runtime_dml_" + uuid.uuid4().hex
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

        card_automation.ensure_card_automation_tables(connection)
        parsing_runtime_config._ensure_runtime_settings_table(connection)
        operator_news_generation._ensure_usernews_table(cursor)
        ensure_user_examples_table(cursor)
        _ensure_service_regeneration_tables(cursor)
        agent_domain_request_executors._ensure_communication_delivery_journal(cursor)
        agent_domain_request_executors._ensure_review_publish_requests(cursor)
        assert parsing_runtime_config.set_use_apify_map_parsing(connection, True)
        assert parsing_runtime_config.get_use_apify_map_parsing(connection) is True
        connection.commit()
    finally:
        connection.rollback()
        cursor.execute("RESET ROLE")
        cursor.execute(f'DROP OWNED BY "{role}"')
        cursor.execute(f'DROP ROLE "{role}"')
        connection.commit()
