from __future__ import annotations

from typing import Any

from services.operator_paid_action_adapter import build_paid_action_adapter_plan, run_paid_action_adapter_stub
from services.operator_credit_reservation import build_credit_reservation_plan
from services.operator_paid_preflight import EXECUTION_ENABLED, build_paid_action_preflight


def build_paid_action_execution_attempt(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    action_key: str,
    estimated_credits: Any = None,
    explicit_consent: bool = False,
) -> dict[str, Any]:
    reservation_plan = build_credit_reservation_plan(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=action_key,
        estimated_credits=estimated_credits,
    )
    adapter_plan = build_paid_action_adapter_plan(
        action_key=action_key,
        business_id=business_id,
        user_id=user_id,
        estimated_credits=estimated_credits,
        idempotency_key=reservation_plan.get("idempotency_key"),
        reservation_plan=reservation_plan,
    )
    preflight = build_paid_action_preflight(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=action_key,
        estimated_credits=estimated_credits,
        explicit_consent=explicit_consent,
    )

    blocked_reasons = list(preflight.get("blocked_reasons") or [])
    if preflight.get("status") != "ready":
        adapter_result = adapter_plan
        next_step = "resolve_preflight_blockers"
        execution_status = "preflight_blocked"
    elif not EXECUTION_ENABLED:
        adapter_result = run_paid_action_adapter_stub(adapter_plan)
        blocked_reasons.append("execution_runtime_disabled")
        next_step = "enable_controlled_execution_runtime"
        execution_status = "execution_disabled"
    else:
        adapter_result = run_paid_action_adapter_stub(adapter_plan)
        blocked_reasons.append("adapter_runtime_stub_only")
        next_step = "implement_paid_action_adapter"
        execution_status = "adapter_stub_only"

    status = "blocked"
    return {
        "action_key": action_key,
        "business_id": business_id,
        "status": status,
        "execution_status": execution_status,
        "execution_enabled": EXECUTION_ENABLED,
        "adapter_plan": adapter_plan,
        "adapter_result": adapter_result,
        "reservation_plan": reservation_plan,
        "preflight": preflight,
        "blocked_reasons": blocked_reasons,
        "warnings": list(preflight.get("warnings") or []),
        "estimated_credits": preflight.get("estimated_credits"),
        "balance_credits": preflight.get("balance_credits"),
        "paid_actions_performed": False,
        "credit_reserved": False,
        "credit_charged": False,
        "external_calls_performed": False,
        "external_writes_performed": False,
        "parsequeue_jobs_created": False,
        "ai_generation_performed": False,
        "next_step": next_step,
        "copy": {
            "title": "Запуск платного действия заблокирован",
            "summary": "Проверил preflight и runtime-флаг. Платное действие не выполнялось.",
            "blocked": "Execution runtime пока отключён: Apify, генерация, списания и внешние публикации не запускались.",
        },
    }
