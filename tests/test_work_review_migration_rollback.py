from pathlib import Path
import importlib
import os
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit, urlunsplit
import uuid

from alembic.migration import MigrationContext
from alembic.operations import Operations
import psycopg2
import pytest
from sqlalchemy import create_engine


pytestmark = pytest.mark.integration

PROJECT_ROOT = Path(__file__).resolve().parents[1]
WORK_REVIEW_REVISION = "20260914_work_review"
PRE_WORK_REVIEW_REVISION = "20260914_riderra_runs"


def _dsn(postgres_container):
    return postgres_container.get_connection_url().replace(
        "postgresql+psycopg2://", "postgresql://", 1
    )


def _database_url(database_url, database_name):
    parts = urlsplit(database_url)
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def _connect(database_url):
    return psycopg2.connect(database_url)


def _close(cursor, connection):
    if cursor is not None:
        cursor.close()
    if connection is not None:
        connection.close()


def _migrate(database_url, action, revision):
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    environment["FLASK_APP"] = "src.main:app"
    environment["PYTHONPATH"] = os.pathsep.join([str(PROJECT_ROOT / "src"), str(PROJECT_ROOT)])
    return subprocess.run(
        [sys.executable, "-m", "flask", "db", action, revision],
        cwd=PROJECT_ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )


@pytest.fixture(scope="module")
def work_review_database(postgres_container):
    database_name = f"work_review_rollback_{uuid.uuid4().hex}"
    admin_url = _database_url(_dsn(postgres_container), "postgres")
    database_url = _database_url(_dsn(postgres_container), database_name)
    connection = _connect(admin_url)
    cursor = connection.cursor()
    try:
        connection.autocommit = True
        cursor.execute(f"CREATE DATABASE {database_name}")
    finally:
        _close(cursor, connection)
    try:
        result = _migrate(database_url, "upgrade", WORK_REVIEW_REVISION)
        assert result.returncode == 0, result.stderr or result.stdout
        yield database_url
    finally:
        connection = _connect(admin_url)
        cursor = connection.cursor()
        try:
            connection.autocommit = True
            cursor.execute(f"DROP DATABASE IF EXISTS {database_name} WITH (FORCE)")
        finally:
            _close(cursor, connection)


def _scalar(database_url, statement, parameters=()):
    connection = _connect(database_url)
    cursor = connection.cursor()
    try:
        cursor.execute(statement, parameters)
        return cursor.fetchone()[0]
    finally:
        _close(cursor, connection)


def _execute(database_url, statement, parameters=()):
    connection = _connect(database_url)
    cursor = connection.cursor()
    try:
        cursor.execute(statement, parameters)
        connection.commit()
    finally:
        _close(cursor, connection)


def _seed_business(database_url):
    user_id = f"work-review-user-{uuid.uuid4()}"
    business_id = f"work-review-business-{uuid.uuid4()}"
    _execute(database_url, "INSERT INTO users (id, email) VALUES (%s, %s)", (user_id, f"{user_id}@test.local"))
    _execute(
        database_url,
        "INSERT INTO businesses (id, owner_id, name) VALUES (%s, %s, 'Work review')",
        (business_id, user_id),
    )
    return user_id, business_id


def test_empty_work_review_schema_downgrades_without_cascade(work_review_database):
    upgrade = _migrate(work_review_database, "upgrade", WORK_REVIEW_REVISION)
    assert upgrade.returncode == 0, upgrade.stderr or upgrade.stdout
    result = _migrate(work_review_database, "downgrade", PRE_WORK_REVIEW_REVISION)

    assert result.returncode == 0, result.stderr or result.stdout
    assert _scalar(
        work_review_database,
        "SELECT to_regclass('public.business_work_links') IS NULL",
    )
    assert _scalar(
        work_review_database,
        "SELECT to_regclass('public.business_work_reviewers') IS NULL",
    )
    assert _scalar(
        work_review_database,
        "SELECT to_regclass('public.business_work_digest_settings') IS NULL",
    )
    assert _scalar(
        work_review_database,
        "SELECT NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'business_work_journal' AND column_name = 'review_status')",
    )
    constraint = _scalar(
        work_review_database,
        "SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conrelid = 'journey_actions'::regclass AND conname = 'ck_journey_actions_flow'",
    )
    assert "work_journal" not in constraint


@pytest.mark.parametrize(
    "kind",
    ["reviewer", "link", "settings", "journal_fields", "work_journal_action"],
)
def test_work_review_data_blocks_downgrade_and_remains_present(work_review_database, kind):
    result = _migrate(work_review_database, "upgrade", WORK_REVIEW_REVISION)
    assert result.returncode == 0, result.stderr or result.stdout
    user_id = f"work-review-user-{uuid.uuid4()}"
    business_id = f"work-review-business-{uuid.uuid4()}"
    journal_id = f"work-review-journal-{uuid.uuid4()}"
    action_id = str(uuid.uuid4())
    connection = _connect(work_review_database)
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO users (id, email) VALUES (%s, %s)", (user_id, f"{user_id}@test.local"))
        cursor.execute(
            "INSERT INTO businesses (id, owner_id, name) VALUES (%s, %s, 'Work review')",
            (business_id, user_id),
        )
        cursor.execute(
            """INSERT INTO business_work_journal
               (id, business_id, user_id, channel, request_key, original_text, occurred_at)
               VALUES (%s, %s, %s, 'web', %s, 'note', NOW())""",
            (journal_id, business_id, user_id, f"request-{uuid.uuid4()}"),
        )
        if kind == "reviewer":
            cursor.execute(
                """INSERT INTO business_work_reviewers (business_id, user_id, granted_by)
                   VALUES (%s, %s, %s)""",
                (business_id, user_id, user_id),
            )
        elif kind == "settings":
            cursor.execute(
                "INSERT INTO business_work_digest_settings (business_id) VALUES (%s)",
                (business_id,),
            )
        elif kind == "journal_fields":
            cursor.execute(
                "UPDATE business_work_journal SET review_status = 'reviewed' WHERE id = %s",
                (journal_id,),
            )
        else:
            flow_type = "work_journal" if kind == "work_journal_action" else "upgrade"
            cursor.execute(
                """INSERT INTO journey_actions
                   (id, business_id, user_id, flow_type, entity_type, action_type, title, cta_label, dedupe_key)
                   VALUES (%s, %s, %s, %s, 'journal', 'review', 'Review', 'Open', %s)""",
                (action_id, business_id, user_id, flow_type, f"dedupe-{uuid.uuid4()}"),
            )
            if kind == "link":
                cursor.execute(
                    """INSERT INTO business_work_links (business_id, entry_id, action_id, created_by)
                       VALUES (%s, %s, %s, %s)""",
                    (business_id, journal_id, action_id, user_id),
                )
        connection.commit()
    finally:
        _close(cursor, connection)

    result = _migrate(work_review_database, "downgrade", PRE_WORK_REVIEW_REVISION)

    assert result.returncode != 0
    assert "Cannot downgrade 20260914_work_review while work-review data exists" in (result.stderr or result.stdout)
    if kind == "link":
        assert _scalar(work_review_database, "SELECT COUNT(*) FROM business_work_links") == 1
    if kind in {"link", "work_journal_action"}:
        assert _scalar(work_review_database, "SELECT COUNT(*) FROM journey_actions WHERE id = %s", (action_id,)) == 1
    if kind == "settings":
        assert _scalar(work_review_database, "SELECT COUNT(*) FROM business_work_digest_settings") == 1
    if kind == "reviewer":
        assert _scalar(work_review_database, "SELECT COUNT(*) FROM business_work_reviewers") == 1
    if kind == "journal_fields":
        assert _scalar(
            work_review_database,
            "SELECT review_status = 'reviewed' FROM business_work_journal WHERE id = %s",
            (journal_id,),
        )
    _execute(work_review_database, "DELETE FROM business_work_links WHERE business_id = %s", (business_id,))
    _execute(work_review_database, "DELETE FROM business_work_reviewers WHERE business_id = %s", (business_id,))
    _execute(work_review_database, "DELETE FROM business_work_digest_settings WHERE business_id = %s", (business_id,))
    _execute(work_review_database, "DELETE FROM journey_actions WHERE business_id = %s", (business_id,))
    _execute(work_review_database, "DELETE FROM business_work_journal WHERE business_id = %s", (business_id,))
    _execute(work_review_database, "DELETE FROM businesses WHERE id = %s", (business_id,))
    _execute(work_review_database, "DELETE FROM users WHERE id = %s", (user_id,))


def test_concurrent_writer_cannot_commit_between_guard_and_destructive_ddl(work_review_database, monkeypatch):
    result = _migrate(work_review_database, "upgrade", WORK_REVIEW_REVISION)
    assert result.returncode == 0, result.stderr or result.stdout
    user_id, business_id = _seed_business(work_review_database)
    writer_started = threading.Event()
    writer_state = {"committed": False, "error": None}
    writer_name = f"work-review-writer-{uuid.uuid4().hex}"

    def write_digest_setting():
        connection = None
        cursor = None
        try:
            connection = psycopg2.connect(work_review_database, application_name=writer_name)
            cursor = connection.cursor()
            writer_started.set()
            cursor.execute(
                "INSERT INTO business_work_digest_settings (business_id) VALUES (%s)",
                (business_id,),
            )
            connection.commit()
            writer_state["committed"] = True
        except psycopg2.Error as error:
            writer_state["error"] = str(error)
            if connection is not None:
                connection.rollback()
        finally:
            _close(cursor, connection)

    migration = importlib.import_module("alembic_migrations.versions.20260914_work_review")
    engine = create_engine(work_review_database)
    migration_connection = engine.connect()
    transaction = migration_connection.begin()
    operations = Operations(MigrationContext.configure(migration_connection))
    writer = threading.Thread(target=write_digest_setting)

    class OperationsProxy:
        def execute(self, statement):
            operations.execute(statement)
            if "DO $$" not in str(statement):
                return
            writer.start()
            assert writer_started.wait(timeout=5)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                waiting = _scalar(
                    work_review_database,
                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE application_name = %s AND wait_event_type = 'Lock')",
                    (writer_name,),
                )
                if waiting:
                    return
                time.sleep(0.02)
            pytest.fail("concurrent writer did not block on the rollback lock")

    try:
        monkeypatch.setattr(migration, "op", OperationsProxy())
        migration.downgrade()
        transaction.commit()
    finally:
        if transaction.is_active:
            transaction.rollback()
        migration_connection.close()
        engine.dispose()

    writer.join(timeout=5)
    assert not writer.is_alive()
    assert not writer_state["committed"]
    assert writer_state["error"] is not None
    assert _scalar(
        work_review_database,
        "SELECT to_regclass('public.business_work_digest_settings') IS NULL",
    )
    _execute(work_review_database, "DELETE FROM businesses WHERE id = %s", (business_id,))
    _execute(work_review_database, "DELETE FROM users WHERE id = %s", (user_id,))
