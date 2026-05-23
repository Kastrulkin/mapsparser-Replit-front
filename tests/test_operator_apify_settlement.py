from services.operator_apify_settlement import provider_actual_cost_to_credits, settle_apify_actual_cost


class FakeCursor:
    def __init__(self, *, balance=100, reserved=5):
        self.balance = balance
        self.reservation = {
            "id": "res-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "action_key": "map_reviews_refresh",
            "status": "reserved",
            "reserved_credits": reserved,
            "charged_credits": 0,
            "released_credits": 0,
            "credit_ledger_id": None,
        }
        self.last_query = ""
        self.last_params = ()
        self.ledger_entries = []
        self.user_updates = []
        self.reservation_updates = []
        self.existing_external_ids = set()

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        if "update users" in self.last_query:
            self.user_updates.append(params or ())
            self.balance -= int((params or (0,))[0] or 0)
        if "insert into credit_ledger" in self.last_query:
            self.ledger_entries.append(params or ())
        if "update operatorcreditreservations" in self.last_query:
            self.reservation_updates.append(params or ())
            self.reservation["status"] = params[0]
            self.reservation["charged_credits"] += int(params[1] or 0)
            self.reservation["released_credits"] += int(params[2] or 0)

    def fetchone(self):
        query = self.last_query
        params = self.last_params
        if "from operatorcreditreservations" in query and "where id =" in query:
            return self.reservation
        if "information_schema.columns" in query:
            return {"?column?": 1}
        if "to_regclass" in query:
            return {"to_regclass": str(params[0]).replace("public.", "")}
        if "from users" in query:
            return {"credits_balance": self.balance}
        if "from credit_ledger" in query:
            external_id = str(params[0] if params else "")
            return {"id": "existing"} if external_id in self.existing_external_ids else None
        return None


def test_provider_actual_cost_to_credits_uses_x10_ceiling() -> None:
    assert provider_actual_cost_to_credits("0") == 0
    assert provider_actual_cost_to_credits("0.24") == 3
    assert provider_actual_cost_to_credits("1.00") == 10
    assert provider_actual_cost_to_credits("-1") is None
    assert provider_actual_cost_to_credits("not-a-number") is None


def test_settle_apify_actual_cost_charges_inside_reservation() -> None:
    cursor = FakeCursor(balance=100, reserved=5)

    result = settle_apify_actual_cost(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        reservation_id="res-1",
        provider_actual_cost="0.30",
        provider_run_id="run-1",
    )

    assert result["status"] == "charged"
    assert result["actual_credits"] == 3
    assert result["charged_credits"] == 3
    assert result["overage_credits"] == 0
    assert cursor.ledger_entries[0][2] == -3


def test_settle_apify_actual_cost_charges_overage_when_actual_exceeds_reserved() -> None:
    cursor = FakeCursor(balance=100, reserved=2)

    result = settle_apify_actual_cost(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        reservation_id="res-1",
        provider_actual_cost="0.50",
        provider_run_id="run-2",
    )

    assert result["status"] == "charged"
    assert result["actual_credits"] == 5
    assert result["charged_credits"] == 5
    assert result["overage_credits"] == 3
    assert cursor.ledger_entries[0][2] == -2
    assert cursor.ledger_entries[1][2] == -3


def test_settle_apify_actual_cost_releases_zero_actual_cost() -> None:
    cursor = FakeCursor(balance=100, reserved=2)

    result = settle_apify_actual_cost(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        reservation_id="res-1",
        provider_actual_cost="0",
        provider_run_id="run-3",
    )

    assert result["status"] == "released"
    assert result["charged_credits"] == 0
    assert len(cursor.ledger_entries) == 0


def test_settle_apify_actual_cost_blocks_invalid_cost() -> None:
    cursor = FakeCursor(balance=100, reserved=2)

    result = settle_apify_actual_cost(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        reservation_id="res-1",
        provider_actual_cost="bad",
    )

    assert result["status"] == "blocked"
    assert "invalid_provider_actual_cost" in result["blocked_reasons"]
