from __future__ import annotations

import math
from typing import Any

from services.operator_credit_reservation import finalize_reserved_action_credits, reserve_paid_action_credits


AGENT_RUN_ACTION_KEY = "agent_production_run"
AGENT_RUN_ESTIMATED_CREDITS = 2
TOKENS_PER_CREDIT = 1000


def reserve_agent_run_credits(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    run_id: str,
    idempotency_key: str,
    preview: bool,
    estimated_credits: int = AGENT_RUN_ESTIMATED_CREDITS,
) -> dict[str, Any]:
    if preview:
        return {
            "status": "free_preview",
            "estimated_credits": 0,
            "reserved_credits": 0,
            "reservation_id": None,
        }
    return reserve_paid_action_credits(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=AGENT_RUN_ACTION_KEY,
        estimated_credits=max(1, int(estimated_credits or AGENT_RUN_ESTIMATED_CREDITS)),
        idempotency_key=idempotency_key,
        metadata={"run_id": run_id, "source": "agent_run_queue"},
    )


def finalize_agent_run_credits(
    cursor: Any,
    *,
    run: dict[str, Any],
    actual_tokens: int = 0,
) -> dict[str, Any]:
    reservation_id = str(run.get("billing_reservation_id") or "").strip()
    if not reservation_id:
        return {"status": "not_required", "charged_credits": 0, "released_credits": 0}

    status = str(run.get("status") or "")
    if status not in {"completed", "failed", "superseded", "rejected"}:
        return {"status": "pending", "charged_credits": 0, "released_credits": 0}

    reserved = max(1, int(run.get("reserved_credits") or AGENT_RUN_ESTIMATED_CREDITS))
    requested_actual = int(math.ceil(max(0, int(actual_tokens or 0)) / TOKENS_PER_CREDIT))
    actual_credits = min(requested_actual, reserved) if status == "completed" else 0
    result = finalize_reserved_action_credits(
        cursor,
        reservation_id=reservation_id,
        business_id=str(run.get("business_id") or ""),
        user_id=str(run.get("created_by_user_id") or ""),
        actual_credits=actual_credits,
        finalization_mode="charge" if status == "completed" else "release",
        external_id=f"agent-run:{run.get('id')}",
    )
    result["actual_tokens"] = max(0, int(actual_tokens or 0))
    result["actual_credits"] = actual_credits
    result["unbilled_overage"] = max(requested_actual - reserved, 0)
    return result
