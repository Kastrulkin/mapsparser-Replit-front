from services.operator_credit_reservation import build_credit_reservation_plan, reserve_paid_action_credits


class FakeCursor:
    def __init__(self, *, table_available=True, balance=100, active_reserved=0):
        self.table_available = table_available
        self.balance = balance
        self.active_reserved = active_reserved
        self.last_query = ""
        self.last_params = ()
        self.inserted = []

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        if "insert into operatorcreditreservations" in self.last_query:
            self.inserted.append(params or ())

    def fetchone(self):
        query = self.last_query
        if "to_regclass" in query:
            if self.table_available:
                return {"to_regclass": "operatorcreditreservations"}
            return {"to_regclass": None}
        if "information_schema.columns" in query:
            return {"?column?": 1}
        if "from users" in query:
            return {"credits_balance": self.balance}
        if "from operatorcreditreservations" in query and "sum" in query:
            return {"reserved_credits": self.active_reserved}
        if "returning id" in query:
            params = self.inserted[-1]
            return {"id": params[0], "status": "reserved", "reserved_credits": params[6]}
        return None


def test_credit_reservation_plan_accounts_for_active_reservations() -> None:
    cursor = FakeCursor(balance=100, active_reserved=30)

    plan = build_credit_reservation_plan(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=50,
        idempotency_key="idem-1",
    )

    assert plan["status"] == "ready"
    assert plan["idempotency_key"] == "idem-1"
    assert plan["balance_credits"] == 100
    assert plan["active_reserved_credits"] == 30
    assert plan["available_after_reservations"] == 70
    assert plan["reservation_would_be_created"] is True
    assert plan["side_effects"]["credit_reserved"] is False


def test_credit_reservation_plan_blocks_when_unreserved_balance_is_low() -> None:
    cursor = FakeCursor(balance=100, active_reserved=95)

    plan = build_credit_reservation_plan(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
    )

    assert plan["status"] == "blocked"
    assert "insufficient_unreserved_balance" in plan["blocked_reasons"]
    assert plan["reservation_would_be_created"] is False


def test_credit_reservation_plan_blocks_when_schema_is_unavailable() -> None:
    cursor = FakeCursor(table_available=False, balance=100)

    plan = build_credit_reservation_plan(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
    )

    assert plan["status"] == "blocked"
    assert "reservation_ledger_unavailable" in plan["blocked_reasons"]


def test_reserve_paid_action_credits_records_reservation_when_ready() -> None:
    cursor = FakeCursor(balance=100, active_reserved=0)

    result = reserve_paid_action_credits(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
        idempotency_key="idem-1",
    )

    assert result["status"] == "reserved"
    assert result["reserved_credits"] == 10
    assert result["side_effects"]["reservation_created"] is True
    assert result["side_effects"]["credit_reserved"] is True
    assert len(cursor.inserted) == 1
