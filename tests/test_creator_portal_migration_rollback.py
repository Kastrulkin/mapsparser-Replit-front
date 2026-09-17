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
PORTAL_REVISION = "20260902_001"
PRE_PORTAL_REVISION = "20260830_003"


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


def _execute(database_url, statement, parameters=()):
    connection = _connect(database_url)
    cursor = connection.cursor()
    try:
        cursor.execute(statement, parameters)
        connection.commit()
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
def portal_database(postgres_container):
    database_name = f"creator_portal_rollback_{uuid.uuid4().hex}"
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
        result = _migrate(database_url, "upgrade", PORTAL_REVISION)
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


def _seed_creator(database_url):
    user_id = f"creator-user-{uuid.uuid4()}"
    business_id = f"creator-business-{uuid.uuid4()}"
    profile_id = str(uuid.uuid4())
    _execute(database_url, "INSERT INTO users (id, email) VALUES (%s, %s)", (user_id, f"{user_id}@test.local"))
    _execute(
        database_url,
        "INSERT INTO businesses (id, owner_id, name) VALUES (%s, %s, 'Creator business')",
        (business_id, user_id),
    )
    _execute(
        database_url,
        "INSERT INTO creator_profiles (id, display_name) VALUES (%s, 'Creator')",
        (profile_id,),
    )
    return user_id, business_id, profile_id


def test_empty_creator_portal_schema_downgrades_without_cascade(portal_database):
    upgrade = _migrate(portal_database, "upgrade", PORTAL_REVISION)
    assert upgrade.returncode == 0, upgrade.stderr or upgrade.stdout
    result = _migrate(portal_database, "downgrade", PRE_PORTAL_REVISION)

    assert result.returncode == 0, result.stderr or result.stdout
    for table_name in (
        "creator_relationships",
        "creator_contact_events",
        "creator_accounts",
        "creator_invites",
        "creator_sessions",
        "creator_profile_change_events",
        "creator_offer_messages",
        "creator_notification_outbox",
    ):
        assert _scalar(portal_database, "SELECT to_regclass(%s) IS NULL", (f"public.{table_name}",))
    assert _scalar(
        portal_database,
        "SELECT to_regprocedure('prevent_creator_contact_event_mutation()') IS NULL",
    )
    assert _scalar(
        portal_database,
        "SELECT NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'creator_collaborations' AND column_name = 'review_status')",
    )


@pytest.mark.parametrize("kind", ["relationship", "review_field"])
def test_creator_portal_data_blocks_downgrade_and_remains_present(portal_database, kind):
    upgrade = _migrate(portal_database, "upgrade", PORTAL_REVISION)
    assert upgrade.returncode == 0, upgrade.stderr or upgrade.stdout
    user_id, business_id, profile_id = _seed_creator(portal_database)
    collaboration_id = str(uuid.uuid4())
    if kind == "relationship":
        _execute(
            portal_database,
            "INSERT INTO creator_relationships (creator_profile_id) VALUES (%s)",
            (profile_id,),
        )
    else:
        campaign_id = str(uuid.uuid4())
        candidate_id = str(uuid.uuid4())
        _execute(
            portal_database,
            "INSERT INTO creator_campaigns (id, business_id, title, goal) VALUES (%s, %s, 'Campaign', 'Test')",
            (campaign_id, business_id),
        )
        _execute(
            portal_database,
            "INSERT INTO creator_campaign_candidates (id, campaign_id, creator_profile_id) VALUES (%s, %s, %s)",
            (candidate_id, campaign_id, profile_id),
        )
        _execute(
            portal_database,
            """INSERT INTO creator_collaborations
               (id, campaign_id, campaign_candidate_id, business_id, creator_profile_id, review_status)
               VALUES (%s, %s, %s, %s, %s, 'approved')""",
            (collaboration_id, campaign_id, candidate_id, business_id, profile_id),
        )

    result = _migrate(portal_database, "downgrade", PRE_PORTAL_REVISION)

    assert result.returncode != 0
    assert "Cannot downgrade 20260902_001 while creator portal data exists" in (result.stderr or result.stdout)
    if kind == "relationship":
        assert _scalar(portal_database, "SELECT COUNT(*) FROM creator_relationships") == 1
    else:
        assert _scalar(
            portal_database,
            "SELECT review_status = 'approved' FROM creator_collaborations WHERE id = %s",
            (collaboration_id,),
        )
    _execute(portal_database, "DELETE FROM creator_relationships WHERE creator_profile_id = %s", (profile_id,))
    _execute(portal_database, "DELETE FROM creator_collaborations WHERE creator_profile_id = %s", (profile_id,))
    _execute(portal_database, "DELETE FROM creator_campaigns WHERE business_id = %s", (business_id,))
    _execute(portal_database, "DELETE FROM creator_profiles WHERE id = %s", (profile_id,))
    _execute(portal_database, "DELETE FROM businesses WHERE id = %s", (business_id,))
    _execute(portal_database, "DELETE FROM users WHERE id = %s", (user_id,))


def test_concurrent_portal_writer_cannot_commit_during_downgrade(portal_database, monkeypatch):
    upgrade = _migrate(portal_database, "upgrade", PORTAL_REVISION)
    assert upgrade.returncode == 0, upgrade.stderr or upgrade.stdout
    user_id, business_id, profile_id = _seed_creator(portal_database)
    writer_started = threading.Event()
    writer_state = {"committed": False, "error": None}
    writer_name = f"creator-portal-writer-{uuid.uuid4().hex}"

    def write_relationship():
        connection = None
        cursor = None
        try:
            connection = psycopg2.connect(portal_database, application_name=writer_name)
            cursor = connection.cursor()
            writer_started.set()
            cursor.execute("INSERT INTO creator_relationships (creator_profile_id) VALUES (%s)", (profile_id,))
            connection.commit()
            writer_state["committed"] = True
        except psycopg2.Error:
            writer_state["error"] = str(sys.exception())
            if connection is not None:
                connection.rollback()
        finally:
            _close(cursor, connection)

    migration = importlib.import_module("alembic_migrations.versions.20260902_add_creator_relationships_portal")
    engine = create_engine(portal_database)
    migration_connection = engine.connect()
    transaction = migration_connection.begin()
    operations = Operations(MigrationContext.configure(migration_connection))
    writer = threading.Thread(target=write_relationship)

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
                    portal_database,
                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE application_name = %s AND wait_event_type = 'Lock')",
                    (writer_name,),
                )
                if waiting:
                    return
                time.sleep(0.02)
            pytest.fail("concurrent portal writer did not block on the rollback lock")

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
    assert _scalar(portal_database, "SELECT to_regclass('public.creator_relationships') IS NULL")
    _execute(portal_database, "DELETE FROM creator_profiles WHERE id = %s", (profile_id,))
    _execute(portal_database, "DELETE FROM businesses WHERE id = %s", (business_id,))
    _execute(portal_database, "DELETE FROM users WHERE id = %s", (user_id,))
