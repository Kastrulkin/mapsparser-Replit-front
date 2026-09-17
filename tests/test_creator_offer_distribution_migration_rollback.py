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

ROOT = Path(__file__).resolve().parents[1]
REVISION = "20260902_002"
PREVIOUS = "20260902_001"


def _url(database_url, database_name):
    parts = urlsplit(database_url.replace("postgresql+psycopg2://", "postgresql://", 1))
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def _close(cursor, connection):
    if cursor is not None:
        cursor.close()
    if connection is not None:
        connection.close()


def _run(database_url, action, revision):
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    environment["FLASK_APP"] = "src.main:app"
    environment["PYTHONPATH"] = os.pathsep.join([str(ROOT / "src"), str(ROOT)])
    return subprocess.run(
        [sys.executable, "-m", "flask", "db", action, revision],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=60,
    )


def _execute(database_url, sql, parameters=()):
    connection = psycopg2.connect(database_url)
    cursor = connection.cursor()
    try:
        cursor.execute(sql, parameters)
        connection.commit()
    finally:
        _close(cursor, connection)


def _scalar(database_url, sql, parameters=()):
    connection = psycopg2.connect(database_url)
    cursor = connection.cursor()
    try:
        cursor.execute(sql, parameters)
        return cursor.fetchone()[0]
    finally:
        _close(cursor, connection)


@pytest.fixture(scope="module")
def offer_database(postgres_container):
    database_name = f"creator_offer_rollback_{uuid.uuid4().hex}"
    original_url = postgres_container.get_connection_url()
    admin_url = _url(original_url, "postgres")
    database_url = _url(original_url, database_name)
    connection = psycopg2.connect(admin_url)
    cursor = connection.cursor()
    try:
        connection.autocommit = True
        cursor.execute(f"CREATE DATABASE {database_name}")
    finally:
        _close(cursor, connection)
    try:
        result = _run(database_url, "upgrade", REVISION)
        assert result.returncode == 0, result.stderr or result.stdout
        yield database_url
    finally:
        connection = psycopg2.connect(admin_url)
        cursor = connection.cursor()
        try:
            connection.autocommit = True
            cursor.execute(f"DROP DATABASE IF EXISTS {database_name} WITH (FORCE)")
        finally:
            _close(cursor, connection)


def _seed_creator(database_url):
    user_id = f"offer-user-{uuid.uuid4()}"
    business_id = f"offer-business-{uuid.uuid4()}"
    profile_id = str(uuid.uuid4())
    _execute(database_url, "INSERT INTO users (id, email) VALUES (%s, %s)", (user_id, f"{user_id}@test.local"))
    _execute(
        database_url,
        "INSERT INTO businesses (id, owner_id, name) VALUES (%s, %s, 'Offer business')",
        (business_id, user_id),
    )
    _execute(database_url, "INSERT INTO creator_profiles (id, display_name) VALUES (%s, 'Creator')", (profile_id,))
    return user_id, business_id, profile_id


def _seed_collaboration(database_url, business_id, profile_id):
    campaign_id = str(uuid.uuid4())
    candidate_id = str(uuid.uuid4())
    collaboration_id = str(uuid.uuid4())
    _execute(
        database_url,
        "INSERT INTO creator_campaigns (id, business_id, title, goal) VALUES (%s, %s, 'Campaign', 'Test')",
        (campaign_id, business_id),
    )
    _execute(
        database_url,
        "INSERT INTO creator_campaign_candidates (id, campaign_id, creator_profile_id) VALUES (%s, %s, %s)",
        (candidate_id, campaign_id, profile_id),
    )
    _execute(
        database_url,
        "INSERT INTO creator_collaborations (id, campaign_id, campaign_candidate_id, business_id, creator_profile_id) VALUES (%s, %s, %s, %s, %s)",
        (collaboration_id, campaign_id, candidate_id, business_id, profile_id),
    )
    return collaboration_id


def _remove_creator(database_url, user_id, business_id, profile_id):
    _execute(database_url, "DELETE FROM creator_offer_recipients WHERE creator_profile_id = %s", (profile_id,))
    _execute(database_url, "DELETE FROM creator_offer_distribution_runs WHERE campaign_id IN (SELECT id FROM creator_campaigns WHERE business_id = %s)", (business_id,))
    _execute(database_url, "DELETE FROM creator_offer_preferences WHERE creator_profile_id = %s", (profile_id,))
    _execute(database_url, "DELETE FROM creator_business_preferences WHERE creator_profile_id = %s", (profile_id,))
    _execute(database_url, "DELETE FROM creator_campaigns WHERE business_id = %s", (business_id,))
    _execute(database_url, "DELETE FROM creator_profiles WHERE id = %s", (profile_id,))
    _execute(database_url, "DELETE FROM businesses WHERE id = %s", (business_id,))
    _execute(database_url, "DELETE FROM users WHERE id = %s", (user_id,))


def test_empty_offer_distribution_schema_reverses(offer_database):
    result = _run(offer_database, "downgrade", PREVIOUS)
    assert result.returncode == 0, result.stderr or result.stdout
    for table_name in (
        "creator_business_preferences",
        "creator_offer_preferences",
        "creator_offer_distribution_runs",
        "creator_offer_recipients",
    ):
        assert _scalar(offer_database, "SELECT to_regclass(%s) IS NULL", (f"public.{table_name}",))
    assert _scalar(
        offer_database,
        "SELECT NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name = 'creator_campaigns' AND column_name = 'distribution_locked_at')",
    )


@pytest.mark.parametrize("kind", ["business_preference", "offer_preference", "distribution_run", "recipient"])
def test_populated_offer_distribution_blocks_and_retains_data(offer_database, kind):
    result = _run(offer_database, "upgrade", REVISION)
    assert result.returncode == 0, result.stderr or result.stdout
    user_id, business_id, profile_id = _seed_creator(offer_database)
    campaign_id = str(uuid.uuid4())
    record_id = str(uuid.uuid4())
    _execute(
        offer_database,
        "INSERT INTO creator_campaigns (id, business_id, title, goal) VALUES (%s, %s, 'Campaign', 'Test')",
        (campaign_id, business_id),
    )
    if kind == "business_preference":
        _execute(
            offer_database,
            "INSERT INTO creator_business_preferences (id, business_id, creator_profile_id) VALUES (%s, %s, %s)",
            (record_id, business_id, profile_id),
        )
        table_name = "creator_business_preferences"
    elif kind == "offer_preference":
        _execute(offer_database, "INSERT INTO creator_offer_preferences (creator_profile_id) VALUES (%s)", (profile_id,))
        table_name = "creator_offer_preferences"
    elif kind == "distribution_run":
        _execute(
            offer_database,
            "INSERT INTO creator_offer_distribution_runs (id, campaign_id, terms_version) VALUES (%s, %s, 1)",
            (record_id, campaign_id),
        )
        table_name = "creator_offer_distribution_runs"
    else:
        _execute(
            offer_database,
            "INSERT INTO creator_offer_recipients (id, campaign_id, business_id, creator_profile_id, terms_version) VALUES (%s, %s, %s, %s, 1)",
            (record_id, campaign_id, business_id, profile_id),
        )
        table_name = "creator_offer_recipients"

    result = _run(offer_database, "downgrade", PREVIOUS)
    assert result.returncode != 0
    assert "Cannot downgrade 20260902_002 while creator offer distribution data exists" in (result.stderr or result.stdout)
    if kind == "offer_preference":
        assert _scalar(offer_database, "SELECT COUNT(*) FROM creator_offer_preferences WHERE creator_profile_id = %s", (profile_id,)) == 1
    else:
        assert _scalar(offer_database, f"SELECT COUNT(*) FROM {table_name} WHERE id = %s", (record_id,)) == 1
    _remove_creator(offer_database, user_id, business_id, profile_id)


@pytest.mark.parametrize("column", ["reviewed_by", "reviewed_at", "distribution_locked_at"])
def test_mutated_campaign_columns_block_downgrade(offer_database, column):
    result = _run(offer_database, "upgrade", REVISION)
    assert result.returncode == 0, result.stderr or result.stdout
    user_id, business_id, profile_id = _seed_creator(offer_database)
    campaign_id = str(uuid.uuid4())
    _execute(
        offer_database,
        "INSERT INTO creator_campaigns (id, business_id, title, goal) VALUES (%s, %s, 'Campaign', 'Test')",
        (campaign_id, business_id),
    )
    if column == "reviewed_by":
        _execute(offer_database, "UPDATE creator_campaigns SET reviewed_by = %s WHERE id = %s", (user_id, campaign_id))
    else:
        _execute(offer_database, f"UPDATE creator_campaigns SET {column} = NOW() WHERE id = %s", (campaign_id,))

    result = _run(offer_database, "downgrade", PREVIOUS)
    assert result.returncode != 0
    assert "Cannot downgrade 20260902_002 while creator offer distribution data exists" in (result.stderr or result.stdout)
    assert _scalar(offer_database, f"SELECT {column} IS NOT NULL FROM creator_campaigns WHERE id = %s", (campaign_id,))
    _remove_creator(offer_database, user_id, business_id, profile_id)


def test_standalone_offer_message_blocks_downgrade_and_is_retained(offer_database):
    result = _run(offer_database, "upgrade", REVISION)
    assert result.returncode == 0, result.stderr or result.stdout
    user_id, business_id, profile_id = _seed_creator(offer_database)
    message_id = str(uuid.uuid4())
    _execute(
        offer_database,
        "INSERT INTO creator_offer_messages (id, collaboration_id, sender_type, body_text) VALUES (%s, NULL, 'localos', 'Standalone offer')",
        (message_id,),
    )

    result = _run(offer_database, "downgrade", PREVIOUS)
    assert result.returncode != 0
    assert "Cannot downgrade 20260902_002 while creator offer distribution data exists" in (result.stderr or result.stdout)
    assert _scalar(
        offer_database,
        "SELECT collaboration_id IS NULL FROM creator_offer_messages WHERE id = %s",
        (message_id,),
    )
    _execute(offer_database, "DELETE FROM creator_offer_messages WHERE id = %s", (message_id,))
    _execute(offer_database, "DELETE FROM creator_campaigns WHERE business_id = %s", (business_id,))
    _execute(offer_database, "DELETE FROM creator_profiles WHERE id = %s", (profile_id,))
    _execute(offer_database, "DELETE FROM businesses WHERE id = %s", (business_id,))
    _execute(offer_database, "DELETE FROM users WHERE id = %s", (user_id,))


def test_existing_collaboration_message_survives_empty_distribution_downgrade(offer_database):
    result = _run(offer_database, "upgrade", REVISION)
    assert result.returncode == 0, result.stderr or result.stdout
    user_id, business_id, profile_id = _seed_creator(offer_database)
    collaboration_id = _seed_collaboration(offer_database, business_id, profile_id)
    message_id = str(uuid.uuid4())
    _execute(
        offer_database,
        "INSERT INTO creator_offer_messages (id, collaboration_id, sender_type, body_text) VALUES (%s, %s, 'localos', 'Existing portal message')",
        (message_id, collaboration_id),
    )

    result = _run(offer_database, "downgrade", PREVIOUS)
    assert result.returncode == 0, result.stderr or result.stdout
    assert _scalar(
        offer_database,
        "SELECT collaboration_id = %s FROM creator_offer_messages WHERE id = %s",
        (collaboration_id, message_id),
    )
    _execute(offer_database, "DELETE FROM creator_offer_messages WHERE id = %s", (message_id,))
    _execute(offer_database, "DELETE FROM creator_campaigns WHERE business_id = %s", (business_id,))
    _execute(offer_database, "DELETE FROM creator_profiles WHERE id = %s", (profile_id,))
    _execute(offer_database, "DELETE FROM businesses WHERE id = %s", (business_id,))
    _execute(offer_database, "DELETE FROM users WHERE id = %s", (user_id,))


def test_concurrent_writer_cannot_commit_after_data_guard_before_drop(offer_database, monkeypatch):
    result = _run(offer_database, "upgrade", REVISION)
    assert result.returncode == 0, result.stderr or result.stdout
    user_id, business_id, profile_id = _seed_creator(offer_database)
    writer_started = threading.Event()
    writer_state = {"committed": False, "error": None}
    writer_name = f"creator-offer-writer-{uuid.uuid4().hex}"

    def write_business_preference():
        connection = None
        cursor = None
        try:
            connection = psycopg2.connect(offer_database, application_name=writer_name)
            cursor = connection.cursor()
            writer_started.set()
            cursor.execute(
                "INSERT INTO creator_business_preferences (id, business_id, creator_profile_id) VALUES (%s, %s, %s)",
                (str(uuid.uuid4()), business_id, profile_id),
            )
            connection.commit()
            writer_state["committed"] = True
        except psycopg2.Error:
            writer_state["error"] = str(sys.exception())
            if connection is not None:
                connection.rollback()
        finally:
            _close(cursor, connection)

    migration = importlib.import_module("alembic_migrations.versions.20260902_add_creator_offer_distribution")
    engine = create_engine(offer_database)
    migration_connection = engine.connect()
    transaction = migration_connection.begin()
    operations = Operations(MigrationContext.configure(migration_connection))
    writer = threading.Thread(target=write_business_preference)

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
                    offer_database,
                    "SELECT EXISTS (SELECT 1 FROM pg_stat_activity WHERE application_name = %s AND wait_event_type = 'Lock')",
                    (writer_name,),
                )
                if waiting:
                    return
                time.sleep(0.02)
            pytest.fail("concurrent offer writer did not block on the rollback lock")

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
    assert _scalar(offer_database, "SELECT to_regclass('public.creator_business_preferences') IS NULL")
    _execute(offer_database, "DELETE FROM creator_profiles WHERE id = %s", (profile_id,))
    _execute(offer_database, "DELETE FROM businesses WHERE id = %s", (business_id,))
    _execute(offer_database, "DELETE FROM users WHERE id = %s", (user_id,))
