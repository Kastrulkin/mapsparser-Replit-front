from datetime import datetime, timezone

from services.operator_async_jobs import (
    cancel_operator_async_job,
    create_operator_async_job,
    load_operator_async_job,
    retry_operator_async_job,
)


class AsyncJobCursor:
    def __init__(self):
        self.job = None
        self.rows = []

    def execute(self, query, params=()):
        normalized = " ".join(str(query).lower().split())
        now = datetime.now(timezone.utc)
        if normalized.startswith("insert into operator_async_jobs"):
            if not self.job:
                self.job = {
                    "id": params[0],
                    "action_id": params[1],
                    "user_id": params[2],
                    "business_id": params[3],
                    "kind": params[4],
                    "status": "queued",
                    "progress": 0,
                    "stage": params[5],
                    "payload_json": params[6],
                    "idempotency_key": params[7],
                    "attempt_count": 0,
                    "max_attempts": params[8],
                    "created_at": now,
                    "updated_at": now,
                }
            self.rows = [self.job]
        elif "left join operatoractions" in normalized:
            self.rows = [{**self.job, "external_effects": False, "action_idempotency_key": "action-key"}] if self.job and self.job["id"] == params[0] else []
        elif normalized.startswith("select * from operator_async_jobs"):
            self.rows = [self.job] if self.job and self.job["id"] == params[0] else []
        elif "set status = 'queued'" in normalized:
            self.job.update({"status": "queued", "progress": 0, "stage": "Повтор поставлен в очередь", "error_text": None, "updated_at": now})
            self.rows = [self.job]
        elif "set status = 'cancelled'" in normalized:
            self.job.update({"status": "cancelled", "progress": 100, "stage": "Остановлено", "completed_at": now, "updated_at": now})
            self.rows = [self.job]
        else:
            raise AssertionError(f"Unexpected query: {normalized}")

    def fetchone(self):
        return self.rows[0] if self.rows else None


def test_durable_job_is_idempotent_and_visible_only_in_scope():
    cursor = AsyncJobCursor()
    first = create_operator_async_job(
        cursor,
        user_id="u-1",
        action_id="a-1",
        business_id="b-1",
        kind="content_plan_generate",
        payload={"period_days": 30},
        idempotency_key="plan-key",
        stage="Собираем данные",
    )
    second = create_operator_async_job(
        cursor,
        user_id="u-1",
        action_id="a-1",
        business_id="b-1",
        kind="content_plan_generate",
        payload={"period_days": 30},
        idempotency_key="plan-key",
        stage="Собираем данные",
    )

    assert first["id"] == second["id"]
    assert load_operator_async_job(cursor, job_id=first["id"], user_id="u-1", scope={"kind": "business", "business_ids": ["b-1"]})
    assert load_operator_async_job(cursor, job_id=first["id"], user_id="u-1", scope={"kind": "business", "business_ids": ["b-2"]}) is None


def test_failed_job_can_retry_but_cannot_bypass_scope():
    cursor = AsyncJobCursor()
    created = create_operator_async_job(
        cursor,
        user_id="u-1",
        action_id="a-1",
        business_id="b-1",
        kind="content_draft_generate",
        payload={"item_id": "i-1"},
        idempotency_key="draft-key",
        stage="Готовим текст",
    )
    cursor.job.update({"status": "failed", "error_text": "temporary", "attempt_count": 1})

    assert retry_operator_async_job(cursor, job_id=created["id"], user_id="u-1", scope={"kind": "business", "business_ids": ["b-2"]}) is None
    retried = retry_operator_async_job(cursor, job_id=created["id"], user_id="u-1", scope={"kind": "business", "business_ids": ["b-1"]})
    assert retried["status"] == "queued"


def test_queued_job_can_be_cancelled_without_deleting_it():
    cursor = AsyncJobCursor()
    created = create_operator_async_job(
        cursor,
        user_id="u-1",
        action_id="a-1",
        business_id="b-1",
        kind="content_plan_generate",
        payload={},
        idempotency_key="cancel-key",
        stage="В очереди",
    )
    cancelled = cancel_operator_async_job(
        cursor,
        job_id=created["id"],
        user_id="u-1",
        scope={"kind": "business", "business_ids": ["b-1"]},
    )

    assert cancelled["status"] == "cancelled"
    assert cancelled["terminal"] is True
