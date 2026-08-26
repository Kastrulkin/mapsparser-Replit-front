from __future__ import annotations

import pytest

from services import operator_core, operator_query
from services.operator_query import compile_operator_query, execute_operator_query, operator_query_tool_contract
from services.operator_tool_loop import run_operator_tool_loop


def _module_result(items):
    return {
        "status": "available",
        "items": items,
        "as_of": "2026-08-26T08:00:00+00:00",
        "freshness": {"status": "live"},
        "data_warnings": [],
    }


def test_compile_operator_query_normalizes_aliases_and_rejects_unknown_fields():
    query = compile_operator_query(
        {
            "resource": "services",
            "filters": [{"field": "name", "operator": "contains", "value": "аэропорт"}],
            "sort_by": "name",
            "sort_direction": "asc",
            "limit": 3,
            "view": "full",
        }
    )

    assert query["schema"] == "localos_operator_query_v1"
    assert query["filters"] == [{"field": "title", "operator": "contains", "value": "аэропорт"}]
    assert query["sort_by"] == "title"
    assert query["limit"] == 3

    with pytest.raises(ValueError, match="unsupported_filter_field"):
        compile_operator_query(
            {
                "resource": "services",
                "filters": [{"field": "business_id", "operator": "eq", "value": "other-tenant"}],
            }
        )


def test_services_query_filters_category_and_renders_full_items(monkeypatch):
    monkeypatch.setattr(
        operator_query,
        "list_operator_mobile_module",
        lambda *_args, **_kwargs: _module_result(
            [
                {
                    "id": "service-1",
                    "title": "Трансфер из аэропорта",
                    "category": "Трансферы",
                    "price": "50 EUR",
                    "description": "Встреча с табличкой.",
                    "status": "active",
                    "updated_at": "2026-08-25T10:00:00+00:00",
                },
                {
                    "id": "service-2",
                    "title": "Экскурсия",
                    "category": "Туры",
                    "price": "80 EUR",
                    "description": "Обзор города.",
                    "status": "active",
                    "updated_at": "2026-08-26T10:00:00+00:00",
                },
            ]
        ),
    )

    result = execute_operator_query(
        object(),
        business_id="business-1",
        arguments={
            "resource": "services",
            "filters": [{"field": "category", "operator": "contains", "value": "трансфер"}],
            "sort_by": "updated_at",
            "sort_direction": "desc",
            "limit": 10,
            "view": "full",
        },
    )

    assert result["status"] == "completed"
    assert result["count"] == 1
    assert result["items"][0]["id"] == "service-1"
    assert "Трансфер из аэропорта" in result["chat_response"]
    assert "Встреча с табличкой." in result["chat_response"]
    assert "Экскурсия" not in result["chat_response"]
    assert result["external_writes_performed"] is False


def test_content_query_uses_date_range_without_phrase_specific_runtime_code(monkeypatch):
    monkeypatch.setattr(
        operator_query,
        "list_operator_mobile_module",
        lambda *_args, **_kwargs: _module_result(
            [
                {"id": "old", "title": "Старый пост", "scheduled_for": "2026-08-24", "status": "edited"},
                {
                    "id": "target",
                    "title": "Вчерашний пост",
                    "scheduled_for": "2026-08-25",
                    "status": "edited",
                    "draft_text": "Полный текст вчерашнего поста.",
                },
                {"id": "new", "title": "Сегодняшний пост", "scheduled_for": "2026-08-26", "status": "edited"},
            ]
        ),
    )

    result = execute_operator_query(
        object(),
        business_id="business-1",
        arguments={
            "resource": "content",
            "filters": [
                {"field": "scheduled_for", "operator": "gte", "value": "2026-08-25"},
                {"field": "scheduled_for", "operator": "lte", "value": "2026-08-25"},
            ],
            "sort_by": "scheduled_for",
            "sort_direction": "asc",
            "limit": 20,
            "view": "full",
        },
    )

    assert [item["id"] for item in result["items"]] == ["target"]
    assert "Полный текст вчерашнего поста." in result["chat_response"]
    assert "Старый пост" not in result["chat_response"]
    assert "Сегодняшний пост" not in result["chat_response"]


class ReviewCursor:
    description = []

    def execute(self, _query, _params=None):
        return None

    def fetchall(self):
        return [
            {
                "id": "review-old",
                "business_id": "business-1",
                "source": "yandex",
                "rating": 3,
                "author_name": "Старый автор",
                "text": "Старый отзыв",
                "response_text": "",
                "published_at": "2026-08-24T12:00:00+00:00",
                "created_at": "2026-08-24T12:00:00+00:00",
                "updated_at": "2026-08-24T12:00:00+00:00",
            },
            {
                "id": "review-latest",
                "business_id": "business-1",
                "source": "google",
                "rating": 5,
                "author_name": "Новый автор",
                "text": "Последний отзыв",
                "response_text": "Спасибо!",
                "published_at": "2026-08-26T07:00:00+00:00",
                "created_at": "2026-08-26T07:00:00+00:00",
                "updated_at": "2026-08-26T07:00:00+00:00",
            },
        ]


def test_reviews_query_returns_latest_review_with_body():
    result = execute_operator_query(
        ReviewCursor(),
        business_id="business-1",
        arguments={
            "resource": "reviews",
            "sort_by": "published_at",
            "sort_direction": "desc",
            "limit": 1,
            "view": "full",
        },
    )

    assert result["count"] == 2
    assert [item["id"] for item in result["items"]] == ["review-latest"]
    assert "Последний отзыв" in result["chat_response"]
    assert "Ответ опубликован" in result["chat_response"]
    assert result["freshness"]["status"] == "stored_snapshot"


def test_full_view_caps_chat_body_without_hiding_result_count():
    query = compile_operator_query({"resource": "content", "limit": 20, "view": "full"})
    items = [
        {"id": f"item-{index}", "title": f"Пост {index}", "draft_text": f"Текст {index}"}
        for index in range(1, 13)
    ]

    response = operator_query.render_operator_query(query, items, total_count=12)

    assert "Нашёл 12 записей" in response
    assert "Пост 10" in response
    assert "Пост 11" not in response
    assert "Показал первые 10 из 12" in response


def test_truncated_source_window_is_not_presented_as_complete_total(monkeypatch):
    monkeypatch.setattr(
        operator_query,
        "list_operator_mobile_module",
        lambda *_args, **_kwargs: _module_result(
            [{"id": f"service-{index}", "title": f"Услуга {index}"} for index in range(200)]
        ),
    )

    result = execute_operator_query(
        object(),
        business_id="business-1",
        arguments={"resource": "services", "limit": 1, "view": "count"},
    )

    assert result["result_is_partial"] is True
    assert result["source_window_limit"] == 200
    assert "в доступном окне" in result["chat_response"].lower()
    assert result["data_warnings"]


def test_deterministic_query_tool_returns_after_one_compiler_step():
    tool = operator_query_tool_contract()
    tool["execute"] = lambda _arguments: {
        "status": "completed",
        "intent": "operator.query",
        "resource": "reviews",
        "items": [{"id": "review-1"}],
        "count": 1,
        "chat_response": "Последний отзыв: всё отлично.",
        "external_writes_performed": False,
    }
    planner_calls = []

    result = run_operator_tool_loop(
        business_id="business-1",
        user_id="user-1",
        message="Покажи последний отзыв",
        tools=[tool],
        planner=lambda state: planner_calls.append(state) or {
            "action": "tool_call",
            "tool": "localos.query",
            "arguments": {
                "resource": "reviews",
                "sort_by": "published_at",
                "sort_direction": "desc",
                "limit": 1,
                "view": "full",
            },
        },
    )

    assert result["chat_response"] == "Последний отзыв: всё отлично."
    assert result["planner_steps"] == 1
    assert result["tool_calls"] == 1
    assert result["compiled_query"]["resource"] == "reviews"
    assert len(planner_calls) == 1
    assert planner_calls[0]["current_timezone"] == "Europe/Moscow"
    assert planner_calls[0]["current_time"]


def test_explicit_new_reviews_check_uses_refresh_policy_instead_of_stored_query():
    planner_calls = []
    refresh_calls = []

    result, pending = operator_core.route_operator_message(
        object(),
        business_id="business-1",
        user_id="user-1",
        message="Проверь, нет ли новых отзывов на картах",
        channel="web",
        refresh_handler=lambda *_args, **kwargs: refresh_calls.append(kwargs) or {
            "status": "queued",
            "intent": "fresh_reviews_refresh",
            "chat_response": "Запустил обновление отзывов.",
            "external_writes_performed": False,
        },
        tool_planner=lambda state: planner_calls.append(state) or {"action": "final", "message": "unused"},
    )

    assert result["status"] == "queued"
    assert result["capability"] == "maps.refresh"
    assert refresh_calls[0]["business_id"] == "business-1"
    assert planner_calls == []
    assert pending == {}


@pytest.mark.parametrize(
    ("message", "resource"),
    [
        ("Покажи услуги категории Трансферы", "services"),
        ("Найди активные услуги со словом аэропорт", "services"),
        ("Какая у нас последняя услуга?", "services"),
        ("Покажи последний отзыв", "reviews"),
        ("Дай негативные отзывы за неделю", "reviews"),
        ("Выведи вчерашние записи контент-плана", "content"),
    ],
)
def test_query_paraphrases_reach_one_universal_contract(monkeypatch, message, resource):
    calls = []
    monkeypatch.setattr(
        operator_core,
        "execute_operator_query",
        lambda _cursor, *, business_id, arguments: calls.append((business_id, arguments)) or {
            "status": "completed",
            "intent": "operator.query",
            "resource": arguments["resource"],
            "items": [],
            "count": 0,
            "chat_response": "Запрос выполнен.",
            "external_writes_performed": False,
        },
    )

    result, pending = operator_core.route_operator_message(
        object(),
        business_id="business-1",
        user_id="user-1",
        message=message,
        channel="web",
        manual_review_handler=lambda *_args, **_kwargs: {"status": "unsupported"},
        tool_planner=lambda _state: {
            "action": "tool_call",
            "tool": "localos.query",
            "arguments": {"resource": resource, "limit": 10, "view": "full"},
        },
    )

    assert result["status"] == "completed"
    assert result["capability"] == "operator.query"
    assert calls == [("business-1", {"resource": resource, "limit": 10, "view": "full"})]
    assert pending == {}
