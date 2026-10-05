"""Audited grants for payments received outside LocalOS."""

from __future__ import annotations

import json
import uuid
from datetime import date, datetime, time, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from billing_constants import TARIFF_ALIASES, TARIFFS


def create_manual_access_grant(
    cursor: Any,
    *,
    actor_user_id: str,
    target_type: str,
    target_id: str,
    tariff_id: str,
    period_end: str,
    payment_amount_rub: Any,
    payment_reference: str = "",
    request_id: str,
) -> dict[str, Any]:
    clean_actor = _uuid(actor_user_id, "actor_user_id")
    clean_target = str(target_id or "").strip()
    if not clean_target:
        raise ValueError("target_id_required")
    clean_type = str(target_type or "").strip().lower()
    if clean_type not in {"business", "network"}:
        raise ValueError("invalid_target_type")
    clean_request_id = _uuid(request_id, "request_id")
    clean_tariff = TARIFF_ALIASES.get(str(tariff_id or "").strip().lower(), str(tariff_id or "").strip().lower())
    if clean_tariff not in TARIFFS:
        raise ValueError("invalid_tariff")
    requested_end = _period_end(period_end)
    amount = _positive_amount(payment_amount_rub)
    reference = str(payment_reference or "").strip()
    if len(reference) > 500:
        raise ValueError("payment_reference_too_long")
    credits = int(TARIFFS[clean_tariff].get("credits") or 0)
    tier = str(TARIFFS[clean_tariff].get("business_tier") or "").strip()
    if not tier:
        raise ValueError("tariff_tier_missing")

    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"manual-access-grant:{clean_request_id}",))
    cursor.execute(
        """SELECT id, request_id, target_type, target_id, user_id, tariff_id,
                  credit_amount, balance_after, payment_amount_rub
           FROM manual_access_grants WHERE request_id = %s FOR UPDATE""",
        (clean_request_id,),
    )
    existing = _row(cursor, cursor.fetchone())
    if existing:
        if (
            str(existing.get("target_type") or "") != clean_type
            or str(existing.get("target_id") or "") != clean_target
            or str(existing.get("tariff_id") or "") != clean_tariff
            or int(existing.get("credit_amount") or 0) != credits
            or Decimal(str(existing.get("payment_amount_rub") or 0)) != amount
        ):
            raise ValueError("request_id_conflicts_with_existing_grant")
        return {**existing, "status": "already_applied", "applied": False}

    owner_id, business_ids, target_name = _resolve_target(cursor, clean_type, clean_target)
    cursor.execute(
        "SELECT id, COALESCE(credits_balance, 0) AS credits_balance FROM users WHERE id = %s FOR UPDATE",
        (owner_id,),
    )
    owner = _row(cursor, cursor.fetchone())
    if not owner:
        raise ValueError("business_owner_not_found")
    balance_before = int(owner.get("credits_balance") or 0)
    balance_after = balance_before + credits
    grant_id = str(uuid.uuid4())
    started_at = datetime.now(timezone.utc).replace(tzinfo=None)
    ends_at = datetime.combine(requested_end, time(23, 59, 59))

    cursor.execute(
        """UPDATE businesses
           SET subscription_tier = %s, subscription_status = 'active',
               subscription_ends_at = %s, updated_at = CURRENT_TIMESTAMP
           WHERE id = ANY(%s)""",
        (tier, ends_at, business_ids),
    )
    if credits:
        cursor.execute(
            "UPDATE users SET credits_balance = COALESCE(credits_balance, 0) + %s, updated_at = CURRENT_TIMESTAMP WHERE id = %s",
            (credits, owner_id),
        )
        cursor.execute(
            """INSERT INTO credit_ledger
               (id, user_id, subscription_id, delta, reason, period_start, period_end, external_id, created_at)
               VALUES (%s, %s, NULL, %s, 'manual_offline_payment', %s, %s, %s, CURRENT_TIMESTAMP)""",
            (
                str(uuid.uuid4()), owner_id, credits, started_at, ends_at,
                f"manual-access-grant:{clean_request_id}",
            ),
        )
    cursor.execute(
        """INSERT INTO manual_access_grants
           (id, request_id, target_type, target_id, business_ids, user_id, granted_by_user_id,
            tariff_id, tier, credit_amount, balance_before, balance_after,
            payment_amount_rub, currency, payment_reference, period_start, period_end, created_at)
           VALUES (%s, %s, %s, %s, %s::jsonb, %s, %s, %s, %s, %s, %s, %s, %s, 'RUB', %s, %s, %s, CURRENT_TIMESTAMP)""",
        (
            grant_id, clean_request_id, clean_type, clean_target, json.dumps(business_ids),
            owner_id, clean_actor, clean_tariff, tier, credits, balance_before, balance_after,
            amount, reference or None, started_at, ends_at,
        ),
    )
    return {
        "id": grant_id,
        "request_id": clean_request_id,
        "status": "applied",
        "applied": True,
        "target_type": clean_type,
        "target_id": clean_target,
        "target_name": target_name,
        "business_ids": business_ids,
        "user_id": owner_id,
        "tariff_id": clean_tariff,
        "tier": tier,
        "credit_amount": credits,
        "balance_before": balance_before,
        "balance_after": balance_after,
        "payment_amount_rub": float(amount),
        "period_end": ends_at.isoformat(),
    }


def _resolve_target(cursor: Any, target_type: str, target_id: str) -> tuple[str, list[str], str]:
    if target_type == "business":
        cursor.execute(
            """SELECT b.id, b.name, b.owner_id
               FROM businesses b
               WHERE b.id = %s AND COALESCE(b.is_active, TRUE) = TRUE
                 AND b.entity_group = 'client'
               FOR UPDATE OF b""",
            (target_id,),
        )
        row = _row(cursor, cursor.fetchone())
        if not row:
            raise ValueError("client_business_not_found")
        owner_id = str(row.get("owner_id") or "")
        if not owner_id:
            raise ValueError("business_owner_not_found")
        return owner_id, [str(row["id"])], str(row.get("name") or "Бизнес")

    cursor.execute("SELECT id, name, owner_id FROM networks WHERE id = %s FOR UPDATE", (target_id,))
    network = _row(cursor, cursor.fetchone())
    if not network:
        raise ValueError("network_not_found")
    owner_id = str(network.get("owner_id") or "")
    if not owner_id:
        raise ValueError("network_owner_not_found")
    cursor.execute(
        """SELECT id FROM businesses
           WHERE network_id = %s AND COALESCE(is_active, TRUE) = TRUE AND entity_group = 'client'
           ORDER BY id FOR UPDATE""",
        (target_id,),
    )
    business_ids = [str(_row(cursor, value).get("id") or "") for value in cursor.fetchall() or []]
    if not business_ids:
        raise ValueError("network_has_no_client_businesses")
    return owner_id, business_ids, str(network.get("name") or "Сеть")


def _period_end(value: Any) -> date:
    try:
        result = date.fromisoformat(str(value or "").strip())
    except (TypeError, ValueError):
        raise ValueError("invalid_period_end")
    if result < datetime.now(timezone.utc).date():
        raise ValueError("period_end_must_not_be_past")
    return result


def _positive_amount(value: Any) -> Decimal:
    try:
        amount = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        raise ValueError("invalid_payment_amount")
    if not amount.is_finite() or amount <= 0 or amount > Decimal("100000000"):
        raise ValueError("invalid_payment_amount")
    return amount.quantize(Decimal("0.01"))


def _uuid(value: Any, label: str) -> str:
    try:
        return str(uuid.UUID(str(value or "").strip()))
    except (TypeError, ValueError, AttributeError):
        raise ValueError(f"{label}_must_be_uuid")


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "keys"):
        return dict(value)
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    if isinstance(value, (tuple, list)):
        return {columns[index]: value[index] for index in range(min(len(columns), len(value)))}
    return {}
