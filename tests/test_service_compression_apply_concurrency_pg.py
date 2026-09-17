from pathlib import Path
import json
import os
import subprocess
import sys
import threading
import time
from urllib.parse import urlsplit, urlunsplit
import uuid

from flask import Flask
import psycopg2
import pytest

from api import services_api


pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parents[1]


def _database_url(database_url, database_name):
    parts = urlsplit(database_url.replace("postgresql+psycopg2://", "postgresql://", 1))
    return urlunsplit((parts.scheme, parts.netloc, f"/{database_name}", parts.query, parts.fragment))


def _close(cursor, connection):
    if cursor is not None:
        cursor.close()
    if connection is not None:
        connection.close()


def _migrate(database_url):
    environment = os.environ.copy()
    environment["DATABASE_URL"] = database_url
    environment["FLASK_APP"] = "src.main:app"
    paths = [str(ROOT / "src"), str(ROOT)]
    if environment.get("PYTHONPATH"):
        paths.append(environment["PYTHONPATH"])
    environment["PYTHONPATH"] = os.pathsep.join(paths)
    result = subprocess.run(
        [sys.executable, "-m", "flask", "db", "upgrade"],
        cwd=ROOT,
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 0, result.stderr or result.stdout


@pytest.fixture(scope="module")
def compression_database(postgres_container):
    database_name = f"service_compression_race_{uuid.uuid4().hex}"
    original_url = postgres_container.get_connection_url()
    admin_url = _database_url(original_url, "postgres")
    database_url = _database_url(original_url, database_name)
    connection = psycopg2.connect(admin_url)
    cursor = connection.cursor()
    try:
        connection.autocommit = True
        cursor.execute("SELECT EXISTS (SELECT 1 FROM pg_database WHERE datname = %s)", (database_name,))
        assert cursor.fetchone()[0] is False
        cursor.execute(f'CREATE DATABASE "{database_name}"')
    finally:
        _close(cursor, connection)
    try:
        _migrate(database_url)
        yield database_url
    finally:
        connection = psycopg2.connect(admin_url)
        cursor = connection.cursor()
        try:
            connection.autocommit = True
            cursor.execute(f'DROP DATABASE IF EXISTS "{database_name}" WITH (FORCE)')
        finally:
            _close(cursor, connection)


def _seed_compression_request(database_url):
    user_id = f"svc-user-{uuid.uuid4()}"
    business_id = f"svc-business-{uuid.uuid4()}"
    request_id = str(uuid.uuid4())
    connection = psycopg2.connect(database_url)
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO users (id, email) VALUES (%s, %s)", (user_id, f"{user_id}@test.invalid"))
        cursor.execute(
            "INSERT INTO businesses (id, owner_id, name) VALUES (%s, %s, 'Compression test')",
            (business_id, user_id),
        )
        cursor.execute(
            """
            INSERT INTO userservices (id, user_id, business_id, category, name, description, keywords, price, is_active)
            VALUES ('source-service', %s, %s, 'Source', 'Source service', '', '[]'::jsonb, '', TRUE)
            """,
            (user_id, business_id),
        )
        cursor.execute(
            """
            INSERT INTO service_catalog_compression_requests (
                id, business_id, user_id, status, before_count, after_count, groups_json, diff_json
            )
            VALUES (%s, %s, %s, 'needs_review', 1, 1, %s, '{}'::jsonb)
            """,
            (
                request_id,
                business_id,
                user_id,
                json.dumps(
                    [
                        {
                            "id": "group-1",
                            "action": "apply",
                            "source_service_ids": ["source-service"],
                            "target": {
                                "category": "Replacement",
                                "name": "Replacement service",
                                "description": "",
                                "keywords": [],
                                "price": "",
                            },
                        }
                    ]
                ),
            ),
        )
        connection.commit()
    finally:
        _close(cursor, connection)
    return user_id, business_id, request_id


def test_second_compression_apply_blocks_then_returns_idempotent_result(compression_database, monkeypatch):
    user_id, business_id, request_id = _seed_compression_request(compression_database)
    first_lock_acquired = threading.Event()
    release_first = threading.Event()
    connection_names = iter(("service-compression-first", "service-compression-second"))
    connection_names_lock = threading.Lock()
    responses = []
    failures = []

    class LockObservingCursor:
        def __init__(self, cursor):
            self.cursor = cursor
            self.locked_request_fetch = False

        @property
        def description(self):
            return self.cursor.description

        def execute(self, statement, parameters=None):
            normalized = " ".join(str(statement).split()).upper()
            self.locked_request_fetch = (
                normalized.startswith("SELECT ID, BUSINESS_ID, USER_ID, STATUS")
                and "FOR UPDATE" in normalized
            )
            if parameters is None:
                return self.cursor.execute(statement)
            return self.cursor.execute(statement, parameters)

        def fetchone(self):
            row = self.cursor.fetchone()
            if self.locked_request_fetch and not first_lock_acquired.is_set():
                first_lock_acquired.set()
                assert release_first.wait(timeout=10)
            return row

        def __getattr__(self, name):
            return getattr(self.cursor, name)

    class ConnectionWrapper:
        def __init__(self):
            with connection_names_lock:
                application_name = next(connection_names)
            self.connection = psycopg2.connect(compression_database, application_name=application_name)

        def cursor(self):
            return LockObservingCursor(self.connection.cursor())

        def commit(self):
            return self.connection.commit()

        def close(self):
            return self.connection.close()

    class RequestDatabase:
        def __init__(self):
            self.conn = ConnectionWrapper()

        def close(self):
            self.conn.close()

    monkeypatch.setattr(services_api, "DatabaseManager", RequestDatabase)
    monkeypatch.setattr(services_api, "_require_services_user", lambda: ({"user_id": user_id}, None, None))
    monkeypatch.setattr(services_api, "_ensure_business_access", lambda *_arguments: (None, None))

    def apply_once():
        app = Flask(__name__)
        try:
            with app.test_request_context(method="POST"):
                responses.append(services_api.apply_service_compression_draft(request_id))
        except BaseException:
            failures.append(sys.exception())

    first = threading.Thread(target=apply_once)
    second = threading.Thread(target=apply_once)
    first.start()
    assert first_lock_acquired.wait(timeout=10)
    second.start()

    deadline = time.monotonic() + 10
    second_blocked = False
    while time.monotonic() < deadline:
        connection = psycopg2.connect(compression_database)
        cursor = connection.cursor()
        try:
            cursor.execute(
                """
                SELECT EXISTS (
                    SELECT 1
                    FROM pg_stat_activity
                    WHERE application_name = 'service-compression-second'
                      AND wait_event_type = 'Lock'
                )
                """
            )
            second_blocked = cursor.fetchone()[0]
        finally:
            _close(cursor, connection)
        if second_blocked:
            break
        time.sleep(0.02)
    assert second_blocked
    release_first.set()
    first.join(timeout=15)
    second.join(timeout=15)

    assert not first.is_alive()
    assert not second.is_alive()
    assert not failures
    assert len(responses) == 2
    payloads = [response.get_json() for response in responses]
    assert all(response.status_code == 200 for response in responses)
    assert sum(bool(payload.get("already_applied")) for payload in payloads) == 1

    connection = psycopg2.connect(compression_database)
    cursor = connection.cursor()
    try:
        cursor.execute(
            """
            SELECT COUNT(*)
            FROM userservices
            WHERE business_id = %s AND name = 'Replacement service' AND is_active IS TRUE
            """,
            (business_id,),
        )
        assert cursor.fetchone()[0] == 1
    finally:
        _close(cursor, connection)
