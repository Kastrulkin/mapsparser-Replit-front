import services.operator_paid_executor
from services.operator_paid_executor import build_paid_action_execution_attempt


class FakeCursor:
    def __init__(self, policy=None, balance=100, reservation_table_available=True, active_reserved=0):
        self.policy = policy
        self.balance = balance
        self.reservation_table_available = reservation_table_available
        self.active_reserved = active_reserved
        self.reservation = None
        self.inserted_reservations = []
        self.released_reservations = []
        self.ledger_entries = []
        self.last_query = ""
        self.last_params = ()

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()
        if "insert into operatorcreditreservations" in self.last_query:
            self.inserted_reservations.append(params or ())
            self.reservation = {
                "id": params[0],
                "business_id": params[1],
                "user_id": params[2],
                "action_key": params[3],
                "status": "reserved",
                "estimated_credits": params[5],
                "reserved_credits": params[6],
                "charged_credits": 0,
                "released_credits": 0,
                "credit_ledger_id": None,
            }
        if "update operatorcreditreservations" in self.last_query and "status = %s" in self.last_query:
            self.released_reservations.append(params or ())
        if "insert into credit_ledger" in self.last_query:
            self.ledger_entries.append(params or ())

    def fetchone(self):
        query = self.last_query
        params = self.last_params
        if "information_schema.columns" in query:
            return {"?column?": 1}
        if "to_regclass" in query:
            table_ref = str(params[0] if params else "")
            if "operatorcreditreservations" in table_ref:
                if self.reservation_table_available:
                    return {"to_regclass": "operatorcreditreservations"}
                return {"to_regclass": None}
            return {"table_ref": "operatorconsentpolicies"}
        if "from operatorconsentpolicies" in query:
            return self.policy
        if "from users" in query:
            return {"credits_balance": self.balance}
        if "from operatorcreditreservations" in query and "sum" in query:
            return {"reserved_credits": self.active_reserved}
        if "from operatorcreditreservations" in query:
            return self.reservation
        if "returning id" in query:
            return {
                "id": (self.reservation or {}).get("id"),
                "status": "reserved",
                "reserved_credits": (self.reservation or {}).get("reserved_credits"),
            }
        return None


def test_execution_attempt_blocks_when_runtime_disabled_after_ready_preflight() -> None:
    cursor = FakeCursor(
        policy={
            "mode": "auto_with_limits",
            "max_credits_per_action": 20,
            "max_credits_per_day": 100,
        },
        balance=100,
    )

    execution = build_paid_action_execution_attempt(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
    )

    assert execution["status"] == "blocked"
    assert execution["execution_status"] == "execution_disabled"
    assert "execution_runtime_disabled" in execution["blocked_reasons"]
    assert execution["preflight"]["status"] == "ready"
    assert execution["adapter_plan"]["adapter_status"] == "planned"
    assert execution["adapter_result"]["adapter_status"] == "dry_run_completed"
    assert execution["reservation_plan"]["status"] == "ready"
    assert execution["reservation_plan"]["reservation_would_be_created"] is True
    assert [stage["stage"] for stage in execution["adapter_result"]["stages"]] == ["estimate", "reserve", "execute", "finalize"]
    assert execution["paid_actions_performed"] is False
    assert execution["credit_reserved"] is False
    assert execution["credit_charged"] is False
    assert execution["external_calls_performed"] is False
    assert execution["external_writes_performed"] is False
    assert execution["parsequeue_jobs_created"] is False
    assert execution["ai_generation_performed"] is False


def test_execution_attempt_keeps_preflight_blockers() -> None:
    cursor = FakeCursor(policy={"mode": "ask_each_time"}, balance=100)

    execution = build_paid_action_execution_attempt(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
    )

    assert execution["status"] == "blocked"
    assert execution["execution_status"] == "preflight_blocked"
    assert "explicit_consent_required" in execution["blocked_reasons"]
    assert "execution_runtime_disabled" not in execution["blocked_reasons"]
    assert execution["adapter_result"]["adapter_status"] == "planned"
    assert execution["paid_actions_performed"] is False


def test_execution_attempt_rejects_unknown_action_without_side_effects() -> None:
    cursor = FakeCursor(policy={"mode": "ask_each_time"}, balance=100)

    execution = build_paid_action_execution_attempt(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="unknown",
        estimated_credits=10,
        explicit_consent=True,
    )

    assert execution["status"] == "blocked"
    assert execution["execution_status"] == "preflight_blocked"
    assert "unknown_action_key" in execution["blocked_reasons"]
    assert execution["adapter_result"]["adapter_status"] == "unsupported_action"
    assert execution["external_calls_performed"] is False


def test_execution_attempt_reserves_and_rolls_back_when_runtime_flag_enabled(monkeypatch) -> None:
    monkeypatch.setattr(services.operator_paid_executor, "EXECUTION_ENABLED", True)
    cursor = FakeCursor(
        policy={
            "mode": "auto_with_limits",
            "max_credits_per_action": 20,
            "max_credits_per_day": 100,
        },
        balance=100,
    )

    execution = build_paid_action_execution_attempt(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
    )

    assert execution["status"] == "blocked"
    assert execution["execution_status"] == "adapter_stub_only"
    assert "adapter_runtime_stub_only" in execution["blocked_reasons"]
    assert execution["reservation_result"]["status"] == "reserved"
    assert execution["reservation_result"]["idempotency_key"] == execution["reservation_plan"]["idempotency_key"]
    assert execution["rollback_result"]["status"] == "released"
    assert execution["credit_reserved"] is True
    assert execution["credit_released"] is True
    assert execution["credit_charged"] is False
    assert execution["external_calls_performed"] is False
    assert execution["parsequeue_jobs_created"] is False
    assert len(cursor.inserted_reservations) == 1
    assert len(cursor.released_reservations) == 1
    assert len(cursor.ledger_entries) == 0


def test_execution_attempt_does_not_reserve_when_runtime_flag_disabled() -> None:
    cursor = FakeCursor(
        policy={
            "mode": "auto_with_limits",
            "max_credits_per_action": 20,
            "max_credits_per_day": 100,
        },
        balance=100,
    )

    execution = build_paid_action_execution_attempt(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
    )

    assert execution["execution_status"] == "execution_disabled"
    assert execution["reservation_result"] is None
    assert execution["rollback_result"] is None
    assert len(cursor.inserted_reservations) == 0
    assert execution["credit_reserved"] is False


def test_execution_attempt_keeps_reservation_blockers_when_runtime_flag_enabled(monkeypatch) -> None:
    monkeypatch.setattr(services.operator_paid_executor, "EXECUTION_ENABLED", True)
    cursor = FakeCursor(
        policy={
            "mode": "auto_with_limits",
            "max_credits_per_action": 20,
            "max_credits_per_day": 100,
        },
        balance=100,
        active_reserved=95,
    )

    execution = build_paid_action_execution_attempt(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
    )

    assert execution["execution_status"] == "reservation_blocked"
    assert "insufficient_unreserved_balance" in execution["blocked_reasons"]
    assert execution["reservation_result"]["status"] == "blocked"
    assert execution["rollback_result"] is None
    assert len(cursor.inserted_reservations) == 0
