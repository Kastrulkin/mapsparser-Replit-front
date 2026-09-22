"""Native PostgreSQL proof that Google OAuth callbacks re-check current access.

The provider and credential encryption are intentionally fake.  Authorization,
locking, transactions, commits, and rollback are the real Flask/PostgreSQL path
against schema-local copies of the migrated production tables.
"""

import uuid

from flask import Flask
import psycopg2
from psycopg2 import sql
from psycopg2.errors import LockNotAvailable
from psycopg2.extras import RealDictCursor
import pytest

import database_manager
from api import google_business_api
from database_manager import DBConnectionWrapper
from tests.test_action_orchestrator_callback_recovery_pg import isolated_test_dsn


TABLES = ("users", "businesses", "externalbusinessaccounts", "agent_integrations")


def _schema_identity(cursor, schema):
    cursor.execute(
        "SELECT oid, pg_get_userbyid(nspowner) AS owner FROM pg_namespace WHERE nspname = %s",
        (schema,),
    )
    row = cursor.fetchone()
    if not row:
        return None
    return (int(row["oid"]), str(row["owner"]))


def _connection(database, *, search_path=True):
    connection = None
    cursor = None
    try:
        connection = psycopg2.connect(database["database_url"], cursor_factory=RealDictCursor)
        cursor = connection.cursor()
        cursor.execute("SET statement_timeout TO '5s'")
        cursor.execute("SET lock_timeout TO '1s'")
        if search_path:
            cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(database["schema"])))
        connection.commit()
        cursor.close()
        return connection
    except Exception:
        if cursor:
            cursor.close()
        if connection:
            connection.close()
        raise


def _database_manager_connection(database):
    return DBConnectionWrapper(_connection(database))


@pytest.fixture
def oauth_database():
    database_url = isolated_test_dsn()
    schema = "callback_recovery_" + uuid.uuid4().hex
    connection = psycopg2.connect(database_url, cursor_factory=RealDictCursor)
    cursor = connection.cursor()
    identity = None
    try:
        cursor.execute("SET statement_timeout TO '5s'")
        cursor.execute("SET lock_timeout TO '1s'")
        if _schema_identity(cursor, schema):
            raise RuntimeError("fresh OAuth schema unexpectedly already exists")
        cursor.execute(sql.SQL("CREATE SCHEMA {}").format(sql.Identifier(schema)))
        identity = _schema_identity(cursor, schema)
        cursor.execute("SELECT current_user AS owner")
        expected_owner = str(cursor.fetchone()["owner"])
        if not identity or identity[1] != expected_owner:
            raise RuntimeError("OAuth schema identity was not created for the current test owner")
        cursor.execute(sql.SQL("SET search_path TO {}").format(sql.Identifier(schema)))
        for table_name in TABLES:
            cursor.execute(
                sql.SQL("CREATE TABLE {} (LIKE public.{} INCLUDING ALL)").format(
                    sql.Identifier(table_name),
                    sql.Identifier(table_name),
                )
            )
        connection.commit()
        yield {"database_url": database_url, "schema": schema}
    finally:
        try:
            connection.rollback()
            if identity and _schema_identity(cursor, schema) == identity:
                cursor.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(sql.Identifier(schema)))
                connection.commit()
            elif identity:
                raise RuntimeError("refusing OAuth schema cleanup after identity changed")
        finally:
            cursor.close()
            connection.close()


def _execute(database, statement, params=()):
    connection = _connection(database)
    cursor = connection.cursor()
    try:
        cursor.execute(statement, params)
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def _row(database, statement, params=()):
    connection = _connection(database)
    cursor = connection.cursor()
    try:
        cursor.execute(statement, params)
        result = cursor.fetchone()
        return dict(result) if result else None
    finally:
        cursor.close()
        connection.close()


def _seed_access(database, *, admin=False):
    actor_id = "actor-" + uuid.uuid4().hex
    business_id = "business-" + uuid.uuid4().hex
    owner_id = "other-owner" if admin else actor_id
    _execute(
        database,
        "INSERT INTO users (id, email, is_active, is_superadmin) VALUES (%s, %s, TRUE, %s)",
        (actor_id, actor_id + "@example.invalid", admin),
    )
    _execute(
        database,
        "INSERT INTO businesses (id, owner_id, name, is_active) VALUES (%s, %s, %s, TRUE)",
        (business_id, owner_id, "OAuth access proof"),
    )
    return {"actor_id": actor_id, "business_id": business_id}


def _account(database, *, business_id, source, account_id=None, encrypted="previous-encrypted"):
    value = account_id or ("account-" + uuid.uuid4().hex)
    _execute(
        database,
        """
        INSERT INTO externalbusinessaccounts
            (id, business_id, source, external_id, display_name, auth_data_encrypted, is_active)
        VALUES (%s, %s, %s, %s, %s, %s, TRUE)
        """,
        (value, business_id, source, "previous-id", "Previous account", encrypted),
    )
    return value


@pytest.fixture(params=("google_business", "google_sheets"))
def callback(request, monkeypatch, oauth_database):
    purpose = request.param
    monkeypatch.setenv("GOOGLE_OAUTH_STATE_SECRET", "native-oauth-current-access-test-secret")
    monkeypatch.setenv("FRONTEND_URL", "https://frontend.invalid")
    monkeypatch.setattr(
        database_manager,
        "get_db_connection",
        lambda: _database_manager_connection(oauth_database),
    )
    control = {"exchange_calls": 0, "exchange_hook": None}

    class Provider:
        def get_credentials_from_code(self, code):
            assert code == "native-code"
            control["exchange_calls"] += 1
            hook = control["exchange_hook"]
            if hook:
                hook()
            return {"provider": "fake"}

        def credentials_to_dict(self, credentials):
            assert credentials == {"provider": "fake"}
            return {"token": "fake-token", "refresh_token": "fake-refresh"}

        def get_account_identity(self, credentials):
            assert credentials == {"provider": "fake"}
            return {"email": "oauth@example.invalid", "name": "OAuth proof"}

        def list_accounts(self):
            return []

    monkeypatch.setattr(google_business_api, "GoogleBusinessAuth", Provider)
    monkeypatch.setattr(google_business_api, "GoogleSheetsAuth", Provider)
    monkeypatch.setattr(google_business_api, "GoogleBusinessAPI", lambda credentials: Provider())
    monkeypatch.setattr(google_business_api, "encrypt_auth_data", lambda payload: "encrypted:" + payload)

    app = Flask("google-oauth-current-access-pg")
    app.register_blueprint(google_business_api.google_business_bp)

    def invoke(ids):
        state = google_business_api._encode_google_oauth_state(
            ids["actor_id"],
            ids["business_id"],
            "/dashboard/settings/integrations",
            purpose,
        )
        route = "/api/google/oauth/callback" if purpose == "google_business" else "/api/google/sheets/oauth/callback"
        return app.test_client().get(route, query_string={"code": "native-code", "state": state})

    return {"database": oauth_database, "purpose": purpose, "control": control, "invoke": invoke}


def _revoke(database, ids, revocation):
    if revocation == "owner":
        _execute(database, "UPDATE businesses SET owner_id = %s WHERE id = %s", ("revoked-owner", ids["business_id"]))
    elif revocation == "admin":
        _execute(database, "UPDATE users SET is_superadmin = FALSE WHERE id = %s", (ids["actor_id"],))
    elif revocation == "inactive":
        _execute(database, "UPDATE users SET is_active = FALSE WHERE id = %s", (ids["actor_id"],))
    else:
        raise AssertionError("unknown revocation")


def _account_count(database, business_id, source):
    row = _row(
        database,
        "SELECT COUNT(*) AS count FROM externalbusinessaccounts WHERE business_id = %s AND source = %s",
        (business_id, source),
    )
    return int(row["count"])


@pytest.mark.parametrize("revocation", ("owner", "admin", "inactive"))
def test_callback_denies_revoked_access_before_provider_exchange(callback, revocation):
    database = callback["database"]
    ids = _seed_access(database, admin=revocation == "admin")
    _revoke(database, ids, revocation)

    response = callback["invoke"](ids)

    assert response.status_code == 302
    assert "google_auth=error" in response.location
    assert callback["control"]["exchange_calls"] == 0
    assert _account_count(database, ids["business_id"], callback["purpose"]) == 0


@pytest.mark.parametrize("revocation", ("owner", "admin", "inactive"))
def test_callback_denies_revocation_committed_during_provider_exchange(callback, revocation):
    database = callback["database"]
    ids = _seed_access(database, admin=revocation == "admin")
    account_id = _account(database, business_id=ids["business_id"], source=callback["purpose"])
    integration_id = None
    legacy_id = None
    if callback["purpose"] == "google_sheets":
        legacy_id = _account(database, business_id=ids["business_id"], source="google_business")
        integration_id = "integration-" + uuid.uuid4().hex
        _execute(
            database,
            """
            INSERT INTO agent_integrations (id, business_id, provider, status, auth_ref)
            VALUES (%s, %s, 'google_sheets', 'active', %s)
            """,
            (integration_id, ids["business_id"], legacy_id),
        )
    callback["control"]["exchange_hook"] = lambda: _revoke(database, ids, revocation)

    response = callback["invoke"](ids)

    assert response.status_code == 302
    assert "google_auth=error" in response.location
    assert callback["control"]["exchange_calls"] == 1
    account = _row(database, "SELECT auth_data_encrypted FROM externalbusinessaccounts WHERE id = %s", (account_id,))
    assert account["auth_data_encrypted"] == "previous-encrypted"
    if integration_id:
        integration = _row(database, "SELECT auth_ref FROM agent_integrations WHERE id = %s", (integration_id,))
        assert integration["auth_ref"] == legacy_id


@pytest.mark.parametrize("existing", (False, True))
@pytest.mark.parametrize("admin", (False, True))
def test_callback_persists_authorized_insert_and_update_for_each_route(callback, existing, admin):
    database = callback["database"]
    ids = _seed_access(database, admin=admin)
    existing_id = None
    if existing:
        existing_id = _account(database, business_id=ids["business_id"], source=callback["purpose"])
    if callback["purpose"] == "google_sheets":
        legacy_id = _account(database, business_id=ids["business_id"], source="google_business")
        _execute(
            database,
            """
            INSERT INTO agent_integrations (id, business_id, provider, status, auth_ref)
            VALUES (%s, %s, 'google_sheets', 'active', %s)
            """,
            ("integration-" + uuid.uuid4().hex, ids["business_id"], legacy_id),
        )

    response = callback["invoke"](ids)

    assert response.status_code == 302
    assert "google_auth=success" in response.location
    account = _row(
        database,
        """
        SELECT id, auth_data_encrypted, is_active
        FROM externalbusinessaccounts WHERE business_id = %s AND source = %s
        """,
        (ids["business_id"], callback["purpose"]),
    )
    assert account
    if existing:
        assert account["id"] == existing_id
    assert account["auth_data_encrypted"].startswith("encrypted:")
    assert account["is_active"] is True
    if callback["purpose"] == "google_sheets":
        integration = _row(
            database,
            "SELECT auth_ref FROM agent_integrations WHERE business_id = %s AND provider = 'google_sheets'",
            (ids["business_id"],),
        )
        assert integration["auth_ref"] == account["id"]


def _assert_for_update_is_blocked(database, ids):
    connection = _connection(database)
    cursor = connection.cursor()
    try:
        for table_name, identifier in (("users", ids["actor_id"]), ("businesses", ids["business_id"])):
            try:
                cursor.execute(
                    sql.SQL("SELECT id FROM {} WHERE id = %s FOR UPDATE NOWAIT").format(sql.Identifier(table_name)),
                    (identifier,),
                )
            except LockNotAvailable:
                connection.rollback()
            else:
                raise AssertionError("OAuth persistence did not retain its FOR SHARE lock")
    finally:
        cursor.close()
        connection.close()


def _assert_for_update_is_released(database, ids):
    connection = _connection(database)
    cursor = connection.cursor()
    try:
        for table_name, identifier in (("users", ids["actor_id"]), ("businesses", ids["business_id"])):
            cursor.execute(
                sql.SQL("SELECT id FROM {} WHERE id = %s FOR UPDATE NOWAIT").format(sql.Identifier(table_name)),
                (identifier,),
            )
            connection.rollback()
    finally:
        cursor.close()
        connection.close()


def test_callback_locks_current_access_rows_only_while_persisting(callback, monkeypatch):
    database = callback["database"]
    ids = _seed_access(database)
    original_auth_data_column = google_business_api._auth_data_column
    observations = []

    def verify_lock(cursor):
        _assert_for_update_is_blocked(database, ids)
        observations.append("locked")
        return original_auth_data_column(cursor)

    monkeypatch.setattr(google_business_api, "_auth_data_column", verify_lock)

    response = callback["invoke"](ids)

    assert response.status_code == 302
    assert "google_auth=success" in response.location
    assert observations == ["locked"]
    _assert_for_update_is_released(database, ids)


def _install_write_failure_trigger(database):
    connection = _connection(database)
    cursor = connection.cursor()
    try:
        function_name = "reject_oauth_write_" + uuid.uuid4().hex
        trigger_name = "reject_oauth_write_" + uuid.uuid4().hex
        cursor.execute(
            sql.SQL(
                "CREATE FUNCTION {}() RETURNS trigger LANGUAGE plpgsql AS "
                "$$ BEGIN RAISE EXCEPTION 'forced deferred OAuth persistence failure'; END; $$"
            ).format(sql.Identifier(function_name))
        )
        cursor.execute(
            sql.SQL("CREATE CONSTRAINT TRIGGER {} AFTER UPDATE ON externalbusinessaccounts "
                    "DEFERRABLE INITIALLY DEFERRED FOR EACH ROW EXECUTE FUNCTION {}()").format(
                sql.Identifier(trigger_name),
                sql.Identifier(function_name),
            )
        )
        connection.commit()
    finally:
        cursor.close()
        connection.close()


def test_callback_rolls_back_previous_credentials_and_releases_locks_on_late_write_failure(callback):
    database = callback["database"]
    ids = _seed_access(database)
    account_id = _account(database, business_id=ids["business_id"], source=callback["purpose"])
    integration_id = None
    if callback["purpose"] == "google_sheets":
        legacy_id = _account(database, business_id=ids["business_id"], source="google_business")
        integration_id = "integration-" + uuid.uuid4().hex
        _execute(
            database,
            """
            INSERT INTO agent_integrations (id, business_id, provider, status, auth_ref)
            VALUES (%s, %s, 'google_sheets', 'active', %s)
            """,
            (integration_id, ids["business_id"], legacy_id),
        )
    _install_write_failure_trigger(database)

    response = callback["invoke"](ids)

    assert response.status_code == 302
    assert "google_auth=error" in response.location
    account = _row(
        database,
        "SELECT auth_data_encrypted FROM externalbusinessaccounts WHERE id = %s",
        (account_id,),
    )
    assert account["auth_data_encrypted"] == "previous-encrypted"
    if integration_id:
        integration = _row(database, "SELECT auth_ref FROM agent_integrations WHERE id = %s", (integration_id,))
        assert integration["auth_ref"] == legacy_id
    _assert_for_update_is_released(database, ids)
