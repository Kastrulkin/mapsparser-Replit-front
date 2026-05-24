from services import operator_map_refresh
from services.operator_map_refresh import build_operator_map_refresh_plan, enqueue_operator_map_refresh, enqueue_paid_operator_map_refresh


class FakeCursor:
    def __init__(self, *, map_url="https://yandex.ru/maps/org/oliver", balance=100):
        self.map_url = map_url
        self.balance = balance
        self.last_query = ""
        self.last_params = ()
        self.inserted_jobs = []
        self.inserted_reservations = []
        self.reservation = None

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        if "insert into parsequeue" in self.last_query:
            self.inserted_jobs.append(params or ())
        if "insert into operatorcreditreservations" in self.last_query:
            self.inserted_reservations.append(params or ())
            self.reservation = {
                "id": (params or ("reservation-1",))[0],
                "status": "reserved",
                "reserved_credits": (params or (None, None, None, None, None, 0))[6],
            }

    def fetchone(self):
        query = self.last_query
        if "to_regclass" in query:
            table_ref = self.last_params[0] if self.last_params else ""
            if "operatorconsentpolicies" in str(table_ref):
                return {"table_ref": None}
            if "operatorcreditreservations" in str(table_ref):
                return {"to_regclass": "operatorcreditreservations"}
            return {"to_regclass": table_ref}
        if "from information_schema.columns" in query:
            table = self.last_params[0] if self.last_params else ""
            column = self.last_params[1] if len(self.last_params) > 1 else ""
            if table == "users" and column == "credits_balance":
                return {"?column?": 1}
            return None
        if "select credits_balance from users" in query:
            return {"credits_balance": self.balance}
        if "from operatorcreditreservations" in query and "sum" in query:
            return {"reserved_credits": 0, "used_credits": 0}
        if "from businessmaplinks" in query:
            return {"url": self.map_url}
        if "returning id, status, reserved_credits" in query:
            return self.reservation
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


def test_paid_map_refresh_reserves_credits_and_links_reservation_to_queue() -> None:
    cursor = FakeCursor(balance=50)

    result = enqueue_paid_operator_map_refresh(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        estimated_credits=10,
    )

    assert result["status"] == "queued"
    assert result["reservation_id"]
    assert result["queue_id"]
    assert result["side_effects"]["credit_reserved"] is True
    assert result["side_effects"]["parsequeue_jobs_created"] is True
    assert len(cursor.inserted_reservations) == 1
    assert len(cursor.inserted_jobs) == 1
    reservation_metadata = cursor.inserted_reservations[0][7]
    assert result["queue_id"] in reservation_metadata
    assert cursor.inserted_jobs[0][0] == result["queue_id"]


def test_paid_map_refresh_blocks_when_balance_is_insufficient() -> None:
    cursor = FakeCursor(balance=2)

    result = enqueue_paid_operator_map_refresh(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        estimated_credits=10,
    )

    assert result["status"] == "blocked"
    assert "insufficient_balance" in result["blocked_reasons"]
    assert len(cursor.inserted_reservations) == 0
    assert len(cursor.inserted_jobs) == 0
