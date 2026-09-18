import os
import uuid

from flask import Flask
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
import pytest

from api import operator_api
from services import operator_chat_service


TEST_DSN_ENV = "LOCALOS_RBAC_TEST_DATABASE_URL"


def isolated_test_dsn():
    database_url = os.getenv(TEST_DSN_ENV, "")
    if not database_url:
        pytest.skip(f"{TEST_DSN_ENV} is required for native PostgreSQL RBAC proof")
    if os.getenv("PGHOSTADDR") or os.getenv("PGSERVICE"):
        raise RuntimeError("native PostgreSQL RBAC proof refuses inherited libpq host overrides")
    parameters = psycopg2.extensions.parse_dsn(database_url)
    database_name = str(parameters.get("dbname") or "").lower()
    host = str(parameters.get("host") or "")
    if (
        "test" not in database_name
        or host not in {"127.0.0.1", "::1"}
        or parameters.get("hostaddr")
        or parameters.get("service")
    ):
        raise RuntimeError("native PostgreSQL RBAC proof requires an explicit loopback test database")
    return database_url


class NativeDatabaseManager:
    def __init__(self, database_url, schema):
        self.conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        cursor = self.conn.cursor()
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        cursor.close()

    def close(self):
        self.conn.close()


@pytest.fixture
def operator_chat_role_database():
    connection = psycopg2.connect(isolated_test_dsn(), cursor_factory=RealDictCursor)
    schema = "operator_chat_rbac_" + uuid.uuid4().hex
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        cursor.execute(
            "CREATE TABLE businesses (id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, network_id TEXT, is_active BOOLEAN)"
        )
        cursor.execute(
            "CREATE TABLE business_members (business_id TEXT NOT NULL, user_id TEXT NOT NULL, role TEXT NOT NULL, status TEXT NOT NULL)"
        )
        cursor.execute(
            "CREATE TABLE network_members (network_id TEXT NOT NULL, user_id TEXT NOT NULL, role TEXT NOT NULL, status TEXT NOT NULL)"
        )
        cursor.execute("CREATE TABLE networks (id TEXT PRIMARY KEY, owner_id TEXT NOT NULL)")
        cursor.execute(
            "CREATE TABLE operatormessages (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, result_json JSONB)"
        )
        cursor.execute(
            "INSERT INTO businesses (id, owner_id, network_id, is_active) VALUES ('business-1', 'owner-1', 'network-1', TRUE)"
        )
        cursor.execute("INSERT INTO networks (id, owner_id) VALUES ('network-1', 'network-owner-1')")
        cursor.execute("INSERT INTO operatormessages (id, user_id) VALUES ('message-1', 'actor-1')")
        connection.commit()
        yield connection, schema
    finally:
        connection.rollback()
        cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        connection.commit()
        cursor.close()
        connection.close()


@pytest.mark.parametrize(
    ("membership_table", "membership_id", "role", "status", "expected_status"),
    [
        ("business_members", "business-1", "viewer", "active", 403),
        ("network_members", "network-1", "viewer", "active", 403),
        ("business_members", "business-1", "member", "active", 200),
        ("business_members", "business-1", "manager", "active", 200),
        ("network_members", "network-1", "member", "active", 200),
        ("network_members", "network-1", "manager", "active", 200),
        ("business_members", "business-1", "manager", "revoked", 403),
        ("network_members", "network-1", "manager", "revoked", 403),
    ],
)
def test_stored_membership_controls_operator_chat_before_chat_effects(
    operator_chat_role_database,
    monkeypatch,
    membership_table,
    membership_id,
    role,
    status,
    expected_status,
):
    connection, schema = operator_chat_role_database
    cursor = connection.cursor()
    cursor.execute(
        sql.SQL("INSERT INTO {} VALUES (%s, 'actor-1', %s, %s)").format(sql.Identifier(membership_table)),
        (membership_id, role, status),
    )
    connection.commit()

    app = Flask(__name__)
    app.register_blueprint(operator_api.operator_bp)
    effects = []

    def database_manager():
        return NativeDatabaseManager(isolated_test_dsn(), schema)

    def process_chat(*_args, **_kwargs):
        effects.append("process_chat")
        return {"status": "completed", "conversation_id": "conversation-1", "message_id": "message-1"}

    monkeypatch.setattr(operator_api, "DatabaseManager", database_manager)
    monkeypatch.setattr(
        operator_api,
        "require_auth_from_request",
        lambda: {"user_id": "actor-1", "is_superadmin": False},
    )
    monkeypatch.setattr(
        operator_api,
        "_scope_capability_access",
        lambda *_args, **_kwargs: {"allowed": True},
    )
    monkeypatch.setattr(operator_api, "_scope_subscription_access", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(operator_api, "record_operator_event", lambda *_args, **_kwargs: effects.append("event"))
    monkeypatch.setattr(operator_chat_service, "process_chat", process_chat)

    response = app.test_client().post(
        "/api/operator/chat",
        json={"business_id": "business-1", "message": "Подготовь черновик"},
    )

    assert response.status_code == expected_status
    if expected_status == 403:
        assert effects == []
    else:
        assert "process_chat" in effects


@pytest.mark.parametrize(
    ("user_id", "is_superadmin"),
    [("owner-1", False), ("network-owner-1", False), ("superadmin-1", True)],
)
def test_existing_owner_and_superadmin_controls_keep_operator_chat_access(
    operator_chat_role_database,
    monkeypatch,
    user_id,
    is_superadmin,
):
    _connection, schema = operator_chat_role_database
    app = Flask(__name__)
    app.register_blueprint(operator_api.operator_bp)
    effects = []

    def database_manager():
        return NativeDatabaseManager(isolated_test_dsn(), schema)

    def process_chat(*_args, **_kwargs):
        effects.append("process_chat")
        return {"status": "completed", "conversation_id": "conversation-1", "message_id": "message-1"}

    monkeypatch.setattr(operator_api, "DatabaseManager", database_manager)
    monkeypatch.setattr(
        operator_api,
        "require_auth_from_request",
        lambda: {"user_id": user_id, "is_superadmin": is_superadmin},
    )
    monkeypatch.setattr(operator_api, "_scope_capability_access", lambda *_args, **_kwargs: {"allowed": True})
    monkeypatch.setattr(operator_api, "_scope_subscription_access", lambda *_args, **_kwargs: {})
    monkeypatch.setattr(operator_api, "record_operator_event", lambda *_args, **_kwargs: None)
    monkeypatch.setattr(operator_chat_service, "process_chat", process_chat)

    response = app.test_client().post(
        "/api/operator/chat",
        json={"business_id": "business-1", "message": "Подготовь черновик"},
    )

    assert response.status_code == 200
    assert effects == ["process_chat"]


def test_stored_viewer_keeps_read_only_current_conversation_access(operator_chat_role_database, monkeypatch):
    connection, schema = operator_chat_role_database
    cursor = connection.cursor()
    cursor.execute("INSERT INTO business_members VALUES ('business-1', 'viewer-1', 'viewer', 'active')")
    connection.commit()

    app = Flask(__name__)
    app.register_blueprint(operator_api.operator_bp)

    def database_manager():
        return NativeDatabaseManager(isolated_test_dsn(), schema)

    def write_gate(*_args, **_kwargs):
        raise AssertionError("read-only conversation route must not use the write gate")

    monkeypatch.setattr(operator_api, "DatabaseManager", database_manager)
    monkeypatch.setattr(
        operator_api,
        "require_auth_from_request",
        lambda: {"user_id": "viewer-1", "is_superadmin": False},
    )
    monkeypatch.setattr(operator_api, "verify_business_write_access", write_gate)
    monkeypatch.setattr(operator_api, "find_latest_operator_conversation", lambda *_args, **_kwargs: {})

    response = app.test_client().get("/api/operator/conversations/current?business_id=business-1")

    assert response.status_code == 200
    assert response.get_json()["conversation"] is None
