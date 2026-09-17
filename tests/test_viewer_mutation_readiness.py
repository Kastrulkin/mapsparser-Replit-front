import io
import os
import uuid

from flask import Flask
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
import pytest

from api import finance_api
from core import auth_helpers


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


@pytest.mark.parametrize("database_url", [
    "postgresql://db.example.invalid/readiness_rbac_test",
    "postgresql://127.0.0.1/localos",
    "postgresql://127.0.0.1.evil/readiness_rbac_test",
    "postgresql://127.0.0.1/readiness_rbac_test?hostaddr=203.0.113.10",
])
def test_native_rbac_dsn_refuses_nonlocal_or_non_test_database(monkeypatch, database_url):
    monkeypatch.setenv(TEST_DSN_ENV, database_url)

    with pytest.raises(RuntimeError, match="loopback test database"):
        isolated_test_dsn()


@pytest.mark.parametrize("environment_name", ["PGHOSTADDR", "PGSERVICE"])
def test_native_rbac_dsn_refuses_inherited_libpq_host_override(monkeypatch, environment_name):
    monkeypatch.setenv(TEST_DSN_ENV, "postgresql://127.0.0.1/readiness_rbac_test")
    monkeypatch.setenv(environment_name, "unsafe")

    with pytest.raises(RuntimeError, match="libpq host overrides"):
        isolated_test_dsn()


class RoleDatabase:
    def __init__(self, connection, schema):
        self.connection = connection
        self.schema = schema

    def cursor(self):
        return self.connection.cursor()

    def commit(self):
        self.connection.commit()


@pytest.fixture
def role_database():
    connection = psycopg2.connect(isolated_test_dsn(), cursor_factory=RealDictCursor)
    schema = "rbac_" + uuid.uuid4().hex
    cursor = connection.cursor()
    try:
        cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        cursor.execute("CREATE TABLE businesses (id TEXT PRIMARY KEY, owner_id TEXT NOT NULL, network_id TEXT, is_active BOOLEAN)")
        cursor.execute("CREATE TABLE business_members (business_id TEXT NOT NULL, user_id TEXT NOT NULL, role TEXT NOT NULL, status TEXT NOT NULL)")
        cursor.execute("CREATE TABLE network_members (network_id TEXT NOT NULL, user_id TEXT NOT NULL, role TEXT NOT NULL, status TEXT NOT NULL)")
        cursor.execute("CREATE TABLE networks (id TEXT PRIMARY KEY, owner_id TEXT NOT NULL)")
        cursor.execute("CREATE TABLE roidata (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, business_id TEXT NOT NULL, investment_amount NUMERIC NOT NULL, returns_amount NUMERIC NOT NULL, roi_percentage NUMERIC NOT NULL, period_start DATE NOT NULL, period_end DATE NOT NULL)")
        cursor.execute("CREATE TABLE financialtransactions (id TEXT PRIMARY KEY, user_id TEXT NOT NULL, business_id TEXT, transaction_date DATE, amount NUMERIC, client_type TEXT, services TEXT, notes TEXT)")
        cursor.execute("INSERT INTO businesses (id, owner_id, network_id, is_active) VALUES ('business-1', 'owner-1', 'network-1', TRUE)")
        cursor.execute("INSERT INTO businesses (id, owner_id, network_id, is_active) VALUES ('business-2', 'other-owner-1', NULL, TRUE)")
        cursor.execute("INSERT INTO networks (id, owner_id) VALUES ('network-1', 'network-owner-1')")
        connection.commit()
        yield RoleDatabase(connection, schema)
    finally:
        connection.rollback()
        cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        connection.commit()
        cursor.close()
        connection.close()


def _actor(user_id, superadmin=False):
    return {"user_id": user_id, "is_superadmin": superadmin}


@pytest.mark.parametrize("role, allowed", [("viewer", False), ("member", True), ("manager", True)])
def test_direct_membership_write_policy_uses_stored_role(role_database, role, allowed):
    cursor = role_database.cursor()
    cursor.execute("INSERT INTO business_members VALUES ('business-1', 'direct-user', %s, 'active')", (role,))
    role_database.commit()

    allowed_write, owner_id = auth_helpers.verify_business_write_access(cursor, "business-1", _actor("direct-user"))

    assert allowed_write is allowed
    assert owner_id == "owner-1"


@pytest.mark.parametrize("role, allowed", [("viewer", False), ("member", True), ("manager", True)])
def test_network_membership_write_policy_uses_stored_role(role_database, role, allowed):
    cursor = role_database.cursor()
    cursor.execute("INSERT INTO network_members VALUES ('network-1', 'network-user', %s, 'active')", (role,))
    role_database.commit()

    allowed_write, owner_id = auth_helpers.verify_business_write_access(cursor, "business-1", _actor("network-user"))

    assert allowed_write is allowed
    assert owner_id == "owner-1"


@pytest.mark.parametrize("actor", [_actor("owner-1"), _actor("network-owner-1"), _actor("superadmin-1", True)])
def test_owner_and_superadmin_keep_existing_write_access(role_database, actor):
    cursor = role_database.cursor()

    allowed_write, owner_id = auth_helpers.verify_business_write_access(cursor, "business-1", actor)

    assert allowed_write is True
    assert owner_id == "owner-1"


@pytest.mark.parametrize("table_name, role", [("business_members", "viewer"), ("network_members", "manager")])
def test_inactive_membership_cannot_write(role_database, table_name, role):
    cursor = role_database.cursor()
    if table_name == "business_members":
        cursor.execute("INSERT INTO business_members VALUES ('business-1', 'inactive-user', %s, 'revoked')", (role,))
    else:
        cursor.execute("INSERT INTO network_members VALUES ('network-1', 'inactive-user', %s, 'revoked')", (role,))
    role_database.commit()

    allowed_write, owner_id = auth_helpers.verify_business_write_access(cursor, "business-1", _actor("inactive-user"))

    assert allowed_write is False
    assert owner_id == "owner-1"


def test_unrelated_tenant_cannot_write(role_database):
    cursor = role_database.cursor()

    allowed_write, owner_id = auth_helpers.verify_business_write_access(cursor, "business-1", _actor("other-user"))

    assert allowed_write is False
    assert owner_id == "owner-1"


class NativeDatabaseManager:
    def __init__(self, database_url, schema):
        self.conn = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
        cursor = self.conn.cursor()
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        cursor.close()

    def close(self):
        self.conn.close()


def test_finance_role_routes_use_actual_postgres_memberships(role_database, monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(finance_api.finance_bp)

    def database_manager():
        return NativeDatabaseManager(isolated_test_dsn(), role_database.schema)

    monkeypatch.setattr(finance_api, "DatabaseManager", database_manager)
    monkeypatch.setattr(finance_api, "verify_session", lambda token: {"user_id": token, "is_superadmin": False})
    monkeypatch.setattr(finance_api, "get_business_id_from_user", lambda _user_id, requested: requested)
    monkeypatch.setattr(finance_api, "get_capability_access", lambda _business_id, _capability, _admin: {"allowed": True})

    cursor = role_database.cursor()
    cursor.execute("INSERT INTO business_members VALUES ('business-1', 'viewer-1', 'viewer', 'active')")
    cursor.execute("INSERT INTO business_members VALUES ('business-1', 'member-1', 'member', 'active')")
    cursor.execute("INSERT INTO network_members VALUES ('network-1', 'network-viewer-1', 'viewer', 'active')")
    cursor.execute("INSERT INTO network_members VALUES ('network-1', 'network-member-1', 'member', 'active')")
    role_database.commit()

    client = app.test_client()
    viewer = client.post(
        "/api/finance/roi",
        headers={"Authorization": "Bearer viewer-1"},
        json={"business_id": "business-1", "investment_amount": 100, "returns_amount": 125},
    )
    cross_business = client.post(
        "/api/finance/roi",
        headers={"Authorization": "Bearer viewer-1"},
        json={"business_id": "business-2", "investment_amount": 100, "returns_amount": 125},
    )
    network_viewer = client.post(
        "/api/finance/roi",
        headers={"Authorization": "Bearer network-viewer-1"},
        json={"business_id": "business-1", "investment_amount": 100, "returns_amount": 125},
    )
    member = client.post(
        "/api/finance/roi",
        headers={"Authorization": "Bearer member-1"},
        json={"business_id": "business-1", "investment_amount": 100, "returns_amount": 125},
    )
    network_member = client.post(
        "/api/finance/roi",
        headers={"Authorization": "Bearer network-member-1"},
        json={"business_id": "business-1", "investment_amount": 100, "returns_amount": 125},
    )
    owner = client.post(
        "/api/finance/roi",
        headers={"Authorization": "Bearer owner-1"},
        json={"business_id": "business-1", "investment_amount": 100, "returns_amount": 125},
    )
    preview = client.post(
        "/api/finance/import-preview?business_id=business-1",
        headers={"Authorization": "Bearer viewer-1"},
        data={"business_id": "business-1", "file": (io.BytesIO(b"date,type,amount\n2026-09-18,revenue,100\n"), "finance.csv")},
    )

    assert viewer.status_code == 403
    assert cross_business.status_code == 403
    assert network_viewer.status_code == 403
    assert member.status_code == 200
    assert network_member.status_code == 200
    assert owner.status_code == 200
    assert preview.status_code == 200, preview.get_json()
    cursor.execute("SELECT user_id, business_id FROM roidata ORDER BY user_id")
    assert cursor.fetchall() == [
        {"user_id": "member-1", "business_id": "business-1"},
        {"user_id": "network-member-1", "business_id": "business-1"},
        {"user_id": "owner-1", "business_id": "business-1"},
    ]


def test_finance_transaction_target_business_rejects_viewer_bypass(role_database, monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(finance_api.finance_bp)

    def database_manager():
        return NativeDatabaseManager(isolated_test_dsn(), role_database.schema)

    monkeypatch.setattr(finance_api, "DatabaseManager", database_manager)
    monkeypatch.setattr(finance_api, "verify_session", lambda token: {"user_id": token, "is_superadmin": False})
    monkeypatch.setattr(finance_api, "get_business_id_from_user", lambda _user_id, requested: requested)
    monkeypatch.setattr(finance_api, "get_capability_access", lambda _business_id, _capability, _admin: {"allowed": True})

    cursor = role_database.cursor()
    cursor.execute("INSERT INTO business_members VALUES ('business-1', 'member-on-a', 'member', 'active')")
    cursor.execute("INSERT INTO business_members VALUES ('business-2', 'member-on-a', 'viewer', 'active')")
    cursor.execute("INSERT INTO financialtransactions VALUES ('transaction-b', 'member-on-a', 'business-2', '2026-09-18', 100, 'new', '[]', 'original')")
    role_database.commit()

    client = app.test_client()
    updated = client.put(
        "/api/finance/transaction/transaction-b?business_id=business-1",
        headers={"Authorization": "Bearer member-on-a"},
        json={"notes": "mutated"},
    )
    deleted = client.delete(
        "/api/finance/transaction/transaction-b?business_id=business-1",
        headers={"Authorization": "Bearer member-on-a"},
    )

    assert updated.status_code == 403
    assert deleted.status_code == 403
    cursor.execute("SELECT notes FROM financialtransactions WHERE id = 'transaction-b'")
    assert cursor.fetchone() == {"notes": "original"}


def test_finance_import_preview_is_the_explicit_read_only_post_exception():
    app = Flask(__name__)
    app.register_blueprint(finance_api.finance_bp)

    with app.test_request_context("/api/finance/import-preview", method="POST"):
        assert finance_api._finance_request_requires_write() is False
    with app.test_request_context("/api/finance/roi", method="POST"):
        assert finance_api._finance_request_requires_write() is True
    with app.test_request_context("/api/finance/crm/preview", method="POST"):
        assert finance_api._finance_request_requires_write() is True
    with app.test_request_context("/api/finance/dashboard", method="GET"):
        assert finance_api._finance_request_requires_write() is False
    with app.test_request_context("/api/finance/dashboard", method="HEAD"):
        assert finance_api._finance_request_requires_write() is False


def test_finance_head_uses_read_gate_without_calling_write_gate(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(finance_api.finance_bp)

    class Database:
        def __init__(self):
            self.conn = self

        def cursor(self):
            return object()

        def close(self):
            return None

    def write_gate(_cursor, _business_id, _user_data):
        raise AssertionError("HEAD must not use the finance write gate")

    monkeypatch.setattr(finance_api, "DatabaseManager", Database)
    monkeypatch.setattr(finance_api, "verify_session", lambda _token: {"user_id": "viewer-1", "is_superadmin": False})
    monkeypatch.setattr(finance_api, "get_business_id_from_user", lambda _user_id, requested: requested)
    monkeypatch.setattr(finance_api, "verify_business_access", lambda _cursor, _business_id, _user: (True, "owner-1"))
    monkeypatch.setattr(finance_api, "verify_business_write_access", write_gate)
    monkeypatch.setattr(finance_api, "get_capability_access", lambda _business_id, _capability, _admin: {"allowed": True})

    with app.test_request_context(
        "/api/finance/dashboard?business_id=business-1",
        method="HEAD",
        headers={"Authorization": "Bearer viewer-1"},
    ):
        assert app.preprocess_request() is None
