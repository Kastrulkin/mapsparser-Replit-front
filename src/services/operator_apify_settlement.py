from __future__ import annotations

import uuid
import json
from decimal import Decimal, InvalidOperation, ROUND_CEILING
from typing import Any

from services.operator_credit_reservation import finalize_reserved_action_credits
from services.operator_manual_review import _clean_text
from services.operator_news_generation import _row_to_dict
from services.operator_paid_actions import APIFY_CREDIT_MULTIPLIER


APIFY_SETTLEMENT_ACTION_KEY = "map_reviews_refresh"


def provider_actual_cost_to_credits(provider_actual_cost: Any) -> int | None:
    try:
        cost = Decimal(str(provider_actual_cost))
    except (InvalidOperation, ValueError):
        return None
    if cost < 0:
        return None
    credits = (cost * Decimal(APIFY_CREDIT_MULTIPLIER)).to_integral_value(rounding=ROUND_CEILING)
    return int(credits)


def _load_reservation(cursor: Any, *, reservation_id: str, business_id: str, user_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT id, business_id, user_id, action_key, status,
               reserved_credits, charged_credits, released_credits
        FROM operatorcreditreservations
        WHERE id = %s
          AND business_id = %s
          AND user_id = %s
        LIMIT 1
        """,
        (reservation_id, business_id, user_id),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _int_field(row: dict[str, Any], key: str) -> int:
    try:
        return int(row.get(key) or 0)
    except Exception:
        return 0


def _ledger_external_exists(cursor: Any, external_id: str) -> bool:
    cursor.execute("SELECT id FROM credit_ledger WHERE external_id = %s LIMIT 1", (external_id,))
    return bool(cursor.fetchone())


def _charge_extra_credits(
    cursor: Any,
    *,
    user_id: str,
    credits: int,
    external_id: str,
) -> dict[str, Any]:
    if credits <= 0:
        return {"status": "nothing_to_charge", "charge_credits": 0, "credit_ledger_id": None}
    if _ledger_external_exists(cursor, external_id):
        return {"status": "already_charged", "charge_credits": 0, "credit_ledger_id": None}
    cursor.execute("SELECT credits_balance FROM users WHERE id = %s LIMIT 1", (user_id,))
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    try:
        balance = int(row.get("credits_balance") or 0)
    except Exception:
        return {"status": "blocked", "charge_credits": 0, "blocked_reasons": ["balance_unavailable"]}
    if balance < credits:
        return {"status": "blocked", "charge_credits": 0, "blocked_reasons": ["insufficient_balance_at_settlement"], "balance_credits": balance}
    ledger_id = str(uuid.uuid4())
    cursor.execute(
        """
        UPDATE users
        SET credits_balance = credits_balance - %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (credits, user_id),
    )
    cursor.execute(
        """
        INSERT INTO credit_ledger (
            id, user_id, subscription_id, delta, reason, period_start, period_end, external_id, created_at
        )
        VALUES (%s, %s, NULL, %s, %s, NULL, NULL, %s, CURRENT_TIMESTAMP)
        """,
        (
            ledger_id,
            user_id,
            -credits,
            "operator_paid_action_actual_cost_overage",
            external_id,
        ),
    )
    return {"status": "charged", "charge_credits": credits, "credit_ledger_id": ledger_id}


def _store_settlement_metadata(
    cursor: Any,
    *,
    reservation_id: str,
    provider_actual_cost: Any,
    actual_credits: int,
    overage_credits: int,
    provider_run_id: str,
    settlement_status: str,
) -> None:
    metadata = {
        "provider": "apify",
        "provider_actual_cost": str(provider_actual_cost),
        "credit_multiplier": APIFY_CREDIT_MULTIPLIER,
        "actual_credits": actual_credits,
        "overage_credits": overage_credits,
        "provider_run_id": _clean_text(provider_run_id),
        "settlement_status": settlement_status,
    }
    cursor.execute(
        """
        UPDATE operatorcreditreservations
        SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (json.dumps(metadata, ensure_ascii=False), reservation_id),
    )


def settle_apify_actual_cost(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    reservation_id: str,
    provider_actual_cost: Any,
    provider_run_id: str = "",
    action_key: str = APIFY_SETTLEMENT_ACTION_KEY,
) -> dict[str, Any]:
    actual_credits = provider_actual_cost_to_credits(provider_actual_cost)
    if actual_credits is None:
        return {
            "status": "blocked",
            "action_key": action_key,
            "provider": "apify",
            "provider_actual_cost": provider_actual_cost,
            "actual_credits": None,
            "blocked_reasons": ["invalid_provider_actual_cost"],
        }

    reservation = _load_reservation(cursor, reservation_id=reservation_id, business_id=business_id, user_id=user_id)
    if not reservation:
        return {
            "status": "blocked",
            "action_key": action_key,
            "provider": "apify",
            "provider_actual_cost": provider_actual_cost,
            "actual_credits": actual_credits,
            "blocked_reasons": ["reservation_not_found"],
        }
    if _clean_text(reservation.get("action_key")) != action_key:
        return {
            "status": "blocked",
            "action_key": action_key,
            "provider": "apify",
            "provider_actual_cost": provider_actual_cost,
            "actual_credits": actual_credits,
            "blocked_reasons": ["reservation_action_mismatch"],
        }

    reserved = _int_field(reservation, "reserved_credits")
    charged = _int_field(reservation, "charged_credits")
    released = _int_field(reservation, "released_credits")
    outstanding = max(reserved - charged - released, 0)
    charge_inside_reservation = min(actual_credits, outstanding)
    overage_credits = max(actual_credits - outstanding, 0)
    external_base = _clean_text(provider_run_id) or reservation_id

    if actual_credits == 0:
        finalization = finalize_reserved_action_credits(
            cursor,
            reservation_id=reservation_id,
            business_id=business_id,
            user_id=user_id,
            finalization_mode="release",
            external_id=f"apify:{external_base}",
        )
        _store_settlement_metadata(
            cursor,
            reservation_id=reservation_id,
            provider_actual_cost=provider_actual_cost,
            actual_credits=actual_credits,
            overage_credits=0,
            provider_run_id=provider_run_id or external_base,
            settlement_status="released",
        )
        return {
            "status": "released",
            "action_key": action_key,
            "provider": "apify",
            "provider_actual_cost": provider_actual_cost,
            "actual_credits": actual_credits,
            "reserved_credits": reserved,
            "finalization_result": finalization,
            "charged_credits": 0,
            "overage_credits": 0,
            "credit_charged": False,
        }

    finalization = finalize_reserved_action_credits(
        cursor,
        reservation_id=reservation_id,
        business_id=business_id,
        user_id=user_id,
        actual_credits=charge_inside_reservation,
        finalization_mode="charge",
        external_id=f"apify:{external_base}",
    )
    if finalization.get("status") not in {"charged", "already_finalized"}:
        return {
            "status": "blocked",
            "action_key": action_key,
            "provider": "apify",
            "provider_actual_cost": provider_actual_cost,
            "actual_credits": actual_credits,
            "reserved_credits": reserved,
            "finalization_result": finalization,
            "blocked_reasons": list(finalization.get("blocked_reasons") or ["finalization_failed"]),
        }

    overage = _charge_extra_credits(
        cursor,
        user_id=user_id,
        credits=overage_credits,
        external_id=f"apify:{external_base}:overage",
    )
    if overage.get("status") == "blocked":
        return {
            "status": "blocked",
            "action_key": action_key,
            "provider": "apify",
            "provider_actual_cost": provider_actual_cost,
            "actual_credits": actual_credits,
            "reserved_credits": reserved,
            "finalization_result": finalization,
            "overage_result": overage,
            "blocked_reasons": list(overage.get("blocked_reasons") or ["overage_charge_failed"]),
        }

    charged_total = int(finalization.get("charge_credits") or 0) + int(overage.get("charge_credits") or 0)
    _store_settlement_metadata(
        cursor,
        reservation_id=reservation_id,
        provider_actual_cost=provider_actual_cost,
        actual_credits=actual_credits,
        overage_credits=overage_credits,
        provider_run_id=provider_run_id or external_base,
        settlement_status="charged",
    )
    return {
        "status": "charged",
        "action_key": action_key,
        "provider": "apify",
        "provider_actual_cost": str(provider_actual_cost),
        "credit_multiplier": APIFY_CREDIT_MULTIPLIER,
        "actual_credits": actual_credits,
        "reserved_credits": reserved,
        "charged_credits": charged_total,
        "overage_credits": overage_credits,
        "finalization_result": finalization,
        "overage_result": overage,
        "credit_charged": charged_total > 0,
        "external_writes_performed": False,
    }
