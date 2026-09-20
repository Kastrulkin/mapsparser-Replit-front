from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone

import auth_system
import main
from database_manager import DBConnectionWrapper
from psycopg2.extras import RealDictRow


class _ResetDatabase:
    def __init__(self, *, reset_expires_at: datetime, fail_session_revoke: bool = False):
        self.fail_session_revoke = fail_session_revoke
        self.connections = []
        self.state = {
            "users": {
                "user-1": {
                    "id": "user-1",
                    "email": "owner@example.com",
                    "password_hash": auth_system.hash_password("old-password"),
                    "reset_token": "valid-reset-token",
                    "reset_token_expires": reset_expires_at,
                    "is_active": True,
                    "is_superadmin": False,
                },
                "user-2": {
                    "id": "user-2",
                    "email": "other@example.com",
                    "password_hash": auth_system.hash_password("other-password"),
                    "reset_token": None,
                    "reset_token_expires": None,
                    "is_active": True,
                    "is_superadmin": False,
                },
            },
            "sessions": {
                "old-owner-session": {"user_id": "user-1", "expires_at": datetime.now() + timedelta(days=7)},
                "other-user-session": {"user_id": "user-2", "expires_at": datetime.now() + timedelta(days=7)},
            },
        }

    def connection(self):
        connection = _ResetConnection(self)
        self.connections.append(connection)
        return connection


class _ResetConnection:
    """A small transactional PostgreSQL-shaped fake: uncommitted writes are discarded."""

    def __init__(self, database: _ResetDatabase):
        self._database = database
        self.state = copy.deepcopy(database.state)
        self.closed = False
        self.committed = False
        self.rolled_back = False
        self.queries = []

    def cursor(self):
        return _ResetCursor(self)

    def commit(self):
        self._database.state = copy.deepcopy(self.state)
        self.committed = True

    def rollback(self):
        self.rolled_back = True
        self.state = copy.deepcopy(self._database.state)

    def close(self):
        self.closed = True


class _ResetCursor:
    def __init__(self, connection: _ResetConnection):
        self.connection = connection
        self._row = None
        self.rowcount = 0

    def execute(self, query, params=None):
        normalized = " ".join(query.lower().split())
        params = params or ()
        self.connection.queries.append((query, params))
        self._row = None
        self.rowcount = 0

        if "select id, reset_token, reset_token_expires" in normalized:
            email, token = params
            row = next(
                (
                    user
                    for user in self.connection.state["users"].values()
                    if user["email"].lower() == email and user["reset_token"] == token
                ),
                None,
            )
            self._row = RealDictRow(
                (key, row[key]) for key in ("id", "reset_token", "reset_token_expires")
            ) if row else None
            return

        if "select id from users where id" in normalized:
            user = self.connection.state["users"].get(params[0])
            self._row = {"id": user["id"]} if user else None
            return

        if "from usersessions s" in normalized and "join users u" in normalized:
            token = params[0]
            session = self.connection.state["sessions"].get(token)
            if not session or session["expires_at"] <= datetime.now():
                return
            user = self.connection.state["users"][session["user_id"]]
            self._row = {
                "user_id": user["id"],
                "expires_at": session["expires_at"],
                "email": user["email"],
                "name": None,
                "phone": None,
                "is_active": user["is_active"],
                "is_superadmin": user["is_superadmin"],
                "session_id": token,
                "session_kind": "standard",
                "scope_business_id": None,
            }
            return

        if normalized.startswith("update users"):
            user_id = params[-1]
            user = self.connection.state["users"][user_id]
            if "password_hash" in normalized:
                user["password_hash"] = params[0]
            if "reset_token = null" in normalized:
                user["reset_token"] = None
                user["reset_token_expires"] = None
            self.rowcount = 1
            return

        if normalized.startswith("delete from usersessions where user_id"):
            if self.connection._database.fail_session_revoke:
                raise RuntimeError("synthetic session delete failure")
            user_id = params[0]
            deleted = [token for token, session in self.connection.state["sessions"].items() if session["user_id"] == user_id]
            for token in deleted:
                del self.connection.state["sessions"][token]
            self.rowcount = len(deleted)
            return

        raise AssertionError(f"Unexpected query: {query}")

    def fetchone(self):
        return self._row


def _install_database(monkeypatch, database: _ResetDatabase):
    # main uses the compatibility wrapper; auth_system uses raw RealDictCursor.
    monkeypatch.setattr(main, "get_db_connection", lambda: DBConnectionWrapper(database.connection()))
    monkeypatch.setattr(auth_system, "get_db_connection", database.connection)


def test_confirm_reset_accepts_runtime_hybrid_row_and_revokes_only_reset_users_sessions(monkeypatch):
    database = _ResetDatabase(reset_expires_at=datetime.now() + timedelta(hours=1))
    _install_database(monkeypatch, database)
    monkeypatch.setattr(auth_system, "set_password", lambda *_args: (_ for _ in ()).throw(AssertionError("nested set_password")))

    response = main.app.test_client().post(
        "/api/auth/confirm-reset",
        json={"email": "owner@example.com", "token": "valid-reset-token", "password": "new-password"},
    )

    assert response.status_code == 200
    assert response.get_json() == {"success": True, "message": "Пароль успешно изменен"}
    owner = database.state["users"]["user-1"]
    assert auth_system.verify_password("new-password", owner["password_hash"])
    assert owner["reset_token"] is None
    assert owner["reset_token_expires"] is None
    assert auth_system.verify_session("old-owner-session") is None
    assert auth_system.verify_session("other-user-session")["user_id"] == "user-2"
    route_connection = database.connections[0]
    assert route_connection.committed is True
    assert route_connection.closed is True
    assert "FOR UPDATE" in route_connection.queries[0][0]


def test_confirm_reset_rejects_expired_token_without_changing_password_or_sessions(monkeypatch):
    database = _ResetDatabase(reset_expires_at=datetime.now() - timedelta(seconds=1))
    _install_database(monkeypatch, database)
    before = copy.deepcopy(database.state)

    response = main.app.test_client().post(
        "/api/auth/confirm-reset",
        json={"email": "owner@example.com", "token": "valid-reset-token", "password": "new-password"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Токен истек"}
    assert database.state == before
    assert database.connections[0].closed is True
    assert database.connections[0].committed is False


def test_confirm_reset_rejects_invalid_token_without_changing_password_or_sessions(monkeypatch):
    database = _ResetDatabase(reset_expires_at=datetime.now() + timedelta(hours=1))
    _install_database(monkeypatch, database)
    before = copy.deepcopy(database.state)

    response = main.app.test_client().post(
        "/api/auth/confirm-reset",
        json={"email": "owner@example.com", "token": "wrong-token", "password": "new-password"},
    )

    assert response.status_code == 400
    assert response.get_json() == {"error": "Неверный токен"}
    assert database.state == before
    assert database.connections[0].closed is True
    assert database.connections[0].committed is False


def test_confirm_reset_rolls_back_password_and_token_when_session_revocation_fails(monkeypatch):
    database = _ResetDatabase(
        reset_expires_at=datetime.now() + timedelta(hours=1),
        fail_session_revoke=True,
    )
    _install_database(monkeypatch, database)
    before = copy.deepcopy(database.state)

    response = main.app.test_client().post(
        "/api/auth/confirm-reset",
        json={"email": "owner@example.com", "token": "valid-reset-token", "password": "new-password"},
    )

    assert response.status_code == 500
    assert database.state == before
    assert database.connections[0].rolled_back is True
    assert database.connections[0].closed is True


def test_confirm_reset_rejects_non_object_or_wrongly_typed_payload_without_writes(monkeypatch):
    database = _ResetDatabase(reset_expires_at=datetime.now() + timedelta(hours=1))
    _install_database(monkeypatch, database)
    before = copy.deepcopy(database.state)
    client = main.app.test_client()

    non_object = client.post(
        "/api/auth/confirm-reset",
        json=["not", "an", "object"],
        environ_overrides={"REMOTE_ADDR": "127.0.0.21"},
    )
    wrong_type = client.post(
        "/api/auth/confirm-reset",
        json={"email": "owner@example.com", "token": 123, "password": "new-password"},
        environ_overrides={"REMOTE_ADDR": "127.0.0.22"},
    )

    assert non_object.status_code == 400
    assert wrong_type.status_code == 400
    assert database.state == before


def test_confirm_reset_consumes_an_iso_timestamp_token_once(monkeypatch):
    database = _ResetDatabase(reset_expires_at=datetime.now() + timedelta(hours=1))
    database.state["users"]["user-1"]["reset_token_expires"] = database.state["users"]["user-1"]["reset_token_expires"].isoformat()
    _install_database(monkeypatch, database)
    client = main.app.test_client()
    payload = {"email": "owner@example.com", "token": "valid-reset-token", "password": "new-password"}

    first = client.post("/api/auth/confirm-reset", json=payload, environ_overrides={"REMOTE_ADDR": "127.0.0.31"})
    replay = client.post("/api/auth/confirm-reset", json=payload, environ_overrides={"REMOTE_ADDR": "127.0.0.32"})

    assert first.status_code == 200
    assert replay.status_code == 400
    assert replay.get_json() == {"error": "Неверный токен"}


def test_confirm_reset_accepts_an_aware_postgres_expiry(monkeypatch):
    database = _ResetDatabase(reset_expires_at=datetime.now(timezone.utc) + timedelta(hours=1))
    _install_database(monkeypatch, database)

    response = main.app.test_client().post(
        "/api/auth/confirm-reset",
        json={"email": "owner@example.com", "token": "valid-reset-token", "password": "new-password"},
        environ_overrides={"REMOTE_ADDR": "127.0.0.41"},
    )

    assert response.status_code == 200
