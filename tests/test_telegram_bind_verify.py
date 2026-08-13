from datetime import datetime, timedelta

import main
from database_manager import HybridRow


class _FakeCursor:
    def __init__(self):
        self._result = None
        self.user_update = None
        self.token_update = None

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        if "from telegrambindtokens" in normalized:
            self._result = HybridRow(
                {
                    "id": "token-id",
                    "user_id": "user-id",
                    "business_id": "business-id",
                    "expires_at": datetime.now() + timedelta(minutes=5),
                    "used": False,
                }
            )
        elif "select id from users where telegram_id" in normalized:
            self._result = None
        elif "update users" in normalized:
            self.user_update = params
            self._result = None
        elif "update telegrambindtokens" in normalized:
            self.token_update = params
            self._result = None
        elif "select email, name from users" in normalized:
            self._result = HybridRow({"email": "alik@example.test", "name": "Алик"})

    def fetchone(self):
        return self._result


class _FakeConnection:
    def __init__(self):
        self.cursor_instance = _FakeCursor()
        self.committed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True


class _FakeDatabaseManager:
    last_instance = None

    def __init__(self):
        self.conn = _FakeConnection()
        self.closed = False
        _FakeDatabaseManager.last_instance = self

    def close(self):
        self.closed = True


def test_bind_verify_accepts_postgres_hybrid_row(monkeypatch):
    monkeypatch.setattr(main, "DatabaseManager", _FakeDatabaseManager)

    response = main.app.test_client().post(
        "/api/telegram/bind/verify",
        json={"token": "valid-token", "telegram_id": "856586343"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "user": {"id": "user-id", "email": "alik@example.test", "name": "Алик"},
    }
    database = _FakeDatabaseManager.last_instance
    assert database is not None
    assert database.conn.committed is True
    assert database.conn.cursor_instance.user_update[0] == "856586343"
    assert database.conn.cursor_instance.token_update == ("business-id", "token-id")
