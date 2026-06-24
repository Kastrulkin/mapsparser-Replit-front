from flask import Flask

import messengers_api


class FakeProfileCursor:
    def __init__(self):
        self.queries = []
        self.last_result = None
        self.update_sql = ""
        self.update_values = []

    def execute(self, sql, params=None):
        self.queries.append((sql, params))
        normalized = " ".join(str(sql).lower().split())
        if "select owner_id from businesses" in normalized:
            self.last_result = {"owner_id": "user-1"}
            return
        if "information_schema.columns" in normalized:
            self.last_result = [
                {"column_name": "owner_id"},
                {"column_name": "telegram_bot_token"},
                {"column_name": "telegram_chat_id"},
                {"column_name": "updated_at"},
            ]
            return
        if normalized.startswith("update businesses"):
            self.update_sql = str(sql)
            self.update_values = list(params or [])
            self.last_result = None
            return
        self.last_result = None

    def fetchone(self):
        if isinstance(self.last_result, list):
            return self.last_result[0] if self.last_result else None
        return self.last_result

    def fetchall(self):
        return self.last_result if isinstance(self.last_result, list) else []


class FakeProfileDb:
    last_cursor = None
    committed = False
    closed = False

    def __init__(self):
        self.cursor_obj = FakeProfileCursor()
        FakeProfileDb.last_cursor = self.cursor_obj
        FakeProfileDb.committed = False
        FakeProfileDb.closed = False
        self.conn = self

    def cursor(self):
        return self.cursor_obj

    def commit(self):
        FakeProfileDb.committed = True

    def close(self):
        FakeProfileDb.closed = True


def test_business_profile_can_save_telegram_chat_id_without_business_bot_token(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(messengers_api.messengers_bp)
    monkeypatch.setattr(messengers_api, "require_auth", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(messengers_api, "DatabaseManager", FakeProfileDb)

    response = app.test_client().put(
        "/api/business/profile",
        json={"business_id": "biz-1", "telegram_chat_id": "@localos_proof"},
    )

    payload = response.get_json()
    cursor = FakeProfileDb.last_cursor
    assert response.status_code == 200
    assert payload["success"] is True
    assert FakeProfileDb.committed is True
    assert FakeProfileDb.closed is True
    assert "telegram_chat_id = %s" in cursor.update_sql
    assert "telegram_bot_token = %s" not in cursor.update_sql
    assert cursor.update_values == ["@localos_proof", "biz-1"]
