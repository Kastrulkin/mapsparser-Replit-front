from __future__ import annotations

import hashlib
from typing import Any

from services.operator_credit_reservation import finalize_reserved_action_credits, reserve_paid_action_credits
from services.operator_paid_preflight import BILLING_URL, build_paid_action_preflight
from services.operator_tool_loop import run_operator_tool_loop


OPERATOR_TOOL_PLAN_ACTION_KEY = "operator_tool_plan"
OPERATOR_TOOL_PLAN_CREDITS = 1


def _is_technical_planner_failure(result: dict[str, Any]) -> bool:
    if bool(result.get("planner_failed")):
        return True
    if str(result.get("status") or "").strip().lower() != "blocked":
        return False
    reasons = {
        str(reason or "").strip().lower()
        for reason in result.get("blocked_reasons") or []
        if str(reason or "").strip()
    }
    exact_reasons = {
        "operator_planner_failed",
        "provider_timeout",
        "provider_unavailable",
        "provider_error",
        "empty_response",
        "invalid_response",
        "invalid_json",
        "schema_invalid",
    }
    technical_suffixes = (
        "_empty_response",
        "_request_failed",
        "_invalid_response",
        "_invalid_json",
        "_schema_invalid",
    )
    return any(reason in exact_reasons or reason.endswith(technical_suffixes) for reason in reasons)


def _idempotency_key(*, business_id: str, user_id: str, conversation_id: str, message: str) -> str:
    source = f"{business_id}|{user_id}|{conversation_id}|{str(message or '').strip().lower()}"
    return "operator-tool:" + hashlib.sha256(source.encode("utf-8")).hexdigest()


def run_paid_operator_tool_loop(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    message: str,
    tools: list[dict[str, Any]],
    conversation_id: str = "",
    conversation_history: Any = None,
    actor_context: Any = None,
    pending_approvals: Any = None,
) -> dict[str, Any]:
    preflight = build_paid_action_preflight(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=OPERATOR_TOOL_PLAN_ACTION_KEY,
        estimated_credits=OPERATOR_TOOL_PLAN_CREDITS,
    )
    if preflight.get("status") != "ready":
        blocked_reasons = list(preflight.get("blocked_reasons") or [])
        insufficient = "insufficient_balance" in blocked_reasons or "insufficient_unreserved_balance" in blocked_reasons
        return {
            "status": "blocked",
            "intent": "operator_tool_loop",
            "capability": "operator.help",
            "chat_response": (
                "Не хватает кредитов для разбора свободной команды. Пополните счёт или сформулируйте одну из доступных команд точнее."
                if insufficient
                else "Безопасный планировщик Оператора сейчас недоступен."
            ),
            "blocked_reasons": blocked_reasons,
            "preflight": preflight,
            "billing_url": BILLING_URL if insufficient else "",
            "ui_actions": ([{"action": "open_billing", "label": "Пополнить счёт", "href": BILLING_URL, "payload": {}}] if insufficient else []),
            "charged_credits": 0,
            "credit_charged": False,
            "paid_actions_performed": False,
            "external_writes_performed": False,
        }

    idempotency_key = _idempotency_key(
        business_id=business_id,
        user_id=user_id,
        conversation_id=conversation_id,
        message=message,
    )
    reservation = reserve_paid_action_credits(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=OPERATOR_TOOL_PLAN_ACTION_KEY,
        estimated_credits=OPERATOR_TOOL_PLAN_CREDITS,
        idempotency_key=idempotency_key,
        metadata={"source": "operator_tool_loop", "conversation_id": conversation_id},
    )
    if reservation.get("status") != "reserved":
        return {
            "status": "blocked",
            "intent": "operator_tool_loop",
            "capability": "operator.help",
            "chat_response": "Не удалось зарезервировать кредиты для планировщика Оператора.",
            "blocked_reasons": list(reservation.get("blocked_reasons") or ["operator_tool_reservation_failed"]),
            "preflight": preflight,
            "reservation_result": reservation,
            "charged_credits": 0,
            "credit_charged": False,
            "paid_actions_performed": False,
            "external_writes_performed": False,
        }

    try:
        result = run_operator_tool_loop(
            business_id=business_id,
            user_id=user_id,
            message=message,
            conversation_id=conversation_id,
            conversation_history=conversation_history,
            actor_context=actor_context,
            pending_approvals=pending_approvals,
            tools=tools,
        )
    except Exception:
        release = finalize_reserved_action_credits(
            cursor,
            reservation_id=str(reservation.get("reservation_id") or ""),
            business_id=business_id,
            user_id=user_id,
            finalization_mode="release",
            external_id=idempotency_key,
        )
        return {
            "status": "blocked",
            "intent": "operator_tool_loop",
            "capability": "operator.help",
            "chat_response": "Оператор не смог завершить безопасный план. Кредиты за планирование не списаны.",
            "blocked_reasons": ["operator_tool_loop_failed"],
            "preflight": preflight,
            "reservation_result": reservation,
            "tool_plan_finalization_result": release,
            "charged_credits": 0,
            "credit_charged": False,
            "paid_actions_performed": False,
            "external_writes_performed": False,
        }
    planner_failed = _is_technical_planner_failure(result)
    finalization = finalize_reserved_action_credits(
        cursor,
        reservation_id=str(reservation.get("reservation_id") or ""),
        business_id=business_id,
        user_id=user_id,
        actual_credits=None if planner_failed else OPERATOR_TOOL_PLAN_CREDITS,
        finalization_mode="release" if planner_failed else "charge",
        external_id=idempotency_key,
    )
    charged = int(finalization.get("charge_credits") or 0)
    domain_charged = int(result.get("charged_credits") or 0)
    result["preflight"] = preflight
    result["reservation_result"] = reservation
    result["tool_plan_finalization_result"] = finalization
    result["tool_plan_charged_credits"] = charged
    result["charged_credits"] = domain_charged + charged
    result["credit_charged"] = bool(result.get("credit_charged")) or finalization.get("status") == "charged"
    result["paid_actions_performed"] = bool(result.get("paid_actions_performed")) or bool(charged)
    return result
