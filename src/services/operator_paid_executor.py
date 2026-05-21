from __future__ import annotations

from typing import Any

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
        next_step = "resolve_preflight_blockers"
        execution_status = "preflight_blocked"
    elif not EXECUTION_ENABLED:
        blocked_reasons.append("execution_runtime_disabled")
        next_step = "enable_controlled_execution_runtime"
        execution_status = "execution_disabled"
    else:
        blocked_reasons.append("execution_runtime_not_implemented")
        next_step = "implement_paid_action_adapter"
        execution_status = "execution_disabled"

    status = "blocked"
    return {
        "action_key": action_key,
        "business_id": business_id,
        "status": status,
        "execution_status": execution_status,
        "execution_enabled": EXECUTION_ENABLED,
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
