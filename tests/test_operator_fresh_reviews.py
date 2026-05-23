from services import operator_map_refresh
from services.operator_fresh_reviews import classify_fresh_reviews_intent, refresh_reviews_from_operator


class FakeCursor:
    def __init__(self, *, map_url="https://yandex.ru/maps/org/oliver", without_response=2):
        self.map_url = map_url
        self.without_response = without_response
        self.last_query = ""
        self.last_params = ()
        self.inserted_jobs = []

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        if "insert into parsequeue" in self.last_query:
            self.inserted_jobs.append(params or ())

    def fetchone(self):
        if "from externalbusinessreviews" in self.last_query:
            return {"total": 5, "without_response": self.without_response, "latest_seen_at": "2026-05-23T20:00:00+00:00"}
        if "from businessmaplinks" in self.last_query:
            return {"url": self.map_url}
        if "returning id, status, source, task_type" in self.last_query:
            params = self.inserted_jobs[-1]
            return {"id": params[0], "status": "pending", "source": params[5], "task_type": params[4]}
        return None


def test_classifies_fresh_reviews_intent() -> None:
    assert classify_fresh_reviews_intent("Проверь новые отзывы")
    assert classify_fresh_reviews_intent("Обнови отзывы")
    assert not classify_fresh_reviews_intent("Подготовь ответы на отзывы")


def test_refresh_reviews_blocks_when_runtime_disabled() -> None:
    cursor = FakeCursor(without_response=3)

    result = refresh_reviews_from_operator(cursor, business_id="biz-1", user_id="user-1")

    assert result["status"] == "blocked"
    assert "operator_apify_refresh_disabled" in result["blocked_reasons"]
    assert result["review_snapshot_before"]["without_response"] == 3
    assert result["external_writes_performed"] is False
    assert len(cursor.inserted_jobs) == 0


def test_refresh_reviews_queues_read_only_job_when_enabled(monkeypatch) -> None:
    monkeypatch.setattr(operator_map_refresh, "OPERATOR_APIFY_REFRESH_ENABLED", True)
    cursor = FakeCursor(without_response=1)

    result = refresh_reviews_from_operator(cursor, business_id="biz-1", user_id="user-1")

    assert result["status"] == "queued"
    assert result["queue_id"]
    assert result["review_snapshot_before"]["without_response"] == 1
    assert result["external_calls_performed"] is False
    assert result["external_writes_performed"] is False
    assert len(cursor.inserted_jobs) == 1
