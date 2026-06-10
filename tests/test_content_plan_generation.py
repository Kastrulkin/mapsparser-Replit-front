from datetime import date, datetime

import src.services.content_plan_service as content_plan_service
from src.core.content_plan_generator import build_content_plan_skeleton
from src.core.content_plan_templates import detect_content_plan_template_key
from src.services.content_plan_service import (
    _build_learning_breakdown_summary,
    _build_learning_feedback_from_breakdowns,
    _build_learning_metrics_summary,
    _build_learning_quality_insights,
    _build_network_quality_summary,
    _build_planning_readiness,
    _classify_text_edit,
    _content_plan_business_facts,
    _content_plan_draft_needs_fallback,
    _fetch_audit_signals,
    _fetch_seo_keywords,
    _fetch_seo_keywords_isolated,
    _filter_foreign_brand_seo_keywords,
    _fallback_draft_text,
    _merge_seo_keyword_lists,
    _network_location_targets_from_context,
    _json_ready,
    _relevant_service_names_for_item,
    _resolve_scope_target_meta,
    _sanitize_generated_news_text,
    _scope_context_business_ids,
    _select_context_seo_keywords,
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


def test_content_plan_templates_detect_requested_business_types():
    assert detect_content_plan_template_key(
        {
            "name": "Весёлая расчёска",
            "categories": '["Детский салон-парикмахерская", "парикмахерская"]',
        }
    ) == "kids_hair_salon"
    assert detect_content_plan_template_key(
        {"name": "Каток", "categories": '["Культурный центр", "художественная галерея"]'}
    ) == "culture_event_center"
    assert detect_content_plan_template_key({"name": "Riderra (Tallinn)", "categories": ""}) == "airport_transfer"
    assert detect_content_plan_template_key({"name": "Кафе Кебаб", "categories": '["быстрое питание"]'}) == "fast_food_kebab"
    assert detect_content_plan_template_key({"name": "Киришиавтосервис (Сургутнефтегаз)"}) == "gas_station"
    assert detect_content_plan_template_key({"name": "Лукойл", "categories": ""}) == "gas_station"


def test_content_plan_skeleton_uses_kids_hair_salon_template():
    plan = build_content_plan_skeleton(
        {
            "business": {
                "name": "Весёлая расчёска",
                "city": "Санкт-Петербург",
                "business_type": "Салон красоты",
                "categories": '["Детский салон-парикмахерская"]',
            },
            "services": [],
            "seo_keywords": [],
            "sales_signals": [],
            "audit_signals": [],
        },
        period_days=30,
        density="light",
        content_mix={"templates": True, "seasonal": False},
    )

    assert plan["meta"]["template_key"] == "kids_hair_salon"
    assert any(item["source_kind"] == "industry_template" for item in plan["items"])
    assert any("детская стрижка" in item["goal"].lower() for item in plan["items"])


def test_content_plan_skeleton_uses_event_center_template_for_katok():
    plan = build_content_plan_skeleton(
        {
            "business": {
                "name": "Каток",
                "city": "Краснодар",
                "categories": '["Культурный центр", "художественная галерея"]',
            },
            "services": [],
            "seo_keywords": [],
            "sales_signals": [],
            "audit_signals": [],
        },
        period_days=30,
        density="light",
        content_mix={"templates": True, "seasonal": False},
    )

    assert plan["meta"]["template_key"] == "culture_event_center"
    assert any("афиша" in item["goal"].lower() or "событ" in item["goal"].lower() for item in plan["items"])


def test_content_plan_katok_site_description_prevents_school_fallback(monkeypatch):
    monkeypatch.setattr(
        content_plan_service,
        "_fetch_site_description",
        lambda _: "Культурный центр в Краснодаре. Концерты, лекции, стендап, мастер-классы — события, которые нельзя пропустить.",
    )
    item = {
        "theme": "Ближайшее событие в афише",
        "goal": "Дать понятный анонс события: что будет, кому подойдет, дата, время и как попасть.",
        "seo_keyword": "афиша",
    }
    business_row = {
        "name": "Каток",
        "city": "Краснодар",
        "business_type": "",
        "industry": "",
        "categories": "",
        "address": "ул. Жлобы, 139",
        "description": "",
        "site": "https://katok.io/",
    }
    facts = _content_plan_business_facts(business_row, item)
    facts["services"] = "- 16 июня, 19:00 — Век вранья\n- 21 июня, 19:00 — Музыкальное казино"

    draft = _fallback_draft_text("Каток", item, facts, "ru")

    assert facts["is_cultural_space"] is True
    assert "культурный центр" in draft.lower()
    assert "школ" not in draft.lower()
    assert _content_plan_draft_needs_fallback("Каток — школа и пространство для детей и подростков.", facts) is True


def test_content_plan_skeleton_uses_transfer_fast_food_and_gas_station_templates():
    cases = [
        (
            {"name": "Riderra (Tallinn)", "categories": ""},
            "airport_transfer",
            "airport",
        ),
        (
            {"name": "Кафе Кебаб", "business_type": "Кафе", "categories": '["быстрое питание"]'},
            "fast_food_kebab",
            "кебаб",
        ),
        (
            {"name": "Киришиавтосервис (Сургутнефтегаз)", "business_type": "network"},
            "gas_station",
            "азс",
        ),
    ]

    for business, template_key, expected_word in cases:
        plan = build_content_plan_skeleton(
            {
                "business": business,
                "services": [],
                "seo_keywords": [],
                "sales_signals": [],
                "audit_signals": [],
            },
            period_days=30,
            density="light",
            content_mix={"templates": True, "seasonal": False},
        )

        assert plan["meta"]["template_key"] == template_key
        assert any(expected_word in item["goal"].lower() or expected_word in item["theme"].lower() for item in plan["items"])


def test_content_plan_skeleton_includes_riderra_route_service_posts():
    plan = build_content_plan_skeleton(
        {
            "business": {"name": "Riderra (Tallinn)", "categories": ""},
            "services": [],
            "seo_keywords": [],
            "sales_signals": [],
            "audit_signals": [],
        },
        period_days=30,
        density="active",
        content_mix={"templates": True, "seasonal": False},
    )

    themes = " ".join(item["theme"] for item in plan["items"])
    goals = " ".join(item["goal"] for item in plan["items"])
    assert "Vilnius" in themes
    assert "Phuket" in themes
    assert "Zanzibar" in themes
    assert "поездке" in goals
    assert "маршрут" in goals
    assert "riderra.com" in goals


def test_scope_target_business_id_uses_parent_for_network_parent():
    assert _scope_target_business_id(None, "child-1", "network_parent", "parent-1") == "parent-1"
    assert _scope_target_business_id(None, "child-1", "network_location", "location-1") == "location-1"
    assert _scope_target_business_id(None, "child-1", "single_business", "parent-1") == "child-1"


def test_scope_context_business_ids_expands_network_parent():
    class FakeCursor:
        def __init__(self):
            self.params = None

        def execute(self, query, params=None):
            self.params = params

        def fetchall(self):
            return [
                ("parent-1",),
                ("loc-1",),
                ("loc-2",),
            ]

    cursor = FakeCursor()

    result = _scope_context_business_ids(
        cursor,
        {"id": "child-1", "network_id": "parent-1"},
        "network_parent",
        "parent-1",
    )

    assert cursor.params == ("parent-1", "parent-1")
    assert result == ["parent-1", "loc-1", "loc-2"]


def test_merge_seo_keyword_lists_deduplicates_primary_and_fallback():
    result = _merge_seo_keyword_lists(
        [{"keyword": "АЗС рядом", "views": 100, "category": "fuel"}],
        [
            {"keyword": "азс рядом", "views": 80, "category": "fuel"},
            {"keyword": "заправка дизель", "views": 70, "category": "fuel"},
        ],
    )

    assert result == [
        {"keyword": "АЗС рядом", "views": 100, "category": "fuel"},
        {"keyword": "заправка дизель", "views": 70, "category": "fuel"},
    ]


def test_select_context_seo_keywords_prefers_sufficient_custom_set():
    result = _select_context_seo_keywords(
        [{"keyword": "салон красоты рядом", "views": 10000, "category": "other"}],
        [
            {"keyword": "лукойл", "views": 12000, "category": "fuel"},
            {"keyword": "лукойл азс", "views": 11000, "category": "fuel"},
            {"keyword": "азс рядом", "views": 9800, "category": "fuel"},
            {"keyword": "заправка рядом", "views": 9400, "category": "fuel"},
            {"keyword": "бензин 95", "views": 7200, "category": "fuel"},
        ],
    )

    assert [item["keyword"] for item in result] == [
        "лукойл",
        "лукойл азс",
        "азс рядом",
        "заправка рядом",
        "бензин 95",
    ]


def test_filter_foreign_brand_seo_keywords_removes_competitor_brands():
    result = _filter_foreign_brand_seo_keywords(
        [
            {"keyword": "точка красоты", "views": 100726, "category": "other"},
            {"keyword": "детская стрижка", "views": 1200, "category": "beauty"},
        ],
        "Весёлая расчёска",
    )

    assert [item["keyword"] for item in result] == ["детская стрижка"]


def test_filter_foreign_brand_seo_keywords_keeps_own_brand():
    result = _filter_foreign_brand_seo_keywords(
        [{"keyword": "точка красоты", "views": 100726, "category": "other"}],
        "Точка красоты",
    )

    assert [item["keyword"] for item in result] == ["точка красоты"]


def test_sanitize_generated_news_text_extracts_json_and_removes_markup():
    raw = '{"news":"🎉 **Что выбрать сейчас:**\\n\\nОсень – время перемен! #салон"}'

    result = _sanitize_generated_news_text(raw)

    assert result == "Что выбрать сейчас: Осень – время перемен!"
    assert "{" not in result
    assert "}" not in result
    assert "**" not in result
    assert "#" not in result


def test_sanitize_generated_news_text_extracts_fenced_payload():
    raw = '```json\n{"news":"Новая тема без технических символов"}\n```'

    assert _sanitize_generated_news_text(raw) == "Новая тема без технических символов"


def test_relevant_service_names_for_item_prefers_topic_matches():
    services = "\n".join(
        [
            "- Гимназия 1–4 класс (английский и естественные науки)",
            "- Курс программирования в Minecraft для детей",
            "- Английский для дошкольников",
            "- Курс визуального дизайна и брендинга",
        ]
    )

    result = _relevant_service_names_for_item(
        services,
        {
            "theme": "Гимназия 1–4 класс: английский и естественные науки в понятной системе",
            "goal": "Раскрыть направление для младших школьников",
        },
    )

    assert result[0] == "Гимназия 1–4 класс"
    assert "Курс программирования в Minecraft для детей" not in result[:2]


def test_school_fallback_draft_stays_on_plan_item_topic():
    text = _fallback_draft_text(
        "Intellectum Space and School",
        {
            "theme": "Гимназия 1–4 класс: английский и естественные науки в понятной системе",
            "goal": "Раскрыть направление для младших школьников и усилить доверие к программе",
        },
        {
            "city": "Батуми",
            "business_type": "school",
            "services": "\n".join(
                [
                    "- Гимназия 1–4 класс (английский и естественные науки)",
                    "- Курс программирования в Minecraft для детей",
                    "- Подготовка детей к школе",
                    "- Английский для дошкольников",
                    "- Курс визуального дизайна и брендинга",
                ]
            ),
        },
    )

    assert "Гимназия 1–4 класс" in text
    assert "младших школьников" in text
    assert "Курс программирования в Minecraft" not in text
    assert "Курс визуального дизайна" not in text


def test_school_fallback_general_intro_does_not_pick_random_single_course():
    text = _fallback_draft_text(
        "Intellectum Space and School",
        {
            "theme": "Что такое Intellectum Space and School и чем школа полезна детям в Батуми",
            "goal": "Общий пост о школе, подходе к обучению и направлениях для детей и подростков",
        },
        {
            "city": "Батуми",
            "business_type": "school",
            "services": "\n".join(
                [
                    "- Английский для дошкольников",
                    "- Гимназия 1–4 класс (английский и естественные науки)",
                    "- Курс программирования в Minecraft для детей",
                    "- Робототехника для детей",
                ]
            ),
        },
    )

    assert "школа и пространство для детей и подростков" in text
    assert "В фокусе публикации" not in text
    assert "Общий пост" not in text
    assert "Английский для дошкольников. Общий пост" not in text


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
            "skipped_total": 0,
            "rescheduled_total": 0,
            "major_rewrite_total": 0,
            "draft_generated_total": 0,
            "edited_before_accept_pct": 50.0,
        },
        {
            "key": "audit",
            "accepted_total": 2,
            "accepted_edited_total": 0,
            "skipped_total": 0,
            "rescheduled_total": 0,
            "major_rewrite_total": 0,
            "draft_generated_total": 0,
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
            "skipped_total": 0,
            "rescheduled_total": 0,
            "major_rewrite_total": 0,
            "draft_generated_total": 0,
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


def test_learning_feedback_penalizes_skipped_source_even_without_accepts():
    feedback = _build_learning_feedback_from_breakdowns(
        [
            {
                "key": "audit_signal",
                "accepted_total": 0,
                "accepted_edited_total": 0,
                "skipped_total": 2,
                "major_rewrite_total": 1,
                "draft_generated_total": 3,
                "edited_before_accept_pct": 0.0,
            }
        ],
        [],
    )

    assert feedback["source_kind"]["audit_signal"]["score_adjustment"] < 0
    assert feedback["source_kind"]["audit_signal"]["skipped_total"] == 2


def test_learning_feedback_includes_network_location_quality():
    feedback = _build_learning_feedback_from_breakdowns(
        [],
        [],
        [
            {
                "key": "loc-risk",
                "label": "Риск-точка",
                "risk_score": 88,
                "reasons": ["major_rewrites"],
                "accepted_total": 2,
                "skipped_total": 1,
                "major_rewrite_total": 2,
                "draft_generated_total": 5,
            }
        ],
    )

    assert feedback["location"]["loc-risk"]["score_adjustment"] < 0
    assert feedback["location"]["loc-risk"]["reasons"] == ["major_rewrites"]


def test_content_plan_generator_uses_location_quality_hint():
    context = {
        "business": {"id": "loc-risk", "name": "LocalOS Clinic", "city": "Кудрово"},
        "scope": {"scope_target_id": "loc-risk"},
        "services": [],
        "seo_keywords": [{"keyword": "стоматология рядом", "views": 6000}],
        "sales_signals": [],
        "audit_signals": [],
        "learning_feedback": {
            "source_kind": {},
            "content_type": {},
            "location": {
                "loc-risk": {
                    "risk_score": 82,
                    "reasons": ["major_rewrites"],
                    "score_adjustment": -12,
                },
            },
        },
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

    item = plan["items"][0]
    assert item["learning_adjustment"] < 0
    assert "Для этой точки" in item["goal"]
    assert any(reason["label"] == "location_quality_feedback" for reason in item["ranking_reasons"])


def test_learning_quality_insights_explain_weak_network_location():
    insights = _build_learning_quality_insights(
        [],
        [],
        [
            {
                "key": "loc-risk",
                "label": "Риск-точка",
                "risk_score": 70,
                "reasons": ["drafts_not_published"],
            }
        ],
    )

    assert insights[0]["kind"] == "network_location_gap"
    assert "Риск-точка" in insights[0]["text_ru"]
    assert "не доходят до публикации" in insights[0]["text_ru"]


def test_content_plan_generator_prioritizes_undercovered_seo_topics():
    context = {
        "business": {"name": "LocalOS Clinic", "city": "Кудрово"},
        "services": [],
        "seo_keywords": [
            {"keyword": "педиатр рядом", "views": 1200},
            {"keyword": "стоматология рядом", "views": 1200},
        ],
        "recent_news": [
            {"text": "Сегодня рассказываем, как выбрать стоматология рядом с домом."},
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

    assert plan["items"][0]["source_ref"] == "педиатр рядом"
    assert plan["items"][0]["ranking_reasons"]
    assert plan["meta"]["quality_ranking_applied"] is True


def test_content_plan_generator_skips_foreign_brand_keywords_and_keeps_views():
    context = {
        "business": {"name": "Весёлая расчёска", "city": "Санкт-Петербург"},
        "services": [],
        "seo_keywords": [
            {"keyword": "точка красоты", "views": 100726},
            {"keyword": "детская стрижка", "views": 1200},
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

    assert plan["items"][0]["seo_keyword"] == "детская стрижка"
    assert plan["items"][0]["seo_views"] == 1200


def test_content_plan_generator_prioritizes_weak_audit_search_zone():
    context = {
        "business": {"name": "LocalOS Beauty", "city": "Кудрово"},
        "services": [],
        "seo_keywords": [],
        "sales_signals": [],
        "audit_signals": [
            {
                "id": "description",
                "title": "Общее описание услуг",
                "problem": "Не хватает конкретики",
                "priority": "medium",
                "section": "content",
            },
            {
                "id": "search_intent:маникюр рядом",
                "title": "Недопокрытый поисковый сценарий: маникюр рядом",
                "problem": "Нет отдельного ответа под спрос",
                "priority": "medium",
                "section": "search",
            },
        ],
    }

    plan = build_content_plan_skeleton(
        context,
        period_days=30,
        density="light",
        content_mix={
            "services": False,
            "seo": False,
            "sales": False,
            "audit": True,
            "seasonal": False,
        },
    )

    assert "маникюр рядом" in plan["items"][0]["source_ref"]
    assert "Недопокрытый поисковый сценарий" not in plan["items"][0]["theme"]
    assert "Закрыть слабую зону" not in plan["items"][0]["theme"]
    assert "Закрыть слабое место" not in plan["items"][0]["goal"]
    assert plan["items"][0]["theme"] == "Почему выбрать вас по запросу «маникюр рядом»"
    assert any(reason["label"] == "weak_zone_priority" for reason in plan["items"][0]["ranking_reasons"])


def test_classify_text_edit_distinguishes_minor_and_major_changes():
    original = "Запишитесь на латте и свежие десерты в карточке."
    minor = "Запишитесь на латте и свежие десерты в нашей карточке."
    major = "Сегодня рассказываем о новых завтраках, сезонном меню и вечерних предложениях."

    assert _classify_text_edit(original, minor) == "minor_edit"
    assert _classify_text_edit(original, major) == "major_rewrite"
    assert _classify_text_edit(original, original) == "unchanged"


def test_build_network_quality_summary_surfaces_risky_locations():
    summary = _build_network_quality_summary(
        [
            {
                "location_scope": "loc-risk",
                "location_label": "Риск-точка",
                "accepted_total": 2,
                "accepted_edited_total": 2,
                "skipped_total": 1,
                "rescheduled_total": 0,
                "major_rewrite_total": 1,
                "draft_generated_total": 5,
            },
            {
                "location_scope": "loc-stable",
                "location_label": "Стабильная точка",
                "accepted_total": 5,
                "accepted_edited_total": 0,
                "skipped_total": 0,
                "rescheduled_total": 0,
                "major_rewrite_total": 0,
                "draft_generated_total": 5,
            },
        ]
    )

    assert summary[0]["key"] == "loc-risk"
    assert summary[0]["risk_score"] > summary[1]["risk_score"]
    assert "major_rewrites" in summary[0]["reasons"]
