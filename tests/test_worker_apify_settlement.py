import worker


class FakeCursor:
    def __init__(self, *, table_exists=True, reservation_id="reservation-1"):
        self.table_exists = table_exists
        self.reservation_id = reservation_id
        self.last_query = ""
        self.last_params = ()

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()

    def fetchone(self):
        if "to_regclass" in self.last_query:
            return {"exists": self.table_exists}
        if "from operatorcreditreservations" in self.last_query and self.reservation_id:
            return {"id": self.reservation_id}
        return None


def test_extract_apify_cost_from_run_data() -> None:
    payload = {"run_data": {"usageTotalUsd": 0.42}}

    assert worker._extract_apify_actual_cost_usd(payload) == 0.42


def test_worker_settlement_skips_without_provider_cost() -> None:
    cursor = FakeCursor()

    result = worker._settle_operator_apify_cost_if_present(
        cursor,
        {"id": "queue-1", "business_id": "biz-1", "user_id": "user-1", "source": "apify_yandex"},
        {"run_id": "run-1"},
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "provider_actual_cost_missing"


def test_worker_settlement_calls_operator_settlement_for_matching_reservation(monkeypatch) -> None:
    captured = {}

    def fake_settle(cursor, **kwargs):
        captured.update(kwargs)
        return {"status": "charged", "charged_credits": 3}

    monkeypatch.setattr(worker, "settle_apify_actual_cost", fake_settle)
    cursor = FakeCursor(reservation_id="reservation-42")

    result = worker._settle_operator_apify_cost_if_present(
        cursor,
        {"id": "queue-1", "business_id": "biz-1", "user_id": "user-1", "source": "apify_yandex"},
        {"run_id": "run-1", "usage_total_usd": "0.21"},
    )

    assert result["status"] == "charged"
    assert captured["business_id"] == "biz-1"
    assert captured["user_id"] == "user-1"
    assert captured["reservation_id"] == "reservation-42"
    assert captured["provider_actual_cost"] == "0.21"
    assert captured["provider_run_id"] == "run-1"


def test_worker_settlement_skips_when_reservation_missing() -> None:
    cursor = FakeCursor(reservation_id="")

    result = worker._settle_operator_apify_cost_if_present(
        cursor,
        {"id": "queue-1", "business_id": "biz-1", "user_id": "user-1", "source": "apify_yandex"},
        {"run_id": "run-1", "usageTotalUsd": "0.10"},
    )

    assert result["status"] == "skipped"
    assert result["reason"] == "operator_reservation_not_found"
