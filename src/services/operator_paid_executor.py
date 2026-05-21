from __future__ import annotations

from typing import Any

from services.operator_paid_action_adapter import (
    build_paid_action_adapter_plan,
    run_paid_action_adapter_stub,
    run_paid_action_internal_fake,
)
from services.operator_credit_reservation import build_credit_reservation_plan, finalize_reserved_action_credits, reserve_paid_action_credits
from services.operator_paid_preflight import EXECUTION_ENABLED, build_paid_action_preflight


INTERNAL_FAKE_ACTUAL_CREDITS = 1


def _internal_fake_actual_credits(estimated_credits: Any) -> int:
    try:
        estimate = int(estimated_credits or 0)
    except Exception:
        return INTERNAL_FAKE_ACTUAL_CREDITS
    if estimate <= 0:
        return INTERNAL_FAKE_ACTUAL_CREDITS
    return min(INTERNAL_FAKE_ACTUAL_CREDITS, estimate)


def build_paid_action_execution_attempt(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    action_key: str,
    estimated_credits: Any = None,
    explicit_consent: bool = False,
) -> dict[str, Any]:
    reservation_result: dict[str, Any] | None = None
    finalization_result: dict[str, Any] | None = None
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
        reservation_result = reserve_paid_action_credits(
            cursor,
            business_id=business_id,
            user_id=user_id,
            action_key=action_key,
            estimated_credits=estimated_credits,
            idempotency_key=str(reservation_plan.get("idempotency_key") or ""),
            metadata={
                "source": "operator_paid_executor",
                "runtime_mode": "internal_stub",
                "execution_enabled": True,
            },
        )
        if reservation_result.get("status") != "reserved":
            adapter_result = adapter_plan
            blocked_reasons.extend(list(reservation_result.get("blocked_reasons") or []))
            next_step = "resolve_reservation_blockers"
            execution_status = "reservation_blocked"
        else:
            actual_credits = _internal_fake_actual_credits(estimated_credits)
            adapter_result = run_paid_action_internal_fake(adapter_plan, actual_credits=actual_credits)
            finalization_result = finalize_reserved_action_credits(
                cursor,
                reservation_id=str(reservation_result.get("reservation_id") or ""),
                business_id=business_id,
                user_id=user_id,
                actual_credits=actual_credits,
                finalization_mode="charge",
                external_id=str(reservation_result.get("idempotency_key") or reservation_result.get("reservation_id") or ""),
            )
            if finalization_result.get("status") not in {"charged", "released", "already_finalized"}:
                blocked_reasons.extend(list(finalization_result.get("blocked_reasons") or []))
                blocked_reasons.append("internal_fake_finalization_failed")
                next_step = "resolve_credit_finalization_blockers"
                execution_status = "internal_fake_finalization_blocked"
            else:
                blocked_reasons.append("internal_fake_execution_only")
                next_step = "replace_internal_fake_with_real_adapter"
                execution_status = "internal_fake_completed"

    reservation_side_effects = dict((reservation_result or {}).get("side_effects") or {})
    finalization_side_effects = dict((finalization_result or {}).get("side_effects") or {})
    adapter_side_effects = dict((adapter_result or {}).get("side_effects") or {})

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
        "reservation_result": reservation_result,
        "finalization_result": finalization_result,
        "rollback_result": finalization_result,
        "preflight": preflight,
        "blocked_reasons": blocked_reasons,
        "warnings": list(preflight.get("warnings") or []),
        "estimated_credits": preflight.get("estimated_credits"),
        "balance_credits": preflight.get("balance_credits"),
        "paid_actions_performed": False,
        "credit_reserved": bool(reservation_side_effects.get("credit_reserved")),
        "credit_charged": bool(finalization_side_effects.get("credit_charged")),
        "credit_released": bool(finalization_side_effects.get("credit_released")),
        "external_calls_performed": False,
        "external_writes_performed": False,
        "parsequeue_jobs_created": False,
        "ai_generation_performed": False,
        "internal_fake_execution_performed": bool(adapter_side_effects.get("internal_fake_execution_performed")),
        "next_step": next_step,
        "copy": {
            "title": "Запуск платного действия заблокирован",
            "summary": "Проверил preflight, runtime-флаг, reserve и внутренний adapter boundary.",
            "blocked": "Execution runtime по умолчанию отключён: Apify, генерация и внешние публикации не запускались.",
        },
    }
