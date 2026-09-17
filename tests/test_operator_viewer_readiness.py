import os
import uuid

from flask import Flask
import psycopg2
from psycopg2 import sql
from psycopg2.extras import RealDictCursor
import pytest

from api import agent_blueprints_api


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
def operator_role_database():
    connection = psycopg2.connect(isolated_test_dsn(), cursor_factory=RealDictCursor)
    schema = "operator_rbac_" + uuid.uuid4().hex
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
            """
            CREATE TABLE agent_blueprints (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                name TEXT NOT NULL,
                category TEXT NOT NULL,
                description TEXT,
                status TEXT NOT NULL,
                created_by_user_id TEXT NOT NULL,
                metadata_json JSONB NOT NULL,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            )
            """
        )
        cursor.execute(
            "CREATE TABLE agent_runs (id TEXT PRIMARY KEY, blueprint_id TEXT NOT NULL, status TEXT NOT NULL)"
        )
        cursor.execute(
            "CREATE TABLE agent_blueprint_versions (id TEXT PRIMARY KEY, blueprint_id TEXT NOT NULL, compiled_state TEXT)"
        )
        cursor.execute(
            "INSERT INTO businesses (id, owner_id, network_id, is_active) VALUES ('business-1', 'owner-1', 'network-1', TRUE)"
        )
        cursor.execute("INSERT INTO networks (id, owner_id) VALUES ('network-1', 'network-owner-1')")
        connection.commit()
        yield connection, schema
    finally:
        connection.rollback()
        cursor.execute(sql.SQL("DROP SCHEMA IF EXISTS {} CASCADE").format(sql.Identifier(schema)))
        connection.commit()
        cursor.close()
        connection.close()


@pytest.mark.parametrize(
    ("membership_table", "membership_id", "role", "status", "expected"),
    [
        ("business_members", "business-1", "viewer", "active", (403, 0)),
        ("network_members", "network-1", "viewer", "active", (403, 0)),
        ("business_members", "business-1", "member", "active", (201, 1)),
        ("business_members", "business-1", "manager", "active", (201, 1)),
        ("network_members", "network-1", "member", "active", (201, 1)),
        ("network_members", "network-1", "manager", "active", (201, 1)),
        ("business_members", "business-1", "viewer", "revoked", (403, 0)),
    ],
)
def test_stored_membership_controls_agent_blueprint_insert(
    operator_role_database,
    monkeypatch,
    membership_table,
    membership_id,
    role,
    status,
    expected,
):
    connection, schema = operator_role_database
    cursor = connection.cursor()
    cursor.execute(
            sql.SQL("INSERT INTO {} VALUES (%s, 'actor-1', %s, %s)").format(
                sql.Identifier(membership_table)
            ),
            (membership_id, role, status),
    )
    connection.commit()

    app = Flask(__name__)
    app.register_blueprint(agent_blueprints_api.agent_blueprints_bp)

    def database_manager():
        return NativeDatabaseManager(isolated_test_dsn(), schema)

    monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", database_manager)
    monkeypatch.setattr(
        agent_blueprints_api,
        "require_auth_from_request",
        lambda: {"user_id": "actor-1", "is_superadmin": False},
    )

    response = app.test_client().post(
        "/api/agent-blueprints",
        json={"business_id": "business-1", "name": "Membership write attempt"},
    )

    cursor.execute("SELECT COUNT(*) AS count FROM agent_blueprints")
    assert (response.status_code, cursor.fetchone()["count"]) == expected


@pytest.mark.parametrize(
    ("user_id", "is_superadmin"),
    [("owner-1", False), ("network-owner-1", False), ("superadmin-1", True)],
)
def test_owner_and_superadmin_controls_keep_agent_blueprint_write_access(
    operator_role_database,
    monkeypatch,
    user_id,
    is_superadmin,
):
    _connection, schema = operator_role_database
    app = Flask(__name__)
    app.register_blueprint(agent_blueprints_api.agent_blueprints_bp)

    def database_manager():
        return NativeDatabaseManager(isolated_test_dsn(), schema)

    monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", database_manager)
    monkeypatch.setattr(
        agent_blueprints_api,
        "require_auth_from_request",
        lambda: {"user_id": user_id, "is_superadmin": is_superadmin},
    )

    response = app.test_client().post(
        "/api/agent-blueprints",
        json={"business_id": "business-1", "name": "Existing write access"},
    )

    assert response.status_code == 201


def test_unrelated_actor_cannot_create_agent_blueprint(operator_role_database, monkeypatch):
    _connection, schema = operator_role_database
    app = Flask(__name__)
    app.register_blueprint(agent_blueprints_api.agent_blueprints_bp)

    def database_manager():
        return NativeDatabaseManager(isolated_test_dsn(), schema)

    monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", database_manager)
    monkeypatch.setattr(
        agent_blueprints_api,
        "require_auth_from_request",
        lambda: {"user_id": "foreign-1", "is_superadmin": False},
    )

    response = app.test_client().post(
        "/api/agent-blueprints",
        json={"business_id": "business-1", "name": "Foreign write attempt"},
    )

    assert response.status_code == 403


def test_agent_preflight_is_explicit_read_only_post():
    app = Flask(__name__)
    app.register_blueprint(agent_blueprints_api.agent_blueprints_bp)

    with app.test_request_context("/api/agent-blueprints/blueprint-1/preflight", method="POST"):
        assert agent_blueprints_api._agent_request_requires_write() is False
    with app.test_request_context("/api/agent-blueprints/blueprint-1/runs", method="POST"):
        assert agent_blueprints_api._agent_request_requires_write() is True
    with app.test_request_context("/api/agent-blueprints/blueprint-1/review", method="GET"):
        assert agent_blueprints_api._agent_request_requires_write() is False
    with app.test_request_context("/api/agent-blueprints/blueprint-1/review", method="HEAD"):
        assert agent_blueprints_api._agent_request_requires_write() is False


def test_stored_viewer_cannot_start_agent_run_before_runner_effect(operator_role_database, monkeypatch):
    connection, schema = operator_role_database
    cursor = connection.cursor()
    cursor.execute("INSERT INTO business_members VALUES ('business-1', 'viewer-1', 'viewer', 'active')")
    cursor.execute(
        """
        INSERT INTO agent_blueprints
            (id, business_id, name, category, status, created_by_user_id, metadata_json)
        VALUES ('blueprint-1', 'business-1', 'Protected run', 'custom', 'draft', 'owner-1', '{}'::jsonb)
        """
    )
    connection.commit()

    app = Flask(__name__)
    app.register_blueprint(agent_blueprints_api.agent_blueprints_bp)

    def database_manager():
        return NativeDatabaseManager(isolated_test_dsn(), schema)

    class Runner:
        def __init__(self, *_args):
            raise AssertionError("viewer denial must happen before runner construction")

    monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", database_manager)
    monkeypatch.setattr(agent_blueprints_api, "AgentBlueprintRunner", Runner)
    monkeypatch.setattr(
        agent_blueprints_api,
        "require_auth_from_request",
        lambda: {"user_id": "viewer-1", "is_superadmin": False},
    )

    response = app.test_client().post("/api/agent-blueprints/blueprint-1/runs", json={})

    assert response.status_code == 403
    cursor.execute("SELECT COUNT(*) AS count FROM agent_runs")
    assert cursor.fetchone()["count"] == 0


def test_stored_viewer_cannot_approve_agent_run_before_runner_effect(operator_role_database, monkeypatch):
    connection, schema = operator_role_database
    cursor = connection.cursor()
    cursor.execute("INSERT INTO business_members VALUES ('business-1', 'viewer-1', 'viewer', 'active')")
    cursor.execute(
        """
        INSERT INTO agent_blueprints
            (id, business_id, name, category, status, created_by_user_id, metadata_json)
        VALUES ('blueprint-1', 'business-1', 'Protected approval', 'custom', 'draft', 'owner-1', '{}'::jsonb)
        """
    )
    cursor.execute("INSERT INTO agent_runs VALUES ('run-1', 'blueprint-1', 'pending')")
    connection.commit()

    app = Flask(__name__)
    app.register_blueprint(agent_blueprints_api.agent_blueprints_bp)

    def database_manager():
        return NativeDatabaseManager(isolated_test_dsn(), schema)

    class Runner:
        def __init__(self, *_args):
            raise AssertionError("viewer denial must happen before runner construction")

    monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", database_manager)
    monkeypatch.setattr(agent_blueprints_api, "AgentBlueprintRunner", Runner)
    monkeypatch.setattr(
        agent_blueprints_api,
        "require_auth_from_request",
        lambda: {"user_id": "viewer-1", "is_superadmin": False},
    )

    response = app.test_client().post("/api/agent-runs/run-1/approvals/approval-1/approve", json={})

    assert response.status_code == 403
    cursor.execute("SELECT status FROM agent_runs WHERE id = 'run-1'")
    assert cursor.fetchone()["status"] == "pending"


def test_stored_viewer_can_use_read_only_preflight_without_write_gate(operator_role_database, monkeypatch):
    connection, schema = operator_role_database
    cursor = connection.cursor()
    cursor.execute("INSERT INTO business_members VALUES ('business-1', 'viewer-1', 'viewer', 'active')")
    cursor.execute(
        """
        INSERT INTO agent_blueprints
            (id, business_id, name, category, status, created_by_user_id, metadata_json)
        VALUES ('blueprint-1', 'business-1', 'Read preflight', 'custom', 'draft', 'owner-1', '{}'::jsonb)
        """
    )
    connection.commit()

    app = Flask(__name__)
    app.register_blueprint(agent_blueprints_api.agent_blueprints_bp)

    def database_manager():
        return NativeDatabaseManager(isolated_test_dsn(), schema)

    def write_gate(*_args):
        raise AssertionError("read-only preflight must not use the write gate")

    monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", database_manager)
    monkeypatch.setattr(agent_blueprints_api, "verify_business_write_access", write_gate)
    monkeypatch.setattr(
        agent_blueprints_api,
        "require_auth_from_request",
        lambda: {"user_id": "viewer-1", "is_superadmin": False},
    )
    monkeypatch.setattr(agent_blueprints_api, "_resolve_candidate_version", lambda *_args: {"id": "version-1"})
    monkeypatch.setattr(agent_blueprints_api, "_resolve_active_version", lambda *_args: {"id": "version-1"})
    monkeypatch.setattr(agent_blueprints_api, "build_agent_integration_preflight", lambda *_args, **_kwargs: {"ready": False})
    monkeypatch.setattr(
        agent_blueprints_api,
        "_agent_connection_context",
        lambda *_args: {"attached_integrations": [], "available_integrations": [], "provider_catalog": []},
    )
    monkeypatch.setattr(agent_blueprints_api, "_activation_connection_plan_from_preflight", lambda *_args, **_kwargs: {})

    response = app.test_client().post("/api/agent-blueprints/blueprint-1/preflight", json={})

    assert response.status_code == 200, response.get_json()
    cursor.execute("SELECT COUNT(*) AS count FROM agent_blueprints")
    assert cursor.fetchone()["count"] == 1
    cursor.execute("SELECT COUNT(*) AS count FROM agent_runs")
    assert cursor.fetchone()["count"] == 0


def test_stored_viewer_cannot_start_custom_process_preview_before_runner_effect(operator_role_database, monkeypatch):
    connection, schema = operator_role_database
    cursor = connection.cursor()
    cursor.execute("INSERT INTO business_members VALUES ('business-1', 'viewer-1', 'viewer', 'active')")
    cursor.execute(
        """
        INSERT INTO agent_blueprints
            (id, business_id, name, category, status, created_by_user_id, metadata_json)
        VALUES ('blueprint-1', 'business-1', 'Protected custom preview', 'custom', 'draft', 'owner-1', '{}'::jsonb)
        """
    )
    connection.commit()

    app = Flask(__name__)
    app.register_blueprint(agent_blueprints_api.agent_blueprints_bp)

    def database_manager():
        return NativeDatabaseManager(isolated_test_dsn(), schema)

    class Runner:
        def __init__(self, *_args):
            raise AssertionError("viewer denial must happen before preview runner construction")

    monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", database_manager)
    monkeypatch.setattr(agent_blueprints_api, "AgentBlueprintRunner", Runner)
    monkeypatch.setattr(
        agent_blueprints_api,
        "require_auth_from_request",
        lambda: {"user_id": "viewer-1", "is_superadmin": False},
    )

    response = app.test_client().post("/api/agent-blueprints/blueprint-1/custom-process/preview", json={})

    assert response.status_code == 403
    cursor.execute("SELECT COUNT(*) AS count FROM agent_runs")
    assert cursor.fetchone()["count"] == 0


def test_stored_viewer_cannot_run_compiled_preview_before_state_effect(operator_role_database, monkeypatch):
    connection, schema = operator_role_database
    cursor = connection.cursor()
    cursor.execute("INSERT INTO business_members VALUES ('business-1', 'viewer-1', 'viewer', 'active')")
    cursor.execute(
        """
        INSERT INTO agent_blueprints
            (id, business_id, name, category, status, created_by_user_id, metadata_json)
        VALUES ('blueprint-1', 'business-1', 'Protected compiled preview', 'custom', 'draft', 'owner-1', '{}'::jsonb)
        """
    )
    cursor.execute("INSERT INTO agent_blueprint_versions VALUES ('version-1', 'blueprint-1', 'checking')")
    connection.commit()

    app = Flask(__name__)
    app.register_blueprint(agent_blueprints_api.agent_blueprints_bp)

    def database_manager():
        return NativeDatabaseManager(isolated_test_dsn(), schema)

    monkeypatch.setenv("COMPILED_SCRIPT_PREVIEW_ENABLED", "true")
    monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", database_manager)
    monkeypatch.setattr(agent_blueprints_api, "_require_current_compiled_account", lambda *_args: None)
    monkeypatch.setattr(
        agent_blueprints_api,
        "require_auth_from_request",
        lambda: {"user_id": "viewer-1", "is_superadmin": False},
    )

    response = app.test_client().post(
        "/api/agent-blueprints/blueprint-1/compiled-script/preview",
        json={"version_id": "version-1", "input": {}},
    )

    assert response.status_code == 403
    cursor.execute("SELECT compiled_state FROM agent_blueprint_versions WHERE id = 'version-1'")
    assert cursor.fetchone()["compiled_state"] == "checking"
