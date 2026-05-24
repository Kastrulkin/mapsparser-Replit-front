from datetime import datetime, timezone

from services.operator_refresh_result import build_refresh_result_status


class FakeCursor:
    def __init__(self, *, queue=None, reviews=None):
        self.queue = queue
        self.reviews = reviews or []
        self.last_query = ""
        self.last_params = ()

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()

    def fetchone(self):
        if "from parsequeue" in self.last_query:
            return self.queue
        return None

    def fetchall(self):
        if "from externalbusinessreviews" in self.last_query:
            return self.reviews
        return []


def test_refresh_result_counts_new_unanswered_reviews() -> None:
    started_at = datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc)
    cursor = FakeCursor(
        queue={
            "id": "queue-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "status": "completed",
            "source": "apify_yandex",
            "task_type": "parse_card",
            "created_at": started_at,
            "updated_at": started_at,
        },
        reviews=[
            {
                "id": "review-1",
                "source": "yandex",
                "external_review_id": "ext-1",
                "rating": 5,
                "author_name": "Анна",
                "text": "Очень понравился сервис.",
                "response_text": "",
                "published_at": started_at,
                "created_at": started_at,
            },
            {
                "id": "review-2",
                "source": "yandex",
                "external_review_id": "ext-2",
                "rating": 4,
                "author_name": "Иван",
                "text": "Спасибо команде.",
                "response_text": "Спасибо!",
                "published_at": started_at,
                "created_at": started_at,
            },
        ],
    )

    result = build_refresh_result_status(cursor, business_id="biz-1", user_id="user-1", queue_id="queue-1")

    assert result["status"] == "completed"
    assert result["new_reviews_count"] == 2
    assert result["new_unanswered_reviews_count"] == 1
    assert result["new_reviews"][0]["author_name"] == "Анна"
    assert result["ui_actions"][1]["action"] == "generate_review_replies"
    assert result["external_writes_performed"] is False


def test_refresh_result_processing_waits_for_worker() -> None:
    cursor = FakeCursor(
        queue={
            "id": "queue-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "status": "processing",
            "created_at": datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc),
        }
    )

    result = build_refresh_result_status(cursor, business_id="biz-1", user_id="user-1", queue_id="queue-1")

    assert result["status"] == "processing"
    assert result["new_reviews_count"] == 0
    assert result["new_reviews"] == []


def test_refresh_result_reports_worker_failure() -> None:
    cursor = FakeCursor(
        queue={
            "id": "queue-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "status": "failed",
            "error_message": "apify timeout",
            "created_at": datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc),
        }
    )

    result = build_refresh_result_status(cursor, business_id="biz-1", user_id="user-1", queue_id="queue-1")

    assert result["status"] == "failed"
    assert result["blocked_reasons"] == ["refresh_job_failed"]
    assert "apify timeout" in result["chat_response"]


def test_refresh_result_requires_known_queue() -> None:
    missing_queue = build_refresh_result_status(FakeCursor(), business_id="biz-1", user_id="user-1", queue_id="")
    unknown_queue = build_refresh_result_status(FakeCursor(queue=None), business_id="biz-1", user_id="user-1", queue_id="queue-404")

    assert missing_queue["blocked_reasons"] == ["queue_id_required"]
    assert unknown_queue["blocked_reasons"] == ["refresh_job_not_found"]
