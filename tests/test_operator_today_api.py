from flask import Flask

from api import operator_api


class _Cursor:
    def execute(self, _query, _params=None):
        return None

    def fetchone(self):
        return {"name": "Тестовый бизнес", "network_id": None, "network_name": None}


class _Connection:
    def cursor(self):
        return _Cursor()


class _Database:
    def __init__(self):
        self.conn = _Connection()

    def close(self):
        return None


def _app():
    app = Flask(__name__)
    app.register_blueprint(operator_api.operator_bp)
    return app


def test_web_today_uses_verified_scope_and_canonical_builder(monkeypatch):
    scope = {
        "kind": "business",
        "id": "business-1",
        "name": "Тестовый бизнес",
        "business_ids": ["business-1"],
    }
    captured = {}
    monkeypatch.setenv("TELEGRAM_MINI_APP_TODAY_V2_ENABLED", "false")
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(operator_api, "DatabaseManager", _Database)
    monkeypatch.setattr(operator_api, "verify_business_access", lambda *_args: (True, "user-1"))
    monkeypatch.setattr(
        operator_api,
        "build_mobile_today",
        lambda _cursor, **kwargs: captured.update(kwargs) or {
            "scope": scope,
            "focus_action": {"title": "Ответить на отзывы"},
            "active_work": [],
            "changes_24h": [],
            "community_pulse": [],
            "completed_results": [],
        },
    )

    response = _app().test_client().get(
        "/api/operator/today?scope_type=business&scope_id=business-1"
    )

    assert response.status_code == 200
    assert response.get_json()["focus_action"]["title"] == "Ответить на отзывы"
    assert captured["user_id"] == "user-1"
    assert captured["scope"]["kind"] == "business"
    assert captured["scope"]["id"] == "business-1"
    assert captured["scope"]["business_ids"] == ["business-1"]


def test_web_today_rejects_unresolved_scope(monkeypatch):
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(operator_api, "DatabaseManager", _Database)
    monkeypatch.setattr(operator_api, "verify_business_access", lambda *_args: (False, None))

    response = _app().test_client().get(
        "/api/operator/today?scope_type=business&scope_id=foreign-business"
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "Раздел недоступен"


def test_web_today_requires_authentication(monkeypatch):
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: None)

    response = _app().test_client().get(
        "/api/operator/today?scope_type=business&scope_id=business-1"
    )

    assert response.status_code == 401


def test_web_today_rejects_non_business_scope(monkeypatch):
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(operator_api, "DatabaseManager", _Database)

    response = _app().test_client().get(
        "/api/operator/today?scope_type=network&scope_id=network-1"
    )

    assert response.status_code == 400
    assert response.get_json()["error"] == "Выберите бизнес"
