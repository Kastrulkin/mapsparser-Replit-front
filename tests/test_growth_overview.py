from datetime import datetime, timezone

from flask import Flask

from api import growth_overview_api
from services.growth_overview_service import build_growth_overview


NOW = datetime.now(timezone.utc).isoformat()


def _snapshot():
    return {
        "scope": {"business_id": "business-1", "locations_count": 1, "is_network": False},
        "maps": {
            "available": True,
            "linked_locations": 1,
            "parsed_locations": 1,
            "services_count": 8,
            "reviews_count": 12,
            "unanswered_reviews": 0,
            "link_created_at": NOW,
            "latest_at": NOW,
        },
        "content": {"available": True, "plans": 1, "drafts": 3, "published": 1, "plan_at": NOW, "draft_at": NOW, "published_at": NOW},
        "partnerships": {"available": True, "leads": 4, "proposals": 2, "contacted": 1, "results": 1, "lead_at": NOW, "proposal_at": NOW, "contact_at": NOW, "result_at": NOW},
        "automation": {"available": True, "agents": 2, "tests": 2, "active": 1, "completed": 3, "failed": 0, "test_at": NOW, "active_at": NOW, "completed_at": NOW},
        "upsells": {"available": True, "matrices": 1, "active": 1, "bought": 1, "revenue": 2500, "matrix_at": NOW, "active_at": NOW, "bought_at": NOW},
    }


def _area(payload, key):
    return next(item for item in payload["areas"] if item["key"] == key)


def test_growth_overview_reports_five_real_directions():
    payload = build_growth_overview(_snapshot())

    assert [item["key"] for item in payload["areas"]] == ["maps", "content", "partnerships", "automation", "upsells"]
    assert payload["summary"]["completed_milestones"] == payload["summary"]["total_milestones"]
    assert payload["summary"]["active_areas"] == 5
    assert payload["summary"]["needs_attention"] == 0


def test_missing_map_is_the_dominant_next_action():
    snapshot = _snapshot()
    snapshot["maps"].update({"linked_locations": 0, "parsed_locations": 0, "services_count": 0, "reviews_count": 0})
    snapshot["content"].update({"plans": 0, "drafts": 0, "published": 0})

    payload = build_growth_overview(snapshot)

    assert payload["focus_action"]["cta_url"] == "/dashboard/profile"
    assert _area(payload, "maps")["status"] == "not_started"
    assert _area(payload, "content")["status"] == "not_started"


def test_previous_map_achievement_survives_current_reputation_problem():
    snapshot = _snapshot()
    snapshot["maps"]["unanswered_reviews"] = 5

    payload = build_growth_overview(snapshot)
    maps = _area(payload, "maps")

    assert maps["status"] == "needs_attention"
    assert maps["problem"] == "Без ответа осталось отзывов: 5."
    assert next(item for item in maps["milestones"] if item["key"] == "map_audited")["status"] == "done"


def test_unavailable_source_is_not_interpreted_as_zero_progress():
    snapshot = _snapshot()
    snapshot["partnerships"] = {"available": False}

    payload = build_growth_overview(snapshot)
    partnerships = _area(payload, "partnerships")

    assert partnerships["status"] == "unavailable"
    assert partnerships["progress"] == {"completed": 0, "total": 0}
    assert payload["summary"]["active_areas"] == 4


def test_money_is_shown_only_for_confirmed_upsell_events():
    payload = build_growth_overview(_snapshot())
    effect = _area(payload, "upsells")["action"]["estimated_effect"]
    assert effect["kind"] == "actual"
    assert effect["amount"] == 2500
    assert effect["source"] == "Отмеченные покупки в разделе допродаж"

    snapshot = _snapshot()
    snapshot["upsells"].update({"bought": 0, "revenue": 0})
    empty_effect = _area(build_growth_overview(snapshot), "upsells")["action"]["estimated_effect"]
    assert empty_effect is None


def test_network_map_coverage_is_explicit():
    snapshot = _snapshot()
    snapshot["scope"].update({"locations_count": 6, "is_network": True})
    snapshot["maps"].update({"linked_locations": 4, "parsed_locations": 4})

    maps = _area(build_growth_overview(snapshot), "maps")

    assert maps["metrics"][0] == {"label": "Карты", "value": "4 из 6"}
    assert maps["milestones"][0]["evidence"] == "4 из 6"


def test_network_problem_names_the_location_that_needs_attention():
    snapshot = _snapshot()
    snapshot["scope"].update({"locations_count": 3, "is_network": True})
    snapshot["maps"].update({"unanswered_reviews": 4, "attention_location": "Органика на Невском"})

    maps = _area(build_growth_overview(snapshot), "maps")

    assert maps["status"] == "needs_attention"
    assert maps["problem"] == "Точка «Органика на Невском»: без ответа осталось отзывов: 4."


class _FakeConnection:
    def cursor(self):
        return object()


class _FakeDatabase:
    def __init__(self):
        self.conn = _FakeConnection()

    def close(self):
        return None


def _app():
    app = Flask(__name__)
    app.register_blueprint(growth_overview_api.growth_overview_bp)
    return app


def test_growth_overview_endpoint_rejects_cross_business_access(monkeypatch):
    monkeypatch.setattr(growth_overview_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(growth_overview_api, "verify_business_access", lambda cursor, business_id, user_data: (False, "user-2"))
    monkeypatch.setattr(growth_overview_api, "DatabaseManager", _FakeDatabase)

    response = _app().test_client().get("/api/business/business-2/growth-overview")

    assert response.status_code == 403
    assert response.get_json() == {"success": False, "error": "Нет доступа к бизнесу"}


def test_growth_overview_endpoint_returns_normalized_contract(monkeypatch):
    expected = build_growth_overview(_snapshot())
    monkeypatch.setattr(growth_overview_api, "require_auth_from_request", lambda: {"user_id": "user-1"})
    monkeypatch.setattr(growth_overview_api, "verify_business_access", lambda cursor, business_id, user_data: (True, "user-1"))
    monkeypatch.setattr(growth_overview_api, "DatabaseManager", _FakeDatabase)
    monkeypatch.setattr(growth_overview_api, "load_growth_overview", lambda business_id: expected)

    response = _app().test_client().get("/api/business/business-1/growth-overview")
    payload = response.get_json()

    assert response.status_code == 200
    assert payload["success"] is True
    assert len(payload["areas"]) == 5
    assert payload["focus_action"]["cta_url"]
