from services import operator_refresh_retry
from services.operator_refresh_retry import build_refresh_retry_plan, request_refresh_retry


class FakeCursor:
    def __init__(self, queue=None):
        self.queue = queue or {
            "id": "queue-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "url": "https://yandex.ru/maps/org/oliver",
            "status": "failed",
            "source": "apify_yandex",
            "task_type": "parse_card",
            "error_message": "timeout while parsing",
            "retry_after": None,
            "captcha_required": False,
            "captcha_status": "",
            "resume_requested": False,
            "warnings": "",
        }
        self.last_query = ""
        self.last_params = ()
        self.updated_parsequeue = False

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        if self.last_query.startswith("update parsequeue"):
            self.updated_parsequeue = True

    def fetchone(self):
        if "from parsequeue" in self.last_query:
            if self.last_params and self.last_params[0] == self.queue.get("id"):
                return self.queue
        return None


def test_refresh_retry_plan_allows_failed_readonly_job() -> None:
    cursor = FakeCursor()

    plan = build_refresh_retry_plan(cursor, business_id="biz-1", user_id="user-1", queue_id="queue-1")

    assert plan["status"] == "ready"
    assert plan["retry_allowed"] is True
    assert plan["reliability_state"]["status"] == "failed"
    assert plan["side_effects"]["parsequeue_jobs_created"] is False
    assert plan["side_effects"]["credit_reserved"] is False
    assert cursor.updated_parsequeue is False


def test_refresh_retry_plan_blocks_processing_job() -> None:
    cursor = FakeCursor(queue={
        "id": "queue-1",
        "business_id": "biz-1",
        "user_id": "user-1",
        "url": "https://yandex.ru/maps/org/oliver",
        "status": "processing",
        "error_message": "",
        "captcha_required": False,
    })

    plan = build_refresh_retry_plan(cursor, business_id="biz-1", user_id="user-1", queue_id="queue-1")

    assert plan["status"] == "blocked"
    assert "refresh_job_still_processing" in plan["blocked_reasons"]
    assert plan["retry_allowed"] is False


def test_refresh_retry_requires_explicit_confirmation() -> None:
    cursor = FakeCursor()

    result = request_refresh_retry(cursor, business_id="biz-1", user_id="user-1", queue_id="queue-1")

    assert result["status"] == "blocked"
    assert result["blocked_reasons"] == ["explicit_retry_confirmation_required"]
    assert result["side_effects"]["parsequeue_jobs_created"] is False
    assert cursor.updated_parsequeue is False


def test_refresh_retry_queues_new_paid_refresh_without_mutating_source(monkeypatch) -> None:
    cursor = FakeCursor()

    def fake_enqueue(cursor_arg, *, business_id, user_id, explicit_url=None, estimated_credits=None, metadata=None):
        assert cursor_arg is cursor
        assert business_id == "biz-1"
        assert user_id == "user-1"
        assert explicit_url == "https://yandex.ru/maps/org/oliver"
        assert estimated_credits == 10
        assert metadata["retry_source_queue_id"] == "queue-1"
        assert metadata["retry_requested_by_operator"] is True
        return {
            "status": "queued",
            "queue_id": "queue-2",
            "reservation_id": "reservation-1",
            "estimated_credits": 10,
            "balance_credits": 90,
            "billing_url": "/dashboard/billing",
            "side_effects": {
                "credit_reserved": True,
                "parsequeue_jobs_created": True,
                "external_calls_performed": False,
                "external_writes_performed": False,
                "credit_charged": False,
            },
        }

    monkeypatch.setattr(operator_refresh_retry, "enqueue_paid_operator_map_refresh", fake_enqueue)

    result = request_refresh_retry(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        queue_id="queue-1",
        estimated_credits=10,
        confirm_retry=True,
    )

    assert result["status"] == "queued"
    assert result["new_queue_id"] == "queue-2"
    assert result["retry_source_queue_id"] == "queue-1"
    assert result["reservation_id"] == "reservation-1"
    assert result["side_effects"]["parsequeue_jobs_created"] is True
    assert result["side_effects"]["credit_reserved"] is True
    assert result["side_effects"]["credit_charged"] is False
    assert result["side_effects"]["external_writes_performed"] is False
    assert "Старый failed job не изменялся" in result["chat_response"]
    assert cursor.updated_parsequeue is False
