from flask import Flask

from api import product_events_api


class _Connection:
    def cursor(self):
        return object()

    def commit(self):
        return None

    def rollback(self):
        return None


class _Database:
    def __init__(self):
        self.conn = _Connection()

    def close(self):
        return None


def _app():
    app = Flask(__name__)
    app.register_blueprint(product_events_api.product_events_bp)
    return app


def test_product_event_requires_access_and_records_allowlisted_event(monkeypatch):
    captured = {}
    monkeypatch.setattr(product_events_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(product_events_api, "verify_business_access", lambda *_args: (True, "user-1"))
    monkeypatch.setattr(product_events_api, "DatabaseManager", _Database)
    monkeypatch.setattr(product_events_api, "record_product_event", lambda _cursor, **kwargs: captured.update(kwargs) or "event-1")

    response = _app().test_client().post(
        "/api/product/events",
        json={"event_name": "onboarding_completed", "business_id": "business-1", "surface": "telegram_mini_app"},
    )

    assert response.status_code == 201
    assert response.get_json() == {"success": True, "event_id": "event-1"}
    assert captured["business_id"] == "business-1"


def test_product_event_rejects_unknown_event_before_writing(monkeypatch):
    monkeypatch.setattr(product_events_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    response = _app().test_client().post(
        "/api/product/events",
        json={"event_name": "unplanned", "business_id": "business-1", "surface": "web"},
    )
    assert response.status_code == 400
    assert response.get_json()["error"] == "Событие не поддерживается"
