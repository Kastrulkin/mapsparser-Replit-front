"""Causal PostgreSQL proof for business-data authorization before legacy DDL.

This test intentionally uses the guarded disposable database fixture from the
existing route regression. It is a local proof only; it never accepts an
ambient, production, or provider-connected database.
"""

import os
import uuid

import psycopg2
import pytest

from tests.test_legacy_business_data_pg import migrated_business_database, seed_user_and_business


class RecordingCursor:
    def __init__(self, cursor, statements):
        self.cursor = cursor
        self.statements = statements

    def execute(self, query, params=None):
        self.statements.append(str(query))
        return self.cursor.execute(query, params)

    def __getattr__(self, name):
        return getattr(self.cursor, name)


class RecordingConnection:
    def __init__(self, connection, statements):
        self.connection = connection
        self.statements = statements

    def cursor(self, *args, **kwargs):
        return RecordingCursor(self.connection.cursor(*args, **kwargs), self.statements)

    def __getattr__(self, name):
        return getattr(self.connection, name)


def route_client(database_url, monkeypatch):
    from main import app
    import database_manager

    assert os.environ.get("DATABASE_URL") == database_url
    statements = []

    class RecordingDatabaseManager(database_manager.DatabaseManager):
        def __init__(self):
            super().__init__()
            self.conn = RecordingConnection(self.conn, statements)

    handler = app.view_functions["get_business_data"]
    monkeypatch.setitem(handler.__globals__, "DatabaseManager", RecordingDatabaseManager)
    return app.test_client(), statements


def bearer(client, email):
    octet = (sum(email.encode("utf-8")) % 240) + 1
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": "benchmark-password"},
        environ_overrides={"REMOTE_ADDR": f"198.51.100.{octet}"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.get_json()['token']}"}


@pytest.fixture
def business_data_access_fixture(migrated_business_database):
    owner, business = seed_user_and_business(migrated_business_database)
    direct, _unused = seed_user_and_business(migrated_business_database)
    network_member, _unused_network = seed_user_and_business(migrated_business_database)
    viewer, _unused_viewer = seed_user_and_business(migrated_business_database)
    revoked, _unused_revoked = seed_user_and_business(migrated_business_database)
    foreign, foreign_business = seed_user_and_business(migrated_business_database)
    network = str(uuid.uuid4())
    foreign_service = str(uuid.uuid4())
    connection = psycopg2.connect(migrated_business_database)
    cursor = connection.cursor()
    try:
        cursor.execute("INSERT INTO networks (id, owner_id, name) VALUES (%s, %s, 'read proof')", (network, owner))
        cursor.execute("UPDATE businesses SET network_id=%s WHERE id=%s", (network, business))
        cursor.execute("INSERT INTO business_members (id, business_id, user_id, role, status) VALUES (%s,%s,%s,'member','active')", (str(uuid.uuid4()), business, direct))
        cursor.execute("INSERT INTO network_members (id, network_id, user_id, role, status) VALUES (%s,%s,%s,'member','active')", (str(uuid.uuid4()), network, network_member))
        cursor.execute("INSERT INTO business_members (id, business_id, user_id, role, status) VALUES (%s,%s,%s,'viewer','active')", (str(uuid.uuid4()), business, viewer))
        cursor.execute("INSERT INTO business_members (id, business_id, user_id, role, status) VALUES (%s,%s,%s,'member','revoked')", (str(uuid.uuid4()), business, revoked))
        cursor.execute("INSERT INTO userservices (id, user_id, business_id, name, keywords, price, is_active) VALUES (%s,%s,%s,'foreign sentinel','[]'::jsonb,'1',TRUE)", (foreign_service, foreign, foreign_business))
        connection.commit()
    finally:
        cursor.close()
        connection.close()
    return {"database_url": migrated_business_database, "owner": owner, "business": business, "direct": direct, "network_member": network_member, "viewer": viewer, "revoked": revoked, "foreign": foreign, "foreign_business": foreign_business, "foreign_service": foreign_service}


def service_business_id(database_url, service_id):
    connection = psycopg2.connect(database_url)
    cursor = connection.cursor()
    try:
        cursor.execute("SELECT business_id FROM userservices WHERE id=%s", (service_id,))
        return cursor.fetchone()[0]
    finally:
        cursor.close()
        connection.close()


def assert_no_runtime_schema_or_data_write(statements):
    assert statements
    normalized = "\n".join(statements).lower()
    assert "create table" not in normalized
    assert "alter table" not in normalized
    assert "update " not in normalized
    assert "insert " not in normalized
    assert "delete " not in normalized


@pytest.mark.parametrize("actor,business_key", (("revoked", "business"), ("foreign", "business"), ("owner", "foreign_business")))
def test_denied_requests_must_not_execute_runtime_ddl_or_writes(business_data_access_fixture, monkeypatch, actor, business_key):
    fixture = business_data_access_fixture
    client, statements = route_client(fixture["database_url"], monkeypatch)
    response = client.get(f"/api/business/{fixture[business_key]}/data", headers=bearer(client, f"{fixture[actor]}@benchmark.invalid"))
    assert response.status_code == 403
    assert_no_runtime_schema_or_data_write(statements)
    assert service_business_id(fixture["database_url"], fixture["foreign_service"]) == fixture["foreign_business"]


@pytest.mark.parametrize("actor", ("owner", "direct", "network_member", "viewer"))
def test_active_stored_members_are_supported_business_data_readers(business_data_access_fixture, monkeypatch, actor):
    fixture = business_data_access_fixture
    client, statements = route_client(fixture["database_url"], monkeypatch)
    response = client.get(f"/api/business/{fixture['business']}/data", headers=bearer(client, f"{fixture[actor]}@benchmark.invalid"))
    assert response.status_code == 200
    assert response.get_json()["business"]["id"] == fixture["business"]
    assert_no_runtime_schema_or_data_write(statements)
