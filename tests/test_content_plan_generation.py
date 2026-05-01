from datetime import date, datetime

import src.services.content_plan_service as content_plan_service
from src.core.content_plan_generator import build_content_plan_skeleton
from src.services.content_plan_service import (
    _build_learning_breakdown_summary,
    _build_learning_feedback_from_breakdowns,
    _build_learning_metrics_summary,
    _build_planning_readiness,
    _classify_text_edit,
    _fetch_audit_signals,
    _fetch_seo_keywords,
    _fetch_seo_keywords_isolated,
    _network_location_targets_from_context,
    _json_ready,
    _resolve_scope_target_meta,
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


def test_content_plan_skeleton_uses_grounded_goals_for_each_signal_type():
    context = {
        "business": {"name": "LocalOS Cafe", "city": "Кудрово"},
        "services": [{"id": "svc-1", "name": "Латте"}],
        "seo_keywords": [{"keyword": "кофе рядом", "views": 1200}],
        "sales_signals": [{"title": "Капучино", "transaction_id": "tx-1"}],
        "audit_signals": [{"title": "Мало свежих новостей", "problem": "нет активности"}],
    }

    plan = build_content_plan_skeleton(
        context,
        period_days=30,
        density="light",
        content_mix={
            "services": True,
            "seo": True,
            "sales": True,
            "audit": True,
            "seasonal": True,
        },
    )

    items_by_type = {item["content_type"]: item for item in plan["items"]}

    assert "«Латте»" in items_by_type["service"]["goal"]
    assert "«кофе рядом»" in items_by_type["seo"]["goal"]
    assert "«Капучино»" in items_by_type["sales"]["goal"]
    assert "«Мало свежих новостей»" in items_by_type["audit"]["goal"]


def test_content_plan_skeleton_prioritizes_stronger_seo_signal():
    context = {
        "business": {"name": "LocalOS Cafe", "city": "Кудрово"},
        "services": [],
        "seo_keywords": [
            {"keyword": "кофе рядом", "views": 6000},
            {"keyword": "десерты рядом", "views": 120},
        ],
        "sales_signals": [],
        "audit_signals": [],
    }

    plan = build_content_plan_skeleton(
        context,
        period_days=30,
        density="light",
        content_mix={
            "services": False,
            "seo": True,
            "sales": False,
            "audit": False,
            "seasonal": False,
        },
    )

    assert plan["items"][0]["source_ref"] == "кофе рядом"
    assert plan["items"][0]["strength_score"] > plan["items"][1]["strength_score"]


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


def test_resolve_scope_target_meta_uses_business_name_and_location():
    business_rows = {
        "parent-1": {
            "id": "parent-1",
            "name": "Сеть Север",
            "city": "Санкт-Петербург",
            "address": "Невский проспект, 10",
        }
    }

    def fake_fetch_business_row(cursor, business_id):
        return business_rows.get(business_id, {})

    original = content_plan_service._fetch_business_row
    content_plan_service._fetch_business_row = fake_fetch_business_row
    try:
        meta = _resolve_scope_target_meta(None, "biz-1", "network_parent", "parent-1")
    finally:
        content_plan_service._fetch_business_row = original

    assert meta == {
        "scope_target_label": "Сеть Север",
        "scope_target_city": "Санкт-Петербург",
        "scope_target_address": "Невский проспект, 10",
    }


def test_network_location_targets_are_extracted_from_scope_options():
    context = {
        "scope": {
            "scope_options": [
                {"scope_type": "network_parent", "scope_target_id": "parent-1", "label": "Сеть Север"},
                {"scope_type": "network_location", "scope_target_id": "loc-1", "label": "Точка 1", "city": "СПб"},
                {"scope_type": "network_location", "scope_target_id": "loc-2", "label": "Точка 2", "address": "Лиговский, 5"},
            ]
        }
    }

    targets = _network_location_targets_from_context(context)

    assert targets == [
        {"business_id": "loc-1", "label": "Точка 1", "city": "СПб", "address": ""},
        {"business_id": "loc-2", "label": "Точка 2", "city": "", "address": "Лиговский, 5"},
    ]


def test_fetch_audit_signals_includes_search_intents_from_audit():
    original = content_plan_service.build_card_audit_snapshot
    content_plan_service.build_card_audit_snapshot = lambda business_id: {
        "issue_blocks": [
            {"id": "reviews_unanswered", "title": "Есть отзывы без ответа", "problem": "Без ответа: 4", "priority": "high", "section": "reviews"},
        ],
        "reasoning": {
            "search_intents_to_target": [
                "кофе рядом",
                "завтрак рядом",
            ]
        },
    }
    try:
        signals = _fetch_audit_signals("business-1")
    finally:
        content_plan_service.build_card_audit_snapshot = original

    assert any(item["section"] == "reviews" for item in signals)
    assert any(item["section"] == "search" and "кофе рядом" in item["title"] for item in signals)


def test_build_learning_metrics_summary_aggregates_content_plan_signals():
    metrics = _build_learning_metrics_summary(
        [
            {
                "capability": "content_plan.generate",
                "generated_total": 5,
                "accepted_total": 0,
                "accepted_edited_total": 0,
                "skipped_total": 0,
                "rescheduled_total": 0,
                "minor_edit_total": 0,
                "major_rewrite_total": 0,
            },
            {
                "capability": "content_plan.publish",
                "generated_total": 0,
                "accepted_total": 4,
                "accepted_edited_total": 1,
                "skipped_total": 0,
                "rescheduled_total": 0,
                "minor_edit_total": 0,
                "major_rewrite_total": 0,
            },
            {
                "capability": "content_plan.item",
                "generated_total": 0,
                "accepted_total": 0,
                "accepted_edited_total": 0,
                "skipped_total": 3,
                "rescheduled_total": 2,
                "minor_edit_total": 1,
                "major_rewrite_total": 1,
            },
        ]
    )

    assert metrics["summary"] == {
        "generated_total": 5,
        "accepted_total": 4,
        "accepted_edited_total": 1,
        "skipped_total": 3,
        "rescheduled_total": 2,
        "minor_edit_total": 1,
        "major_rewrite_total": 1,
        "edited_before_accept_pct": 25.0,
    }
    publish_metrics = next(item for item in metrics["items"] if item["capability"] == "content_plan.publish")
    assert publish_metrics["edited_before_accept_pct"] == 25.0


def test_build_learning_breakdown_summary_calculates_edit_share():
    breakdown = _build_learning_breakdown_summary(
        [
            {
                "source_kind": "seo",
                "accepted_total": 6,
                "accepted_edited_total": 3,
            },
            {
                "source_kind": "audit",
                "accepted_total": 2,
                "accepted_edited_total": 0,
            },
        ],
        "source_kind",
    )

    assert breakdown == [
        {
            "key": "seo",
            "accepted_total": 6,
            "accepted_edited_total": 3,
            "edited_before_accept_pct": 50.0,
        },
        {
            "key": "audit",
            "accepted_total": 2,
            "accepted_edited_total": 0,
            "edited_before_accept_pct": 0.0,
        },
    ]


def test_build_learning_breakdown_summary_keeps_optional_label():
    breakdown = _build_learning_breakdown_summary(
        [
            {
                "location_scope": "loc-1",
                "location_label": "Точка 1",
                "accepted_total": 4,
                "accepted_edited_total": 2,
            },
        ],
        "location_scope",
        "location_label",
    )

    assert breakdown == [
        {
            "key": "loc-1",
            "label": "Точка 1",
            "accepted_total": 4,
            "accepted_edited_total": 2,
            "edited_before_accept_pct": 50.0,
        }
    ]


def test_learning_feedback_adjusts_generator_ranking_softly():
    feedback = _build_learning_feedback_from_breakdowns(
        [
            {
                "key": "seo_keyword",
                "accepted_total": 4,
                "accepted_edited_total": 4,
                "edited_before_accept_pct": 100.0,
            },
            {
                "key": "service",
                "accepted_total": 4,
                "accepted_edited_total": 0,
                "edited_before_accept_pct": 0.0,
            },
        ],
        [
            {
                "key": "seo",
                "accepted_total": 4,
                "accepted_edited_total": 4,
                "edited_before_accept_pct": 100.0,
            },
            {
                "key": "service",
                "accepted_total": 4,
                "accepted_edited_total": 0,
                "edited_before_accept_pct": 0.0,
            },
        ],
    )
    context = {
        "business": {"name": "LocalOS Cafe", "city": "Кудрово"},
        "services": [{"id": "svc-1", "name": "Латте", "description": "Кофе с молоком"}],
        "seo_keywords": [{"keyword": "кофе рядом", "views": 6000}],
        "sales_signals": [],
        "audit_signals": [],
        "learning_feedback": feedback,
    }

    plan = build_content_plan_skeleton(
        context,
        period_days=30,
        density="light",
        content_mix={
            "services": True,
            "seo": True,
            "sales": False,
            "audit": False,
            "seasonal": False,
        },
    )

    seo_item = next(item for item in plan["items"] if item["content_type"] == "seo")
    service_item = next(item for item in plan["items"] if item["content_type"] == "service")
    assert seo_item["learning_adjustment"] < 0
    assert service_item["learning_adjustment"] > 0
    assert plan["meta"]["learning_feedback_applied"] is True


def test_classify_text_edit_distinguishes_minor_and_major_changes():
    original = "Запишитесь на латте и свежие десерты в карточке."
    minor = "Запишитесь на латте и свежие десерты в нашей карточке."
    major = "Сегодня рассказываем о новых завтраках, сезонном меню и вечерних предложениях."

    assert _classify_text_edit(original, minor) == "minor_edit"
    assert _classify_text_edit(original, major) == "major_rewrite"
    assert _classify_text_edit(original, original) == "unchanged"
