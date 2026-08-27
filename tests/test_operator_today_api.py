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
    monkeypatch.setattr(operator_api, "resolve_control_scope", lambda *_args, **_kwargs: scope)
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
    monkeypatch.setattr(operator_api, "resolve_control_scope", lambda *_args, **_kwargs: None)

    response = _app().test_client().get(
        "/api/operator/today?scope_type=business&scope_id=foreign-business"
    )

    assert response.status_code == 403
    assert response.get_json()["error"] == "Раздел недоступен"


def test_mobile_feed_uses_verified_scope_and_cursor(monkeypatch):
    scope = {"kind": "network", "id": "network-1", "name": "Сеть", "business_ids": ["b-1", "b-2"]}
    captured = {}
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(operator_api, "DatabaseManager", _Database)
    monkeypatch.setattr(operator_api, "resolve_control_scope", lambda *_args, **_kwargs: scope)
    monkeypatch.setattr(
        operator_api,
        "build_mobile_feed",
        lambda _cursor, **kwargs: captured.update(kwargs) or {
            "scope": scope,
            "topics": [],
            "items": [{"id": "message-1", "url": "https://t.me/channel/1"}],
            "cursor": None,
        },
    )

    response = _app().test_client().get(
        "/api/operator/mobile/feed?scope_type=network&scope_id=network-1&limit=15&cursor=next-page"
    )

    assert response.status_code == 200
    assert response.get_json()["items"][0]["url"] == "https://t.me/channel/1"
    assert captured["scope"] == scope
    assert captured["limit"] == 15
    assert captured["page_cursor"] == "next-page"


def test_mobile_feed_rejects_unresolved_scope(monkeypatch):
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(operator_api, "DatabaseManager", _Database)
    monkeypatch.setattr(operator_api, "resolve_control_scope", lambda *_args, **_kwargs: None)

    response = _app().test_client().get(
        "/api/operator/mobile/feed?scope_type=business&scope_id=foreign-business"
    )

    assert response.status_code == 403


def test_web_feed_uses_same_verified_scope_and_builder(monkeypatch):
    scope = {"kind": "business", "id": "business-1", "name": "Бизнес", "business_ids": ["business-1"]}
    captured = {}
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(operator_api, "DatabaseManager", _Database)
    monkeypatch.setattr(operator_api, "resolve_control_scope", lambda *_args, **_kwargs: scope)
    monkeypatch.setattr(
        operator_api,
        "build_mobile_feed",
        lambda _cursor, **kwargs: captured.update(kwargs) or {
            "scope": scope,
            "topics": [{"id": "topic-1", "title": "Локальный маркетинг"}],
            "items": [],
            "cursor": None,
        },
    )

    response = _app().test_client().get(
        "/api/operator/feed?scope_type=business&scope_id=business-1&limit=12"
    )

    assert response.status_code == 200
    assert response.get_json()["topics"][0]["title"] == "Локальный маркетинг"
    assert captured["scope"] == scope
    assert captured["limit"] == 12


def test_web_feed_rejects_unresolved_scope(monkeypatch):
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(operator_api, "DatabaseManager", _Database)
    monkeypatch.setattr(operator_api, "resolve_control_scope", lambda *_args, **_kwargs: None)

    response = _app().test_client().get(
        "/api/operator/feed?scope_type=business&scope_id=foreign-business"
    )

    assert response.status_code == 403


def test_web_today_requires_authentication(monkeypatch):
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: None)

    response = _app().test_client().get(
        "/api/operator/today?scope_type=business&scope_id=business-1"
    )

    assert response.status_code == 401


def test_web_today_accepts_verified_network_scope(monkeypatch):
    scope = {"kind": "network", "id": "network-1", "name": "Сеть", "business_ids": ["b-1", "b-2"]}
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(operator_api, "DatabaseManager", _Database)
    monkeypatch.setattr(operator_api, "resolve_control_scope", lambda *_args, **_kwargs: scope)
    monkeypatch.setattr(operator_api, "build_mobile_today", lambda _cursor, **kwargs: {"scope": kwargs["scope"], "network_summary": {"locations_count": 2}})

    response = _app().test_client().get(
        "/api/operator/today?scope_type=network&scope_id=network-1"
    )

    assert response.status_code == 200
    assert response.get_json()["scope"]["business_ids"] == ["b-1", "b-2"]


def test_web_today_keeps_demo_inside_its_business(monkeypatch):
    scope = {"kind": "business", "id": "demo-business", "name": "Демо", "business_ids": ["demo-business"]}
    captured = {}
    monkeypatch.setattr(
        operator_api,
        "require_auth_from_request",
        lambda: {"user_id": "demo-user", "session_kind": "demo", "scope_business_id": "demo-business"},
    )
    monkeypatch.setattr(operator_api, "DatabaseManager", _Database)
    monkeypatch.setattr(operator_api, "resolve_control_scope", lambda *_args, **kwargs: captured.update(kwargs) or scope)
    monkeypatch.setattr(operator_api, "build_mobile_today", lambda _cursor, **kwargs: {"scope": kwargs["scope"]})

    response = _app().test_client().get("/api/operator/today?scope_type=business&scope_id=demo-business")

    assert response.status_code == 200
    assert captured["requested_kind"] == "business"
    assert captured["requested_id"] == "demo-business"


def test_web_today_rejects_demo_network_escape(monkeypatch):
    monkeypatch.setattr(
        operator_api,
        "require_auth_from_request",
        lambda: {"user_id": "demo-user", "session_kind": "demo", "scope_business_id": "demo-business"},
    )
    monkeypatch.setattr(operator_api, "DatabaseManager", _Database)

    response = _app().test_client().get("/api/operator/today?scope_type=network&scope_id=network-1")

    assert response.status_code == 403


def test_web_progress_uses_same_verified_network_scope(monkeypatch):
    scope = {"kind": "network", "id": "network-1", "name": "Сеть", "business_ids": ["b-1", "b-2"]}
    monkeypatch.setattr(operator_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(operator_api, "DatabaseManager", _Database)
    monkeypatch.setattr(operator_api, "resolve_control_scope", lambda *_args, **_kwargs: scope)
    monkeypatch.setattr(operator_api, "build_mobile_progress", lambda _cursor, **kwargs: {"scope": kwargs["scope"], "network_summary": {"locations_count": 2}})

    response = _app().test_client().get(
        "/api/operator/progress?scope_type=network&scope_id=network-1"
    )

    assert response.status_code == 200
    assert response.get_json()["network_summary"]["locations_count"] == 2
