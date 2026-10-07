"""Shared-account credit billing for bounded company discovery."""
from __future__ import annotations

from decimal import Decimal, ROUND_CEILING
from typing import Any

from services.operator_paid_actions import APIFY_CREDIT_MULTIPLIER

SEARCH_ACTION = "outreach_company_search"
CHECK_ACTION = "outreach_company_check"
CHECK_CREDITS = 1


def search_credits_per_call(config: dict[str, Any]) -> int:
    provider_cap = provider_call_cap_usd(config)
    return max(1, int((provider_cap * APIFY_CREDIT_MULTIPLIER).to_integral_value(rounding=ROUND_CEILING)))


def provider_call_cap_usd(config: dict[str, Any]) -> Decimal:
    if config.get("billing_mode") == "shared_balance_actual":
        return Decimal(config["search_call_cap_cents"]) / Decimal(100)
    return Decimal(config["search_budget_cents"]) / Decimal(100 * config["max_search_calls"])


def actual_search_credits(usage_total_usd: Any, reserved_credits: int) -> int:
    """Settle only a provider-reported amount; never exceed the held credits."""
    amount = Decimal(str(usage_total_usd))
    if not amount.is_finite() or amount < 0:
        raise ValueError("invalid_provider_search_cost")
    credits = int((amount * APIFY_CREDIT_MULTIPLIER).to_integral_value(rounding=ROUND_CEILING))
    if credits > reserved_credits:
        raise ValueError("provider_search_cost_exceeds_reservation")
    return credits


def credit_quote(config: dict[str, Any]) -> dict[str, int]:
    calls = int(config["max_search_calls"])
    checks = int(config["max_qualification_calls"])
    search_each = search_credits_per_call(config)
    return {"search_each": search_each, "search_max": calls * search_each,
            "check_each": CHECK_CREDITS, "check_max": checks * CHECK_CREDITS,
            "total_max": calls * search_each + checks * CHECK_CREDITS}


def reserve_step(cursor: Any, row: dict[str, Any], *, step: str, key: str, credits: int) -> dict[str, Any]:
    from services.operator_credit_reservation import reserve_paid_action_credits
    action = SEARCH_ACTION if step == "search" else CHECK_ACTION
    return reserve_paid_action_credits(cursor, business_id=str(row["business_id"]),
        user_id=str(row["user_id"]), action_key=action, estimated_credits=credits,
        idempotency_key=f"outreach:{row['id']}:{step}:{key}",
        metadata={"task_id": str(row["id"]), "step": step, "step_key": key})


def charge_step(cursor: Any, row: dict[str, Any], *, reservation_id: str, credits: int, step: str, key: str) -> dict[str, Any]:
    from services.operator_credit_reservation import finalize_reserved_action_credits
    return finalize_reserved_action_credits(cursor, reservation_id=reservation_id,
        business_id=str(row["business_id"]), user_id=str(row["user_id"]),
        actual_credits=credits, external_id=f"outreach:{row['id']}:{step}:{key}")
