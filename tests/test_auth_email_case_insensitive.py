import auth_system
import pytest
from flask import Flask, jsonify, request
from api import auth_user_api
from core.email_delivery import build_password_setup_link


class FakeCursor:
    def __init__(self, rows, fetchall_rows=None):
        self.rows = list(rows)
        self.fetchall_rows = list(fetchall_rows or [])
        self.queries = []

    def execute(self, query, params=None):
        self.queries.append((query, params))

    def fetchone(self):
        if not self.rows:
            return None
        return self.rows.pop(0)

    def fetchall(self):
        return list(self.fetchall_rows)


class FakeConnection:
    def __init__(self, cursor):
        self.cursor_value = cursor
        self.closed = False

    def cursor(self):
        return self.cursor_value

    def close(self):
        self.closed = True

    def commit(self):
        pass


def test_authenticate_user_looks_up_email_case_insensitively(monkeypatch):
    password_hash = auth_system.hash_password("secret-password")
    cursor = FakeCursor(
        [
            {
                "id": "user-1",
                "email": "Eliseygoodmaps@yandex.ru",
                "password_hash": password_hash,
                "name": "Elisey",
                "phone": None,
                "is_active": True,
                "is_verified": True,
            }
        ]
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)

    result = auth_system.authenticate_user("  eliseygoodmaps@yandex.ru  ", "secret-password")

    assert result["id"] == "user-1"
    assert result["email"] == "Eliseygoodmaps@yandex.ru"
    assert "LOWER(email)" in cursor.queries[0][0]
    assert cursor.queries[0][1] == ("eliseygoodmaps@yandex.ru",)


def test_create_user_checks_duplicates_by_normalized_email(monkeypatch):
    cursor = FakeCursor([{"id": "existing-user"}])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)

    result = auth_system.create_user("Eliseygoodmaps@yandex.ru", "secret-password")

    assert result["error"] == "Пользователь с таким email уже существует"
    assert "LOWER(email)" in cursor.queries[0][0]
    assert cursor.queries[0][1] == ("eliseygoodmaps@yandex.ru",)


def test_authenticate_user_blocks_unverified_email(monkeypatch):
    password_hash = auth_system.hash_password("secret-password")
    cursor = FakeCursor(
        [
            {
                "id": "user-1",
                "email": "new@example.com",
                "password_hash": password_hash,
                "name": "New",
                "phone": None,
                "is_active": True,
                "is_verified": False,
            }
        ]
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)

    result = auth_system.authenticate_user("new@example.com", "secret-password")

    assert result["error"] == "EMAIL_NOT_VERIFIED"


def test_create_user_stores_consent_and_unverified_status(monkeypatch):
    columns = [
        {"column_name": "updated_at"},
        {"column_name": "verification_token"},
        {"column_name": "is_verified"},
        {"column_name": "personal_data_consent_at"},
        {"column_name": "personal_data_consent_version"},
        {"column_name": "privacy_accepted_at"},
        {"column_name": "terms_accepted_at"},
        {"column_name": "consent_ip"},
        {"column_name": "consent_user_agent"},
    ]
    cursor = FakeCursor([None], fetchall_rows=columns)
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)

    result = auth_system.create_user(
        "New@Example.com",
        "secret-password",
        personal_data_consent=True,
        consent_version="policy-v1",
        consent_ip="127.0.0.1",
        consent_user_agent="pytest",
        is_verified=False,
    )

    insert_query, insert_params = cursor.queries[2]
    assert result["email"] == "new@example.com"
    assert "personal_data_consent_at" in insert_query
    assert "is_verified" in insert_query
    assert False in insert_params
    assert "policy-v1" in insert_params


def test_create_password_setup_token_rotates_token_for_passwordless_user(monkeypatch):
    columns = [
        {"column_name": "verification_token"},
        {"column_name": "is_verified"},
        {"column_name": "updated_at"},
    ]
    cursor = FakeCursor(
        [
            {
                "id": "user-1",
                "email": "Manual@Example.com",
                "name": "Manual User",
                "phone": None,
                "password_hash": None,
                "is_active": True,
            }
        ],
        fetchall_rows=columns,
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)
    monkeypatch.setattr(auth_system.secrets, "token_urlsafe", lambda length: "setup-token")

    result = auth_system.create_password_setup_token("user-1")

    update_query, update_params = cursor.queries[2]
    assert result["success"] is True
    assert result["verification_token"] == "setup-token"
    assert "verification_token = %s" in update_query
    assert "is_verified = %s" in update_query
    assert update_params[0] == "setup-token"
    assert False in update_params


def test_create_password_setup_token_does_not_rotate_existing_password_user(monkeypatch):
    columns = [{"column_name": "verification_token"}]
    cursor = FakeCursor(
        [
            {
                "id": "user-1",
                "email": "user@example.com",
                "name": "User",
                "phone": None,
                "password_hash": "hash",
                "is_active": True,
            }
        ],
        fetchall_rows=columns,
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)

    result = auth_system.create_password_setup_token("user-1")

    assert result["error"] == "У пользователя уже установлен пароль"
    assert len(cursor.queries) == 2


def test_build_password_setup_link_encodes_email_and_token(monkeypatch):
    monkeypatch.setenv("PUBLIC_APP_URL", "https://localos.pro/")

    link = build_password_setup_link("User+test@example.com", "token/value")

    assert link == "https://localos.pro/set-password?email=User%2Btest%40example.com&token=token%2Fvalue"


def test_create_session_stores_demo_kind_scope_and_ttl(monkeypatch):
    cursor = FakeCursor([])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)
    monkeypatch.setattr(auth_system.secrets, "token_urlsafe", lambda length: "demo-token")

    token = auth_system.create_session(
        "user-1",
        session_kind="demo",
        scope_business_id="business-1",
        expires_days=14,
    )

    insert_query, insert_params = cursor.queries[0]
    assert token == "demo_demo-token"
    assert "session_kind" in insert_query
    assert "scope_business_id" in insert_query
    assert insert_params[-2:] == ("demo", "business-1")


def test_verify_session_returns_kind_and_scope(monkeypatch):
    cursor = FakeCursor(
        [
            (
                "user-1",
                "2099-01-01T00:00:00",
                "demo@example.com",
                "Demo",
                None,
                True,
                False,
                "session-1",
                "demo",
                "business-1",
            )
        ]
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)

    session = auth_system.verify_session("demo-token")

    assert session["session_id"] == "session-1"
    assert session["session_kind"] == "demo"
    assert session["scope_business_id"] == "business-1"


def test_verify_session_never_exposes_superadmin_through_demo_session(monkeypatch):
    cursor = FakeCursor(
        [
            (
                "user-1",
                "2099-01-01T00:00:00",
                "demo@example.com",
                "Demo",
                None,
                True,
                True,
                "session-1",
                "demo",
                "business-1",
            )
        ]
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)

    session = auth_system.verify_session("demo-token")

    assert session["session_kind"] == "demo"
    assert session["is_superadmin"] is False


def test_verify_session_falls_back_for_legacy_session_schema(monkeypatch):
    class MissingColumnCursor(FakeCursor):
        def execute(self, query, params=None):
            raise RuntimeError('column s.session_kind does not exist')

    legacy_cursor = FakeCursor(
        [("user-1", "2099-01-01T00:00:00", "user@example.com", "User", None, True, False)]
    )

    class LegacyConnection(FakeConnection):
        def __init__(self):
            super().__init__(MissingColumnCursor([]))
            self.cursor_calls = 0

        def cursor(self):
            self.cursor_calls += 1
            return self.cursor_value if self.cursor_calls == 1 else legacy_cursor

        def rollback(self):
            pass

    connection = LegacyConnection()
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)

    session = auth_system.verify_session("standard-token")

    assert session["user_id"] == "user-1"
    assert session["session_kind"] == "standard"
    assert session["scope_business_id"] is None


def _session_row(*, is_active=True, expires_at="2099-01-01T00:00:00"):
    return (
        "user-1",
        expires_at,
        "user@example.com",
        "User",
        None,
        is_active,
        False,
        "session-1",
        "standard",
        None,
    )


def _protected_mutation_app():
    app = Flask(__name__)
    writes = []

    @app.post("/protected-mutation")
    def protected_mutation():
        auth_header = request.headers.get("Authorization", "")
        token = auth_header[7:] if auth_header.startswith("Bearer ") else ""
        if not auth_system.verify_session(token):
            return jsonify({"error": "invalid_token"}), 401
        writes.append("mutation")
        return jsonify({"success": True})

    return app, writes


def test_verify_session_rejects_inactive_bearer_before_protected_mutation(monkeypatch):
    cursor = FakeCursor([_session_row(is_active=False)])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)
    app, writes = _protected_mutation_app()

    response = app.test_client().post(
        "/protected-mutation",
        headers={"Authorization": "Bearer inactive-token"},
    )

    assert response.status_code == 401
    assert response.get_json() == {"error": "invalid_token"}
    assert writes == []


def test_verify_session_keeps_active_bearer_usable_for_protected_mutation(monkeypatch):
    cursor = FakeCursor([_session_row(is_active=True)])
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)
    app, writes = _protected_mutation_app()

    response = app.test_client().post(
        "/protected-mutation",
        headers={"Authorization": "Bearer active-token"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True}
    assert writes == ["mutation"]


class SessionLookupCursor(FakeCursor):
    def __init__(self, rows_by_token):
        super().__init__([])
        self.rows_by_token = rows_by_token
        self.params = None

    def execute(self, query, params=None):
        super().execute(query, params)
        self.params = params

    def fetchone(self):
        token, expires_after = self.params
        row = self.rows_by_token.get(token)
        if row is None or row[1] <= expires_after:
            return None
        return row


def test_verify_session_rejects_missing_or_expired_bearer(monkeypatch):
    cursor = SessionLookupCursor(
        {"expired-token": _session_row(expires_at="2000-01-01T00:00:00")}
    )
    connection = FakeConnection(cursor)
    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)

    assert auth_system.verify_session("missing-token") is None
    assert auth_system.verify_session("expired-token") is None
    assert "s.expires_at >" in cursor.queries[0][0]


def test_auth_me_keeps_account_blocked_contract_without_enabling_mutations(monkeypatch):
    calls = []

    def fake_verify_session(token, *, include_inactive=False):
        calls.append((token, include_inactive))
        if include_inactive:
            return {"user_id": "user-1", "is_active": False}
        return None

    monkeypatch.setattr(auth_user_api, "verify_session", fake_verify_session)
    app = Flask(__name__)
    app.register_blueprint(auth_user_api.auth_user_bp)

    response = app.test_client().get(
        "/api/auth/me",
        headers={"Authorization": "Bearer inactive-token"},
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "account_blocked"
    assert calls == [("inactive-token", True)]


@pytest.mark.parametrize("inactive_value", [False, 0, "0"])
def test_auth_me_blocks_all_legacy_inactive_values_without_profile_lookup(
    monkeypatch,
    inactive_value,
):
    cursor = FakeCursor([_session_row(is_active=inactive_value)])
    connection = FakeConnection(cursor)
    profile_lookup_calls = []

    class ProfileLookupMustNotRun:
        def __init__(self):
            profile_lookup_calls.append("created")

    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)
    monkeypatch.setattr(auth_user_api, "DatabaseManager", ProfileLookupMustNotRun)
    app = Flask(__name__)
    app.register_blueprint(auth_user_api.auth_user_bp)

    response = app.test_client().get(
        "/api/auth/me",
        headers={"Authorization": "Bearer inactive-token"},
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "account_blocked",
        "message": "user is blocked",
    }
    assert profile_lookup_calls == []


def test_auth_me_keeps_real_active_session_usable(monkeypatch):
    cursor = FakeCursor([_session_row(is_active=True)])
    connection = FakeConnection(cursor)

    class ActiveProfileDatabase:
        def is_superadmin(self, _user_id):
            return False

        def get_businesses_for_user_access(self, _user_id):
            return [{"id": "business-1", "name": "Active business"}]

        def close(self):
            return None

    monkeypatch.setattr(auth_system, "get_db_connection", lambda: connection)
    monkeypatch.setattr(auth_user_api, "DatabaseManager", ActiveProfileDatabase)
    app = Flask(__name__)
    app.register_blueprint(auth_user_api.auth_user_bp)

    response = app.test_client().get(
        "/api/auth/me",
        headers={"Authorization": "Bearer active-token"},
    )

    assert response.status_code == 200
    assert response.get_json()["user"]["id"] == "user-1"


def test_login_keeps_account_blocked_contract(monkeypatch):
    import main

    monkeypatch.setattr(
        main,
        "authenticate_user",
        lambda _email, _password: {"error": "account_blocked"},
    )

    response = main.app.test_client().post(
        "/api/auth/login",
        json={"email": "inactive@example.com", "password": "secret-password"},
    )

    assert response.status_code == 403
    assert response.get_json() == {
        "error": "account_blocked",
        "message": "user is blocked",
    }
