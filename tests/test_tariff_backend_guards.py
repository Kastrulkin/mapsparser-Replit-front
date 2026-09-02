from flask import Flask

from api import content_plans_api, services_api


class _Cursor:
    def execute(self, _query, _params=None):
        return None

    def fetchone(self):
        return None


class _Connection:
    def cursor(self):
        return _Cursor()


class _Database:
    def __init__(self):
        self.conn = _Connection()

    def close(self):
        return None


def _payment_required(capability):
    return {
        "allowed": False,
        "capability": capability,
        "status": "payment_required",
        "code": "payment_required",
        "payment_required": True,
        "required_tier": "starter",
        "required_tier_name": "Карты",
        "reason": "Функция входит в тариф «Карты».",
    }


def test_direct_service_mutation_requires_maps_tier(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(services_api.services_bp)
    monkeypatch.setattr(services_api, "verify_session", lambda _token: {"user_id": "user-1"})
    monkeypatch.setattr(services_api, "DatabaseManager", _Database)
    monkeypatch.setattr(services_api, "verify_business_access", lambda *_args: (True, "user-1"))
    monkeypatch.setattr(services_api, "get_capability_access", lambda _business_id, capability, _admin=False: _payment_required(capability))

    response = app.test_client().post(
        "/api/services/add",
        headers={"Authorization": "Bearer token"},
        json={"business_id": "business-1", "name": "Service"},
    )

    assert response.status_code == 402
    assert response.get_json()["capability"] == "maps.services"
    assert response.get_json()["return_to"] == "/api/services/add"


def test_direct_content_plan_generation_requires_maps_news_tier(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(content_plans_api.content_plans_bp)
    monkeypatch.setattr(content_plans_api, "verify_session", lambda _token: {"user_id": "user-1"})
    monkeypatch.setattr(content_plans_api, "DatabaseManager", _Database)
    monkeypatch.setattr(content_plans_api, "verify_business_access", lambda *_args: (True, "user-1"))
    monkeypatch.setattr(content_plans_api, "get_capability_access", lambda _business_id, capability, _admin=False: _payment_required(capability))

    response = app.test_client().post(
        "/api/content-plans/generate",
        headers={"Authorization": "Bearer token"},
        json={"business_id": "business-1"},
    )

    assert response.status_code == 402
    assert response.get_json()["capability"] == "maps.news"
    assert response.get_json()["return_to"] == "/api/content-plans/generate"
