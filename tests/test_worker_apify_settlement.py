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


class FakeFailureCursor:
    def __init__(self, row):
        self.row = row
        self.last_query = ""
        self.last_params = ()

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()

    def fetchone(self):
        if "from parsequeue" in self.last_query:
            return self.row
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


def test_failed_operator_refresh_releases_reservation_and_sends_followup(monkeypatch) -> None:
    captured = {"commits": 0}

    def fake_release(cursor, **kwargs):
        captured["release"] = kwargs
        return {"status": "released", "side_effects": {"credit_released": True}}

    def fake_followup(cursor, **kwargs):
        captured["followup"] = kwargs
        return {"status": "sent", "sent": True}

    def fake_commit():
        captured["commits"] += 1

    monkeypatch.setattr(worker, "release_failed_refresh_reservation", fake_release)
    monkeypatch.setattr(worker, "dispatch_operator_refresh_telegram_followup", fake_followup)
    cursor = FakeFailureCursor(
        {
            "id": "queue-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "source": "apify_yandex",
            "task_type": "parse_card",
        }
    )

    result = worker._finalize_failed_operator_refresh(cursor, "queue-1", fake_commit)

    assert result["status"] == "completed"
    assert captured["release"]["business_id"] == "biz-1"
    assert captured["release"]["user_id"] == "user-1"
    assert captured["release"]["queue_id"] == "queue-1"
    assert captured["release"]["confirm_release"] is True
    assert captured["followup"]["business_id"] == "biz-1"
    assert captured["followup"]["queue_id"] == "queue-1"
    assert captured["commits"] == 1


def test_failed_operator_refresh_skips_non_refresh_queue(monkeypatch) -> None:
    def fail_release(cursor, **kwargs):
        raise AssertionError("release should not be called")

    monkeypatch.setattr(worker, "release_failed_refresh_reservation", fail_release)
    cursor = FakeFailureCursor(
        {
            "id": "queue-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "source": "manual",
            "task_type": "parse_card",
        }
    )

    result = worker._finalize_failed_operator_refresh(cursor, "queue-1")

    assert result["status"] == "skipped"
    assert result["reason"] == "not_operator_map_refresh"


def test_failed_operator_refresh_skips_followup_without_reservation(monkeypatch) -> None:
    def fake_release(cursor, **kwargs):
        return {"status": "blocked", "reservation_id": None, "blocked_reasons": ["no_recovery_action_available"]}

    def fail_followup(cursor, **kwargs):
        raise AssertionError("followup should not be called without reservation")

    monkeypatch.setattr(worker, "release_failed_refresh_reservation", fake_release)
    monkeypatch.setattr(worker, "dispatch_operator_refresh_telegram_followup", fail_followup)
    cursor = FakeFailureCursor(
        {
            "id": "queue-1",
            "business_id": "biz-1",
            "user_id": "user-1",
            "source": "apify_yandex",
            "task_type": "parse_card",
        }
    )

    result = worker._finalize_failed_operator_refresh(cursor, "queue-1")

    assert result["status"] == "skipped"
    assert result["reason"] == "operator_reservation_not_found_or_not_releasable"
