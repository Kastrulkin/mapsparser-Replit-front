from services.operator_capabilities import (
    build_operator_help_response,
    classify_operator_help_intent,
    classify_unanswered_reviews_status_intent,
    get_unanswered_reviews_status,
)


class FakeCursor:
    def __init__(self, *, unanswered_count=2):
        self.unanswered_count = unanswered_count
        self.last_query = ""
        self.last_params = ()

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()

    def fetchone(self):
        if "to_regclass" in self.last_query:
            return {"table_ref": "externalbusinessreviews"}
        if "count(*) as cnt" in self.last_query:
            return {"cnt": self.unanswered_count}
        return None

    def fetchall(self):
        if "from externalbusinessreviews" not in self.last_query:
            return []
        if self.unanswered_count <= 0:
            return []
        return [
            {
                "id": "review-1",
                "source": "yandex",
                "external_review_id": "ext-1",
                "rating": 5,
                "author_name": "Анна",
                "text": "Очень понравился сервис.",
                "published_at": "2026-05-24T10:00:00Z",
                "created_at": "2026-05-24T10:05:00Z",
            }
        ]


def test_classifies_unanswered_reviews_status_intent() -> None:
    assert classify_unanswered_reviews_status_intent("У нас есть неотвеченные отзывы сейчас в базе?")
    assert classify_unanswered_reviews_status_intent("Сколько отзывов без ответа?")
    assert not classify_unanswered_reviews_status_intent("Подготовь ответы на отзывы")
    assert not classify_unanswered_reviews_status_intent("Проверь новые отзывы")


def test_get_unanswered_reviews_status_returns_cached_count_and_reviews() -> None:
    result = get_unanswered_reviews_status(FakeCursor(unanswered_count=2), business_id="biz-1")

    assert result["status"] == "completed"
    assert result["intent"] == "unanswered_reviews_status"
    assert result["unanswered_reviews_count"] == 2
    assert result["new_unanswered_reviews_count"] == 2
    assert result["new_reviews"][0]["author_name"] == "Анна"
    assert result["credit_charged"] is False
    assert result["external_writes_performed"] is False
    assert result["ui_actions"][1]["action"] == "generate_review_replies"


def test_get_unanswered_reviews_status_handles_empty_cached_reviews() -> None:
    result = get_unanswered_reviews_status(FakeCursor(unanswered_count=0), business_id="biz-1")

    assert result["unanswered_reviews_count"] == 0
    assert "нет отзывов без ответа" in result["chat_response"].lower()


def test_operator_help_lists_supported_chat_scenarios() -> None:
    assert classify_operator_help_intent("Что ты умеешь?")

    result = build_operator_help_response()

    assert result["status"] == "completed"
    assert result["intent"] == "operator_help"
    assert "Показать отзывы, которые ждут ответа" in result["chat_response"]
    assert "read-only" not in result["chat_response"]
    assert "Составить контент-план" in result["chat_response"]
    assert "Улучшить названия" in result["chat_response"]
