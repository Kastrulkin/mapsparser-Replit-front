from __future__ import annotations

import hashlib
import uuid
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


def _stable_id(*parts: Any) -> str:
    raw = "|".join(str(part or "").strip() for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def build_agent_creation_cost_preview() -> dict[str, Any]:
    return {
        "action_key": AGENT_CREATION_ACTION_KEY,
        "task_type": AGENT_CREATION_TASK_TYPE,
        "label": "Создание агента",
        "estimated_credits": AGENT_CREATION_ESTIMATED_CREDITS,
        "actual_credits": AGENT_CREATION_ACTUAL_CREDITS,
        "cost_source": "model_tokens",
        "billing_url": BILLING_URL,
        "copy": "Оценка: примерно 3 кредита за компиляцию агента.",
    }


def _row_value(row: Any, key: str, index: int = 0) -> Any:
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    if isinstance(row, (list, tuple)) and len(row) > index:
        return row[index]
    return None


def _record_agent_creation_token_estimate(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    source_id: str,
) -> str | None:
    cursor.execute("SELECT to_regclass('public.tokenusage')")
    reg = _row_value(cursor.fetchone(), "to_regclass")
    if not reg:
        return None

    usage_id = str(uuid.uuid4())
    total_tokens = AGENT_CREATION_ACTUAL_CREDITS * TOKENS_PER_CREDIT
    prompt_tokens = int(total_tokens * 0.7)
    completion_tokens = total_tokens - prompt_tokens
    cursor.execute(
        """
        INSERT INTO TokenUsage
        (id, business_id, user_id, task_type, model, prompt_tokens, completion_tokens, total_tokens, endpoint)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """,
        (
            usage_id,
            business_id,
            user_id,
            AGENT_CREATION_TASK_TYPE,
            "agent_compiler_estimate",
            prompt_tokens,
            completion_tokens,
            total_tokens,
            f"agent_creation:{source_id}",
        ),
    )
    return usage_id


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
    token_usage_id = None
    if finalization.get("status") == "charged":
        token_usage_id = _record_agent_creation_token_estimate(
            cursor,
            business_id=business_id,
            user_id=user_id,
            source_id=source_id,
        )
    return {
        **finalization,
        "task_type": AGENT_CREATION_TASK_TYPE,
        "action_key": AGENT_CREATION_ACTION_KEY,
        "idempotency_key": idempotency_key,
        "estimated_credits": AGENT_CREATION_ESTIMATED_CREDITS,
        "actual_credits": AGENT_CREATION_ACTUAL_CREDITS,
        "token_usage_id": token_usage_id,
        "billing_url": BILLING_URL,
    }
