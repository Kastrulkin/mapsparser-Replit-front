from __future__ import annotations

import json

from services.operator_core import route_operator_message
from services.operator_product_knowledge import (
    FEATURES,
    build_product_catalog_response,
    build_product_feature_explanation,
    classify_product_explanation_intent,
    read_saved_competitors,
    resolve_product_feature,
)


class CompetitorCursor:
    def __init__(self, competitors):
        self.competitors = competitors
        self.last_query = ""
        self.last_params = ()

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query).split()).lower()
        self.last_params = tuple(params or ())

    def fetchone(self):
        return {
            "competitors": json.dumps(self.competitors, ensure_ascii=False),
            "created_at": "2026-08-25T12:00:00Z",
            "updated_at": "2026-08-26T08:00:00Z",
        }


def test_product_catalog_covers_root_product_areas():
    keys = {str(item.get("key") or "") for item in FEATURES}

    assert len(keys) >= 19
    assert {
        "maps",
        "competitors",
        "services",
        "seo_visibility",
        "reviews",
        "content",
        "finance",
        "web_analytics",
        "partnerships",
        "telegram_radar",
        "telegram_control",
        "customer_bot",
        "agents",
        "network",
        "integrations",
        "billing",
        "public_materials",
    }.issubset(keys)

    result = build_product_catalog_response()
    assert result["feature_count"] == len(FEATURES)
    assert result["sources"] == ["PRODUCT.md", "README.md"]
    assert result["external_writes_performed"] is False


def test_resolver_understands_business_language_and_neighbor_alias():
    assert resolve_product_feature("Посмотри, как дела у соседа")["key"] == "competitors"
    assert resolve_product_feature("Как увеличить средний чек?")["key"] == "average_ticket"
    assert resolve_product_feature("Что с источниками трафика на сайте?")["key"] == "web_analytics"
    assert resolve_product_feature("Покажи мои ИИ-сотрудники")["key"] == "agents"


def test_feature_explanation_is_canonical_and_honest_about_boundaries():
    result = build_product_feature_explanation("Как работает публикация ответов на отзывы?")

    assert result["status"] == "completed"
    assert result["feature"]["key"] == "reviews"
    assert result["result_ref"]["href"].startswith("/dashboard/card?tab=reviews")
    assert "публикация" in result["chat_response"].lower()
    assert "ручной" in result["chat_response"].lower()
    assert result["external_writes_performed"] is False


def test_product_explanation_intent_does_not_hijack_operational_request():
    assert classify_product_explanation_intent("Как работает Telegram-радар?") is True
    assert classify_product_explanation_intent("Объясни, что умеют агенты") is True
    assert classify_product_explanation_intent("Посмотри, как дела у соседа") is False


def test_saved_competitors_asks_which_neighbor_when_there_are_several():
    cursor = CompetitorCursor(
        [
            {"id": "one", "name": "Салон Рядом", "rating": 4.7, "reviews_count": 80},
            {"id": "two", "name": "Красивые люди", "rating": 4.5, "reviews_count": 51},
        ]
    )

    result = read_saved_competitors(cursor, business_id="business-1")

    assert result["status"] == "clarification_required"
    assert result["clarification"]["options"] == ["Салон Рядом", "Красивые люди"]
    assert result["result_ref"]["href"] == "/dashboard/card?tab=competitors"
    assert cursor.last_params == ("business-1",)


def test_saved_competitor_returns_only_cached_facts_without_claiming_refresh():
    cursor = CompetitorCursor(
        [
            {"id": "one", "name": "Салон Рядом", "rating": 4.7, "reviews_count": 80},
            {"id": "two", "name": "Красивые люди", "rating": 4.5, "reviews_count": 51},
        ]
    )

    result = read_saved_competitors(cursor, business_id="business-1", name="салон рядом")

    assert result["status"] == "completed"
    assert result["competitors"][0]["name"] == "Салон Рядом"
    assert result["fresh_external_check_performed"] is False
    assert "новая внешняя проверка не запускалась" in result["chat_response"].lower()
    assert result["external_writes_performed"] is False


def test_operator_tool_catalog_routes_neighbor_to_cached_competitors():
    cursor = CompetitorCursor(
        [{"id": "one", "name": "Салон Рядом", "rating": 4.7, "reviews_count": 80}]
    )

    result, pending = route_operator_message(
        cursor,
        business_id="business-1",
        user_id="user-1",
        message="Посмотри, как дела у соседа",
        channel="web",
        tool_planner=lambda _state: {
            "action": "tool_call",
            "tool": "competitors.list",
            "arguments": {},
        },
    )

    assert pending == {}
    assert result["status"] == "completed"
    assert result["capability"] == "competitors.read"
    assert result["competitors"][0]["name"] == "Салон Рядом"
    assert result["tool_calls"] == 1


def test_operator_tool_catalog_can_explain_feature_without_model_invention():
    result, pending = route_operator_message(
        object(),
        business_id="business-1",
        user_id="user-1",
        message="Хочу сведения о возможностях Telegram-радара",
        channel="web",
        tool_planner=lambda _state: {
            "action": "tool_call",
            "tool": "product.explain_feature",
            "arguments": {"feature_key": "telegram_radar"},
        },
    )

    assert pending == {}
    assert result["status"] == "completed"
    assert result["capability"] == "operator.product_explain"
    assert result["feature"]["key"] == "telegram_radar"
    assert result["result_ref"]["href"] == "/dashboard/telegram-radar"
    assert result["tool_calls"] == 1
