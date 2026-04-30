from datetime import date, datetime

import src.services.content_plan_service as content_plan_service
from src.core.content_plan_generator import build_content_plan_skeleton
from src.services.content_plan_service import (
    _build_planning_readiness,
    _fetch_seo_keywords,
    _fetch_seo_keywords_isolated,
    _json_ready,
    _scope_target_business_id,
)


def test_content_plan_skeleton_respects_allowed_period_and_sources():
    context = {
        "business": {"name": "LocalOS Cafe", "city": "Санкт-Петербург"},
        "services": [{"id": "svc-1", "name": "Кофе навынос"}],
        "seo_keywords": [{"keyword": "кофе рядом", "views": 1200}],
        "sales_signals": [{"title": "Капучино", "transaction_id": "tx-1"}],
        "audit_signals": [{"title": "Мало свежих новостей", "problem": "нет активности"}],
    }

    plan = build_content_plan_skeleton(
        context,
        period_days=60,
        density="standard",
        content_mix={
            "services": True,
            "seo": True,
            "sales": True,
            "audit": True,
            "seasonal": False,
        },
    )

    assert plan["period_days"] == 60
    assert plan["title"] == "Контент-план на 60 дней"
    assert len(plan["items"]) >= 4
    assert any(item["content_type"] == "service" for item in plan["items"])
    assert any(item["content_type"] == "seo" for item in plan["items"])
    assert any(item["content_type"] == "sales" for item in plan["items"])
    assert any(item["content_type"] == "audit" for item in plan["items"])


def test_content_plan_skeleton_falls_back_to_30_for_invalid_period():
    plan = build_content_plan_skeleton(
        {"business": {"name": "Fallback Biz"}},
        period_days=45,
        density="light",
        content_mix={},
    )

    assert plan["period_days"] == 30
    assert len(plan["items"]) >= 4
    assert all(item["theme"] for item in plan["items"])


def test_scope_target_business_id_uses_parent_for_network_parent():
    assert _scope_target_business_id(None, "child-1", "network_parent", "parent-1") == "parent-1"
    assert _scope_target_business_id(None, "child-1", "network_location", "location-1") == "location-1"
    assert _scope_target_business_id(None, "child-1", "single_business", "parent-1") == "child-1"


def test_fetch_seo_keywords_isolated_returns_empty_list_when_optional_loader_fails(monkeypatch):
    class FakeCursor:
        pass

    class FakeConn:
        def __init__(self):
            self.rolled_back = False

        def cursor(self):
            return FakeCursor()

        def rollback(self):
            self.rolled_back = True

        def commit(self):
            return None

        def close(self):
            return None

    created_connections: list[FakeConn] = []

    class FakeDatabaseManager:
        def __init__(self):
            self.conn = FakeConn()
            created_connections.append(self.conn)

        def close(self):
            self.conn.close()

    def fake_fetch_seo_keywords(cursor, user_id, business_id):
        raise RuntimeError("wordstat exploded")

    monkeypatch.setattr(content_plan_service, "DatabaseManager", FakeDatabaseManager)
    monkeypatch.setattr(content_plan_service, "_fetch_seo_keywords", fake_fetch_seo_keywords)

    assert _fetch_seo_keywords_isolated("user-1", "business-1") == []
    assert created_connections and created_connections[0].rolled_back is True


def test_fetch_seo_keywords_disables_global_fallback_for_empty_business_context(monkeypatch):
    observed: dict[str, object] = {}

    def fake_collect_ranked_keywords(cursor, business_id, user_id, **kwargs):
        observed["business_id"] = business_id
        observed["user_id"] = user_id
        observed["fallback_global_when_empty_terms"] = kwargs.get("fallback_global_when_empty_terms")
        return {
            "items": [
                {"keyword": "маникюр", "views": 100, "category": "nails"},
            ]
        }

    monkeypatch.setattr(content_plan_service, "collect_ranked_keywords", fake_collect_ranked_keywords)

    result = _fetch_seo_keywords(cursor=None, user_id="user-42", business_id="business-42")

    assert observed["business_id"] == "business-42"
    assert observed["user_id"] == "user-42"
    assert observed["fallback_global_when_empty_terms"] is False
    assert result == [{"keyword": "маникюр", "views": 100, "category": "nails"}]


def test_json_ready_serializes_nested_dates_and_datetimes():
    payload = {
        "created_at": datetime(2026, 4, 30, 15, 20, 0),
        "scheduled_for": date(2026, 5, 1),
        "items": [
            {"when": datetime(2026, 5, 2, 9, 0, 0)},
            date(2026, 5, 3),
        ],
    }

    normalized = _json_ready(payload)

    assert normalized == {
        "created_at": "2026-04-30T15:20:00",
        "scheduled_for": "2026-05-01",
        "items": [
            {"when": "2026-05-02T09:00:00"},
            "2026-05-03",
        ],
    }


def test_build_planning_readiness_marks_missing_grounding_inputs():
    readiness = _build_planning_readiness(
        map_links_count=0,
        services_count=0,
        seo_keywords_count=0,
        sales_signals_count=0,
        audit_signals_count=3,
    )

    assert readiness["has_map_links"] is False
    assert readiness["has_services"] is False
    assert readiness["has_seo_keywords"] is False
    assert readiness["has_audit_signals"] is True
    assert readiness["is_grounded_for_search"] is False
    assert readiness["missing_inputs"] == ["map_links", "services", "seo_keywords"]
