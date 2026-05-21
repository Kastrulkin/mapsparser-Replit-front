from services.operator_paid_preflight import build_paid_action_preflight


class FakeCursor:
    def __init__(self, policy=None, balance=100, usage_table_available=True, used_today=0, used_month=0):
        self.policy = policy
        self.balance = balance
        self.usage_table_available = usage_table_available
        self.used_today = used_today
        self.used_month = used_month
        self.last_query = ""
        self.last_params = ()

    def execute(self, query, params=None):
        self.last_query = " ".join(str(query or "").lower().split())
        self.last_params = params or ()

    def fetchone(self):
        query = self.last_query
        params = self.last_params
        if "information_schema.columns" in query:
            return {"?column?": 1}
        if "to_regclass" in query:
            table_ref = str(params[0] if params else "")
            if "operatorcreditreservations" in table_ref:
                if self.usage_table_available:
                    return {"to_regclass": "operatorcreditreservations"}
                return {"to_regclass": None}
            return {"table_ref": "operatorconsentpolicies"}
        if "from operatorconsentpolicies" in query:
            return self.policy
        if "from users" in query:
            return {"credits_balance": self.balance}
        if "from operatorcreditreservations" in query:
            if "date_trunc('day'" in query:
                return {"used_credits": self.used_today}
            if "date_trunc('month'" in query:
                return {"used_credits": self.used_month}
            return {"used_credits": 0}
        return None


def test_preflight_allows_auto_policy_but_execution_stays_disabled() -> None:
    cursor = FakeCursor(
        policy={
            "mode": "auto_with_limits",
            "max_credits_per_action": 20,
            "max_credits_per_day": 100,
            "max_credits_per_month": 1000,
        },
        balance=100,
    )

    preflight = build_paid_action_preflight(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
    )

    assert preflight["status"] == "ready"
    assert preflight["would_be_allowed"] is True
    assert preflight["can_execute_now"] is False
    assert preflight["execution_enabled"] is False
    assert preflight["paid_actions_performed"] is False
    assert preflight["credit_charged"] is False
    assert preflight["external_calls_performed"] is False
    assert preflight["usage_window"]["used_credits_today"] == 0
    assert preflight["usage_window"]["used_credits_month"] == 0


def test_preflight_requires_estimate() -> None:
    cursor = FakeCursor(policy={"mode": "ask_each_time"}, balance=100)

    preflight = build_paid_action_preflight(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
    )

    assert preflight["status"] == "blocked"
    assert "estimate_required" in preflight["blocked_reasons"]


def test_preflight_allows_paid_action_with_credits_without_extra_consent() -> None:
    cursor = FakeCursor(policy={"mode": "ask_each_time"}, balance=100)

    preflight = build_paid_action_preflight(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="review_replies_generate",
        estimated_credits=10,
    )

    assert preflight["status"] == "ready"
    assert preflight["would_be_allowed"] is True
    assert preflight["requires_explicit_consent"] is False
    assert "explicit_consent_required" not in preflight["blocked_reasons"]


def test_preflight_blocks_disabled_policy() -> None:
    cursor = FakeCursor(policy={"mode": "disabled"}, balance=100)

    preflight = build_paid_action_preflight(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
        explicit_consent=True,
    )

    assert "consent_disabled" in preflight["blocked_reasons"]


def test_preflight_blocks_insufficient_balance() -> None:
    cursor = FakeCursor(policy={"mode": "ask_each_time"}, balance=5)

    preflight = build_paid_action_preflight(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
        explicit_consent=True,
    )

    assert "insufficient_balance" in preflight["blocked_reasons"]
    assert preflight["next_step"] == "top_up_credits"
    assert preflight["billing_url"] == "/dashboard/billing"
    assert preflight["copy"]["billing_url"] == "/dashboard/billing"


def test_preflight_blocks_auto_policy_over_limit() -> None:
    cursor = FakeCursor(
        policy={
            "mode": "auto_with_limits",
            "max_credits_per_action": 5,
            "max_credits_per_day": 100,
        },
        balance=100,
    )

    preflight = build_paid_action_preflight(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
    )

    assert "limit_per_action_exceeded" in preflight["blocked_reasons"]


def test_preflight_blocks_auto_policy_when_daily_usage_window_would_exceed_limit() -> None:
    cursor = FakeCursor(
        policy={
            "mode": "auto_with_limits",
            "max_credits_per_action": 20,
            "max_credits_per_day": 100,
            "max_credits_per_month": 1000,
        },
        balance=200,
        used_today=95,
        used_month=200,
    )

    preflight = build_paid_action_preflight(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
    )

    assert preflight["status"] == "blocked"
    assert "limit_per_day_exceeded" in preflight["blocked_reasons"]
    assert "limit_per_month_exceeded" not in preflight["blocked_reasons"]
    assert preflight["usage_window"]["used_credits_today"] == 95


def test_preflight_blocks_auto_policy_when_month_usage_window_would_exceed_limit() -> None:
    cursor = FakeCursor(
        policy={
            "mode": "auto_with_limits",
            "max_credits_per_action": 20,
            "max_credits_per_day": 100,
            "max_credits_per_month": 205,
        },
        balance=300,
        used_today=10,
        used_month=200,
    )

    preflight = build_paid_action_preflight(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
    )

    assert preflight["status"] == "blocked"
    assert "limit_per_day_exceeded" not in preflight["blocked_reasons"]
    assert "limit_per_month_exceeded" in preflight["blocked_reasons"]
    assert preflight["usage_window"]["used_credits_month"] == 200


def test_preflight_blocks_auto_policy_when_usage_window_is_unavailable() -> None:
    cursor = FakeCursor(
        policy={
            "mode": "auto_with_limits",
            "max_credits_per_action": 20,
            "max_credits_per_day": 100,
            "max_credits_per_month": 1000,
        },
        balance=300,
        usage_table_available=False,
    )

    preflight = build_paid_action_preflight(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="map_reviews_refresh",
        estimated_credits=10,
    )

    assert preflight["status"] == "blocked"
    assert "usage_window_unavailable" in preflight["blocked_reasons"]


def test_preflight_rejects_unknown_action() -> None:
    cursor = FakeCursor(policy={"mode": "ask_each_time"}, balance=100)

    preflight = build_paid_action_preflight(
        cursor,
        business_id="biz-1",
        user_id="user-1",
        action_key="unknown",
        estimated_credits=10,
    )

    assert preflight["status"] == "blocked"
    assert "unknown_action_key" in preflight["blocked_reasons"]
