from flask import Flask

import api.parsing_admin_api


class FakeCursor:
    def __init__(self):
        self.description = []
        self.last_query = ""

    def execute(self, sql, _params=None):
        self.last_query = " ".join(str(sql).split()).lower()
        if "count(*)" in self.last_query:
            self.description = [("cnt",)]
        elif "select status" in self.last_query:
            self.description = [("status",), ("cnt",)]
        elif "select task_type" in self.last_query:
            self.description = [("task_type",), ("cnt",)]
        elif "select source" in self.last_query:
            self.description = [("source",), ("cnt",)]
        else:
            self.description = [("id",)]

    def fetchone(self):
        if "count(*)" in self.last_query:
            return (0,)
        return None

    def fetchall(self):
        return []


class FakeConnection:
    def __init__(self):
        self.cursor_instance = FakeCursor()
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def close(self):
        self.closed = True


class FakeDatabaseManager:
    def __init__(self):
        self.conn = FakeConnection()

    def close(self):
        self.conn.close()


def build_client(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(api.parsing_admin_api.parsing_admin_bp)
    monkeypatch.setattr(
        api.parsing_admin_api,
        "verify_session",
        lambda _token: {"user_id": "admin", "is_superadmin": True},
    )
    monkeypatch.setattr(api.parsing_admin_api, "DatabaseManager", FakeDatabaseManager)
    return app.test_client()


def test_parsing_tasks_returns_success_for_superadmin(monkeypatch):
    client = build_client(monkeypatch)

    response = client.get(
        "/api/admin/parsing/tasks?limit=50&offset=0",
        headers={"Authorization": "Bearer admin"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "tasks": [],
        "total": 0,
        "stats": {},
    }


def test_parsing_stats_returns_success_for_superadmin(monkeypatch):
    client = build_client(monkeypatch)

    response = client.get(
        "/api/admin/parsing/stats",
        headers={"Authorization": "Bearer admin"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["success"] is True
    assert payload["stats"]["total_tasks"] == 0


def test_parsing_runtime_settings_returns_current_mode(monkeypatch):
    client = build_client(monkeypatch)
    connection = FakeConnection()
    if hasattr(api.parsing_admin_api, "get_db_connection"):
        monkeypatch.setattr(api.parsing_admin_api, "get_db_connection", lambda: connection)
    monkeypatch.setattr(api.parsing_admin_api, "get_use_apify_map_parsing", lambda _conn: False)

    response = client.get(
        "/api/admin/parsing/runtime-settings",
        headers={"Authorization": "Bearer admin"},
    )

    assert response.status_code == 200
    assert response.get_json() == {
        "success": True,
        "settings": {"use_apify_map_parsing": False},
    }
    assert connection.closed is True


def test_completed_filter_keeps_legacy_done_tasks_compatible(monkeypatch):
    client = build_client(monkeypatch)

    response = client.get(
        "/api/admin/parsing/tasks?status=completed&limit=50&offset=0",
        headers={"Authorization": "Bearer admin"},
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True
