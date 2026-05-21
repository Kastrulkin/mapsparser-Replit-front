from services.operator_paid_executor import build_paid_action_execution_attempt


class FakeCursor:
    def __init__(self, policy=None, balance=100):
        self.policy = policy
        self.balance = balance
        self.last_query = ""

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())

    def fetchone(self):
        query = self.last_query
        if "information_schema.columns" in query:
            return {"?column?": 1}
        if "to_regclass" in query:
            return {"table_ref": "operatorconsentpolicies"}
        if "from operatorconsentpolicies" in query:
            return self.policy
        if "from users" in query:
            return {"credits_balance": self.balance}
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
    assert execution["external_calls_performed"] is False
