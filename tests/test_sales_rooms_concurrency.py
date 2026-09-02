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


class _CoordinatedCursor:
    def __init__(
        self,
        cursor,
        *,
        role: str,
        event_inserted: threading.Event,
        second_reached_conflict_point: threading.Event,
        errors: list[BaseException],
    ):
        self._cursor = cursor
        self._role = role
        self._event_inserted = event_inserted
        self._second_reached_conflict_point = second_reached_conflict_point
        self._errors = errors

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        if (
            self._role == "second"
            and "create table if not exists sales_rooms" in normalized
        ):
            assert self._event_inserted.wait(
                timeout=10
            ), "first request never inserted its view event"
        if (
            self._role == "second"
            and "create table if not exists sales_room_events" in normalized
        ):
            self._second_reached_conflict_point.set()
        try:
            result = self._cursor.execute(query, params)
        except BaseException as exc:
            self._errors.append(exc)
            raise
        if self._role == "first" and "insert into sales_room_events" in normalized:
            self._event_inserted.set()
            assert self._second_reached_conflict_point.wait(
                timeout=10
            ), "second request never reached its event conflict point"
        if self._role == "second" and "insert into sales_room_events" in normalized:
            self._second_reached_conflict_point.set()
        return result

    def __getattr__(self, name):
        return getattr(self._cursor, name)


class _CoordinatedConnection:
    def __init__(
        self,
        connection,
        *,
        role: str,
        event_inserted: threading.Event,
        second_reached_conflict_point: threading.Event,
        errors: list[BaseException],
    ):
        self._connection = connection
        self._role = role
        self._event_inserted = event_inserted
        self._second_reached_conflict_point = second_reached_conflict_point
        self._errors = errors

    def cursor(self, *args, **kwargs):
        return _CoordinatedCursor(
            self._connection.cursor(*args, **kwargs),
            role=self._role,
            event_inserted=self._event_inserted,
            second_reached_conflict_point=self._second_reached_conflict_point,
            errors=self._errors,
        )

    def __getattr__(self, name):
        return getattr(self._connection, name)


def test_concurrent_public_sales_room_reads_do_not_deadlock(
    run_migrations,
    postgres_container,
    monkeypatch,
) -> None:
    dsn = _postgres_dsn(postgres_container)
    room_slug = f"concurrent-room-{uuid.uuid4().hex}"
    room_id = str(uuid.uuid4())
    seed_connection = psycopg2.connect(dsn)
    try:
        with seed_connection.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO sales_rooms (
                    id, slug, business_id, mode, room_json, status, visibility
                )
                VALUES (%s, %s, %s, 'client', %s::jsonb, 'ready', 'shared')
                """,
                (room_id, room_slug, str(uuid.uuid4()), '{"proposal": {}}'),
            )
            cursor.execute(
                """
                INSERT INTO sales_room_proposal_versions (
                    id, room_id, version_no, body_text, metadata_json
                )
                VALUES (%s, %s, 1, 'Existing proposal', '{}'::jsonb)
                """,
                (str(uuid.uuid4()), room_id),
            )
        seed_connection.commit()
    finally:
        seed_connection.close()

    event_inserted = threading.Event()
    second_reached_conflict_point = threading.Event()
    database_errors: list[BaseException] = []
    roles = iter(("first", "second"))
    role_lock = threading.Lock()

    def connection_factory():
        with role_lock:
            role = next(roles)
        connection = psycopg2.connect(dsn)
        return _CoordinatedConnection(
            connection,
            role=role,
            event_inserted=event_inserted,
            second_reached_conflict_point=second_reached_conflict_point,
            errors=database_errors,
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

    assert not any(isinstance(error, psycopg2.errors.DeadlockDetected) for error in database_errors)
    assert sorted(statuses) == [200, 200]
