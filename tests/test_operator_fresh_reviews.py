from services.operator_fresh_reviews import classify_fresh_reviews_intent, refresh_reviews_from_operator


class FakeCursor:
    def __init__(self, *, map_url="https://yandex.ru/maps/org/oliver", without_response=2, balance=100):
        self.map_url = map_url
        self.without_response = without_response
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
        if "to_regclass" in self.last_query:
            table_ref = self.last_params[0] if self.last_params else ""
            if "operatorconsentpolicies" in str(table_ref):
                return {"table_ref": None}
            if "operatorcreditreservations" in str(table_ref):
                return {"to_regclass": "operatorcreditreservations"}
            return {"to_regclass": table_ref}
        if "from information_schema.columns" in self.last_query:
            table = self.last_params[0] if self.last_params else ""
            column = self.last_params[1] if len(self.last_params) > 1 else ""
            if table == "users" and column == "credits_balance":
                return {"?column?": 1}
            return None
        if "select credits_balance from users" in self.last_query:
            return {"credits_balance": self.balance}
        if "from operatorcreditreservations" in self.last_query and "sum" in self.last_query:
            return {"reserved_credits": 0, "used_credits": 0}
        if "from externalbusinessreviews" in self.last_query:
            return {"total": 5, "without_response": self.without_response, "latest_seen_at": "2026-05-23T20:00:00+00:00"}
        if "from businessmaplinks" in self.last_query:
            return {"url": self.map_url}
        if "returning id, status, reserved_credits" in self.last_query:
            return self.reservation
        if "returning id, status, source, task_type" in self.last_query:
            params = self.inserted_jobs[-1]
            return {"id": params[0], "status": "pending", "source": params[5], "task_type": params[4]}
        return None


def test_classifies_fresh_reviews_intent() -> None:
    assert classify_fresh_reviews_intent("Проверь новые отзывы")
    assert classify_fresh_reviews_intent("Обнови отзывы")
    assert not classify_fresh_reviews_intent("Подготовь ответы на отзывы")


def test_refresh_reviews_blocks_when_balance_is_insufficient() -> None:
    cursor = FakeCursor(without_response=3, balance=1)

    result = refresh_reviews_from_operator(cursor, business_id="biz-1", user_id="user-1")

    assert result["status"] == "blocked"
    assert "insufficient_balance" in result["blocked_reasons"]
    assert result["review_snapshot_before"]["without_response"] == 3
    assert result["external_writes_performed"] is False
    assert len(cursor.inserted_jobs) == 0


def test_refresh_reviews_queues_paid_read_only_job() -> None:
    cursor = FakeCursor(without_response=1)

    result = refresh_reviews_from_operator(cursor, business_id="biz-1", user_id="user-1")

    assert result["status"] == "queued"
    assert result["queue_id"]
    assert result["reservation_id"]
    assert result["review_snapshot_before"]["without_response"] == 1
    assert result["external_calls_performed"] is False
    assert result["external_writes_performed"] is False
    assert result["paid_actions_performed"] is True
    assert result["credit_reserved"] is True
    assert len(cursor.inserted_jobs) == 1
