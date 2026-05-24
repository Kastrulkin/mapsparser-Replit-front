from datetime import datetime, timezone

from services.operator_refresh_result import build_parse_reliability_state, build_refresh_result_status, list_refresh_jobs


class FakeCursor:
    def __init__(self, *, queue=None, queues=None, reviews=None, reservations=None):
        self.queue = queue
        self.queues = queues or []
        self.reviews = reviews or []
        self.reservations = reservations or []
        self.last_query = ""
        self.last_params = ()

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()

    def fetchone(self):
        if "to_regclass" in self.last_query:
            return {"to_regclass": "operatorcreditreservations"}
        if "from parsequeue" in self.last_query:
            if self.queues and self.last_params:
                queue_id = self.last_params[0]
                for queue in self.queues:
                    if queue.get("id") == queue_id:
                        return queue
            return self.queue
        if "from operatorcreditreservations" in self.last_query:
            queue_id = self.last_params[2]
            for reservation in self.reservations:
                metadata = reservation.get("metadata") or {}
                if metadata.get("parsequeue_id") == queue_id:
                    return reservation
        return None

    def fetchall(self):
        if "from parsequeue" in self.last_query:
            return self.queues
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
    assert result["result_summary"]["status"] == "new_reviews_found"
    assert result["result_summary"]["primary_action"] == "generate_review_replies"
    assert result["new_reviews"][0]["author_name"] == "Анна"
    assert result["ui_actions"][1]["action"] == "generate_review_replies"
    assert result["external_writes_performed"] is False
    assert result["billing_state"]["status"] == "not_found"


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
            "error_message": "reason_code=timeout; apify timeout",
            "created_at": datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc),
        }
    )

    result = build_refresh_result_status(cursor, business_id="biz-1", user_id="user-1", queue_id="queue-1")

    assert result["status"] == "failed"
    assert result["blocked_reasons"] == ["refresh_job_failed"]
    assert "apify timeout" in result["chat_response"]
    assert result["reliability_state"]["status"] == "failed"
    assert result["reliability_state"]["reason_code"] == "timeout"
    assert "Таймаут" in result["reliability_state"]["title"]


def test_refresh_result_requires_known_queue() -> None:
    missing_queue = build_refresh_result_status(FakeCursor(), business_id="biz-1", user_id="user-1", queue_id="")
    unknown_queue = build_refresh_result_status(FakeCursor(queue=None), business_id="biz-1", user_id="user-1", queue_id="queue-404")

    assert missing_queue["blocked_reasons"] == ["queue_id_required"]
    assert unknown_queue["blocked_reasons"] == ["refresh_job_not_found"]


def test_list_refresh_jobs_summarizes_recent_jobs() -> None:
    started_at = datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc)
    cursor = FakeCursor(
        queues=[
            {
                "id": "queue-completed",
                "business_id": "biz-1",
                "user_id": "user-1",
                "status": "completed",
                "source": "apify_yandex",
                "task_type": "parse_card",
                "created_at": started_at,
                "updated_at": started_at,
            },
            {
                "id": "queue-processing",
                "business_id": "biz-1",
                "user_id": "user-1",
                "status": "processing",
                "retry_after": "2026-05-24T10:10:00+00:00",
                "source": "apify_yandex",
                "task_type": "parse_card",
                "created_at": started_at,
                "updated_at": started_at,
            },
            {
                "id": "queue-failed",
                "business_id": "biz-1",
                "user_id": "user-1",
                "status": "failed",
                "source": "apify_yandex",
                "task_type": "parse_card",
                "error_message": "apify timeout",
                "created_at": started_at,
                "updated_at": started_at,
            },
        ],
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
        ],
    )

    result = list_refresh_jobs(cursor, business_id="biz-1", user_id="user-1", limit=10)

    assert result["status"] == "completed"
    assert result["summary"]["jobs_count"] == 3
    assert result["summary"]["processing_count"] == 1
    assert result["summary"]["completed_count"] == 1
    assert result["summary"]["failed_count"] == 1
    assert result["summary"]["retrying_count"] == 1
    assert result["summary"]["reliability_failed_count"] == 1
    assert result["summary"]["new_unanswered_reviews_count"] == 1
    assert result["jobs"][0]["queue_id"] == "queue-completed"
    assert result["jobs"][0]["result_summary"]["title"] == "Найдено новых отзывов: 1"
    assert result["jobs"][0]["ui_actions"][0]["action"] == "check_refresh_result"
    assert result["jobs"][1]["reliability_state"]["status"] == "retrying"
    assert result["limits"]["external_writes_performed"] is False


def test_refresh_result_includes_billing_state_from_reservation_metadata() -> None:
    started_at = datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc)
    cursor = FakeCursor(
        queue={
            "id": "queue-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "status": "completed",
            "created_at": started_at,
            "updated_at": started_at,
        },
        reservations=[
            {
                "id": "reservation-1",
                "status": "charged",
                "estimated_credits": 5,
                "reserved_credits": 5,
                "charged_credits": 3,
                "released_credits": 2,
                "metadata": {
                    "parsequeue_id": "queue-1",
                    "provider": "apify",
                    "provider_actual_cost": "0.24",
                    "credit_multiplier": 10,
                    "actual_credits": 3,
                    "overage_credits": 0,
                    "settlement_status": "charged",
                },
                "created_at": started_at,
                "updated_at": started_at,
                "finalized_at": started_at,
            }
        ],
        reviews=[],
    )

    result = build_refresh_result_status(cursor, business_id="biz-1", user_id="user-1", queue_id="queue-1")

    assert result["status"] == "completed"
    assert result["billing_state"]["status"] == "charged"
    assert result["billing_state"]["charged_credits"] == 3
    assert result["billing_state"]["released_credits"] == 2
    assert result["billing_state"]["provider_actual_cost"] == "0.24"
    assert "provider cost" in result["billing_state"]["explanation"]
    assert result["billing_state"]["user_facing_summary"]["charged"] == 3


def test_refresh_result_exposes_retry_lineage_from_reservation_metadata() -> None:
    started_at = datetime(2026, 5, 24, 10, 0, tzinfo=timezone.utc)
    cursor = FakeCursor(
        queue={
            "id": "queue-2",
            "business_id": "biz-1",
            "user_id": "user-1",
            "status": "processing",
            "created_at": started_at,
            "updated_at": started_at,
        },
        reservations=[
            {
                "id": "reservation-2",
                "status": "reserved",
                "estimated_credits": 10,
                "reserved_credits": 10,
                "charged_credits": 0,
                "released_credits": 0,
                "metadata": {
                    "parsequeue_id": "queue-2",
                    "retry_source_queue_id": "queue-1",
                    "retry_source_status": "failed",
                    "retry_requested_by_operator": True,
                    "retry_reason_code": "timeout",
                },
                "created_at": started_at,
                "updated_at": started_at,
                "finalized_at": None,
            }
        ],
    )

    result = build_refresh_result_status(cursor, business_id="biz-1", user_id="user-1", queue_id="queue-2")

    assert result["billing_state"]["retry_source_queue_id"] == "queue-1"
    assert result["billing_state"]["retry_requested_by_operator"] is True
    assert result["billing_state"]["retry_reason_code"] == "timeout"


def test_parse_reliability_state_explains_captcha_without_external_writes() -> None:
    result = build_parse_reliability_state(
        {
            "status": "captcha",
            "captcha_required": 1,
            "captcha_status": "waiting",
            "error_message": "reason_code=captcha; captcha_required",
            "warnings": "",
        }
    )

    assert result["status"] == "captcha_required"
    assert result["severity"] == "warning"
    assert result["reason_code"] == "captcha"
    assert "не публикует" in result["explanation"]


def test_parse_reliability_state_reports_completed_warnings() -> None:
    result = build_parse_reliability_state(
        {
            "status": "completed",
            "warnings": "operator_apify_settlement:charged:credits=3 | low_quality_payload:services",
        }
    )

    assert result["status"] == "warning"
    assert result["reason_code"] == "completed_with_warnings"
    assert len(result["warnings"]) == 2


def test_parse_reliability_state_includes_technical_attempt_details() -> None:
    result = build_parse_reliability_state(
        {
            "status": "failed",
            "error_message": "reason_code=timeout; transient_retry_attempt=3; attempt=3; max_attempts=8",
            "retry_after": "2026-05-24T10:10:00+00:00",
            "captcha_required": False,
            "warnings": "provider timeout",
        }
    )

    assert result["technical_details"]["queue_status"] == "failed"
    assert result["technical_details"]["retry_after"] == "2026-05-24T10:10:00+00:00"
    assert result["technical_details"]["attempts"]["transient_retry_attempt"] == "3"
    assert result["technical_details"]["attempts"]["max_attempts"] == "8"
    assert result["technical_details"]["warnings_count"] == 1
