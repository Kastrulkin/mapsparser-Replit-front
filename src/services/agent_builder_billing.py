from __future__ import annotations

import hashlib
from typing import Any

from services.operator_credit_reservation import finalize_reserved_action_credits, reserve_paid_action_credits
from services.operator_paid_preflight import BILLING_URL, build_paid_action_preflight


AGENT_CREATION_ACTION_KEY = "agent_creation"
AGENT_CREATION_TASK_TYPE = "agent_creation"
AGENT_CREATION_ESTIMATED_CREDITS = 3
AGENT_CREATION_ACTUAL_CREDITS = 3
TOKENS_PER_CREDIT = 1000

OPERATOR_CHAT_USAGE_CATEGORY = "operator_chat"
OPERATOR_CHAT_ESTIMATED_CREDITS = 1
AGENT_PREVIEW_RUN_ESTIMATED_TOKENS = 500
AGENT_PRODUCTION_RUN_ESTIMATED_TOKENS = 2000
AGENT_EXTERNAL_ACTION_ESTIMATED_TOKENS = 2000


def _stable_id(*parts: Any) -> str:
    raw = "|".join(str(part or "").strip() for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def build_agent_creation_cost_preview() -> dict[str, Any]:
    items = build_agent_billing_estimate_items()
    return {
        "action_key": AGENT_CREATION_ACTION_KEY,
        "task_type": AGENT_CREATION_TASK_TYPE,
        "label": "Создание агента",
        "estimated_credits": AGENT_CREATION_ESTIMATED_CREDITS,
        "actual_credits": AGENT_CREATION_ACTUAL_CREDITS,
        "cost_source": "model_tokens",
        "billing_url": BILLING_URL,
        "copy": "Оценка: примерно 3 кредита за компиляцию агента.",
        "schema": "localos_agent_billing_estimate_v1",
        "items": items,
        "total_estimated_credits": sum(int(item.get("estimated_credits") or 0) for item in items),
        "total_estimated_tokens": sum(int(item.get("estimated_tokens") or 0) for item in items),
    }


def build_agent_billing_estimate_items() -> list[dict[str, Any]]:
    return [
        {
            "key": "agent_creation",
            "label": "Создание агента",
            "phase": "compile",
            "estimated_credits": AGENT_CREATION_ESTIMATED_CREDITS,
            "estimated_tokens": AGENT_CREATION_ESTIMATED_CREDITS * TOKENS_PER_CREDIT,
            "billing_mode": "reserve_then_charge",
        },
        {
            "key": "preview_run",
            "label": "Preview run",
            "phase": "preview",
            "estimated_credits": 0,
            "estimated_tokens": AGENT_PREVIEW_RUN_ESTIMATED_TOKENS,
            "billing_mode": "meter_after_run",
        },
        {
            "key": "production_run",
            "label": "Production run",
            "phase": "run",
            "estimated_credits": 0,
            "estimated_tokens": AGENT_PRODUCTION_RUN_ESTIMATED_TOKENS,
            "billing_mode": "meter_after_run",
        },
        {
            "key": "external_action",
            "label": "Внешнее действие",
            "phase": "external_action",
            "estimated_credits": 0,
            "estimated_tokens": AGENT_EXTERNAL_ACTION_ESTIMATED_TOKENS,
            "billing_mode": "action_orchestrator_reserve_settle",
        },
        {
            "key": "operator_chat",
            "label": "Чат оператора",
            "phase": "operator_chat",
            "estimated_credits": OPERATOR_CHAT_ESTIMATED_CREDITS,
            "estimated_tokens": OPERATOR_CHAT_ESTIMATED_CREDITS * TOKENS_PER_CREDIT,
            "billing_mode": "reserve_then_charge",
        },
    ]


def charge_agent_creation_credits(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    source_id: str,
    description: str,
    channel: str = "agent_builder",
) -> dict[str, Any]:
    idempotency_key = _stable_id(
        AGENT_CREATION_ACTION_KEY,
        business_id,
        user_id,
        source_id,
        description,
    )
    preflight = build_paid_action_preflight(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=AGENT_CREATION_ACTION_KEY,
        estimated_credits=AGENT_CREATION_ESTIMATED_CREDITS,
    )
    if preflight.get("status") != "ready":
        return {
            **preflight,
            "status": "blocked",
            "idempotency_key": idempotency_key,
            "task_type": AGENT_CREATION_TASK_TYPE,
            "estimated_credits": AGENT_CREATION_ESTIMATED_CREDITS,
            "actual_credits": AGENT_CREATION_ACTUAL_CREDITS,
            "billing_url": BILLING_URL,
        }

    reservation = reserve_paid_action_credits(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=AGENT_CREATION_ACTION_KEY,
        estimated_credits=AGENT_CREATION_ESTIMATED_CREDITS,
        idempotency_key=idempotency_key,
        metadata={
            "task_type": AGENT_CREATION_TASK_TYPE,
            "source": channel,
            "source_id": source_id,
            "description_preview": str(description or "").strip()[:240],
        },
    )
    if reservation.get("status") != "reserved":
        return {
            **reservation,
            "status": "blocked",
            "task_type": AGENT_CREATION_TASK_TYPE,
            "billing_url": BILLING_URL,
        }

    finalization = finalize_reserved_action_credits(
        cursor,
        reservation_id=str(reservation.get("reservation_id") or ""),
        business_id=business_id,
        user_id=user_id,
        actual_credits=AGENT_CREATION_ACTUAL_CREDITS,
        finalization_mode="charge",
        external_id=idempotency_key,
    )
    return {
        **finalization,
        "task_type": AGENT_CREATION_TASK_TYPE,
        "action_key": AGENT_CREATION_ACTION_KEY,
        "idempotency_key": idempotency_key,
        "estimated_credits": AGENT_CREATION_ESTIMATED_CREDITS,
        "actual_credits": AGENT_CREATION_ACTUAL_CREDITS,
        "token_usage_id": None,
        "usage_record_mode": "provider_actual",
        "billing_url": BILLING_URL,
    }
