from services import operator_map_refresh
from services.operator_map_refresh import build_operator_map_refresh_plan, enqueue_operator_map_refresh


class FakeCursor:
    def __init__(self, *, map_url="https://yandex.ru/maps/org/oliver"):
        self.map_url = map_url
        self.last_query = ""
        self.last_params = ()
        self.inserted_jobs = []

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        if "insert into parsequeue" in self.last_query:
            self.inserted_jobs.append(params or ())

    def fetchone(self):
        query = self.last_query
        if "from businessmaplinks" in query:
            return {"url": self.map_url}
        if "returning id, status, source, task_type" in query:
            params = self.inserted_jobs[-1]
            return {
                "id": params[0],
                "status": "pending",
                "source": params[5],
                "task_type": params[4],
            }
        return None


def test_map_refresh_plan_blocks_when_runtime_flag_disabled() -> None:
    cursor = FakeCursor()

    plan = build_operator_map_refresh_plan(
        cursor,
        business_id="biz-1",
        user_id="user-1",
    )

    assert plan["status"] == "blocked"
    assert "operator_apify_refresh_disabled" in plan["blocked_reasons"]
    assert plan["side_effects"]["parsequeue_jobs_created"] is False


def test_map_refresh_enqueue_creates_parsequeue_job_when_flag_enabled(monkeypatch) -> None:
    monkeypatch.setattr(operator_map_refresh, "OPERATOR_APIFY_REFRESH_ENABLED", True)
    cursor = FakeCursor()

    result = enqueue_operator_map_refresh(
        cursor,
        business_id="biz-1",
        user_id="user-1",
    )

    assert result["status"] == "queued"
    assert result["queue_status"] == "pending"
    assert result["source"] == "apify_yandex"
    assert result["side_effects"]["parsequeue_jobs_created"] is True
    assert result["side_effects"]["external_calls_performed"] is False
    assert len(cursor.inserted_jobs) == 1
    assert cursor.inserted_jobs[0][4] == "parse_card"
    assert cursor.inserted_jobs[0][5] == "apify_yandex"


def test_map_refresh_plan_requires_map_link() -> None:
    cursor = FakeCursor(map_url="")

    plan = build_operator_map_refresh_plan(
        cursor,
        business_id="biz-1",
        user_id="user-1",
    )

    assert "map_link_required" in plan["blocked_reasons"]
