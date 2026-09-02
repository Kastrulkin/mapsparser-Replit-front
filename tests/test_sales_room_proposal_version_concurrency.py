from __future__ import annotations

import threading
import uuid
from concurrent.futures import ThreadPoolExecutor

import psycopg2
from flask import Flask

from api import sales_rooms_api


def _postgres_dsn(postgres_container) -> str:
    raw_url = postgres_container.get_connection_url()
    return raw_url.replace("postgresql+psycopg2://", "postgresql://", 1)


class _VersionRaceCursor:
    def __init__(
        self,
        cursor,
        *,
        version_reads_complete: threading.Barrier,
        database_errors: list[BaseException],
    ):
        self._cursor = cursor
        self._version_reads_complete = version_reads_complete
        self._database_errors = database_errors
        self._version_read_coordinated = False

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        try:
            result = self._cursor.execute(query, params)
        except BaseException as exc:
            self._database_errors.append(exc)
            raise
        if (
            not self._version_read_coordinated
            and "from sales_room_proposal_versions" in normalized
            and "order by version_no desc" in normalized
        ):
            self._version_read_coordinated = True
            self._version_reads_complete.wait(timeout=10)
        return result

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _VersionRaceConnection:
    def __init__(
        self,
        connection,
        *,
        version_reads_complete: threading.Barrier,
        database_errors: list[BaseException],
    ):
        self._connection = connection
        self._version_reads_complete = version_reads_complete
        self._database_errors = database_errors

    def cursor(self, *args, **kwargs):
        return _VersionRaceCursor(
            self._connection.cursor(*args, **kwargs),
            version_reads_complete=self._version_reads_complete,
            database_errors=self._database_errors,
        )

    def __getattr__(self, name):
        return getattr(self._connection, name)


def test_concurrent_first_reads_create_one_proposal_version_without_errors(
    run_migrations,
    postgres_container,
    monkeypatch,
) -> None:
    dsn = _postgres_dsn(postgres_container)
    room_id = str(uuid.uuid4())
    room_slug = f"proposal-version-race-{uuid.uuid4().hex}"
    seed_connection = psycopg2.connect(dsn)
    try:
        with seed_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sales_rooms (
                    id, slug, business_id, mode, room_json, status, visibility
                )
                VALUES (
                    %s, %s, %s, 'client',
                    '{"proposal": {"body_text": "Concurrent proposal"}}'::jsonb,
                    'ready', 'shared'
                )
                """,
                (room_id, room_slug, str(uuid.uuid4())),
            )
        seed_connection.commit()
    finally:
        seed_connection.close()

    version_reads_complete = threading.Barrier(2)
    database_errors: list[BaseException] = []

    def connection_factory():
        return _VersionRaceConnection(
            psycopg2.connect(dsn),
            version_reads_complete=version_reads_complete,
            database_errors=database_errors,
        )

    monkeypatch.setattr(sales_rooms_api, "get_db_connection", connection_factory)
    monkeypatch.setattr(sales_rooms_api, "_optional_auth", lambda: {})

    app = Flask(__name__)
    app.register_blueprint(sales_rooms_api.sales_rooms_bp)

    def request_room() -> int:
        with app.test_client() as client:
            return client.get(f"/api/sales-rooms/public/{room_slug}").status_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        statuses = list(executor.map(lambda _index: request_room(), range(2)))

    assert not any(
        isinstance(error, psycopg2.errors.UniqueViolation)
        for error in database_errors
    )
    assert sorted(statuses) == [200, 200]

    verification_connection = psycopg2.connect(dsn)
    try:
        with verification_connection.cursor() as cursor:
            cursor.execute(
                "SELECT COUNT(*) FROM sales_room_proposal_versions WHERE room_id = %s",
                (room_id,),
            )
            assert cursor.fetchone()[0] == 1
    finally:
        verification_connection.close()
