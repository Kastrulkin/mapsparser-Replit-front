from __future__ import annotations

import uuid
from typing import Any


PILOT_CREDIT_GRANT_REASON = "compiled_ai_pilot_credit_grant"
PILOT_CREDIT_EXTERNAL_ID_PREFIX = "compiled-ai-pilot:"
MAX_PILOT_CREDIT_GRANT = 24


def grant_compiled_ai_pilot_credits(
    cursor: Any,
    *,
    user_id: str,
    credits: int,
    external_id: str,
    apply: bool = False,
) -> dict[str, Any]:
    clean_user_id = _uuid_text(user_id, "user_id")
    clean_credits = _credit_amount(credits)
    clean_external_id = str(external_id or "").strip()
    if not clean_external_id.startswith(PILOT_CREDIT_EXTERNAL_ID_PREFIX):
        raise ValueError("external_id_must_use_compiled_ai_pilot_prefix")
    if len(clean_external_id) > 160:
        raise ValueError("external_id_too_long")

    cursor.execute(
        "SELECT pg_advisory_xact_lock(hashtext(%s))",
        (f"compiled-ai-pilot-credit:{clean_external_id}",),
    )
    cursor.execute(
        "SELECT credits_balance FROM users WHERE id = %s FOR UPDATE",
        (clean_user_id,),
    )
    user_row = _row_to_dict(cursor, cursor.fetchone())
    if not user_row:
        raise ValueError("user_not_found")
    balance_before = int(user_row.get("credits_balance") or 0)

    cursor.execute(
        """
        SELECT id, user_id, delta, reason, external_id
        FROM credit_ledger
        WHERE external_id = %s
        LIMIT 1
        """,
        (clean_external_id,),
    )
    existing = _row_to_dict(cursor, cursor.fetchone())
    if existing:
        if (
            str(existing.get("user_id") or "") != clean_user_id
            or int(existing.get("delta") or 0) != clean_credits
            or str(existing.get("reason") or "") != PILOT_CREDIT_GRANT_REASON
        ):
            raise ValueError("external_id_conflicts_with_existing_ledger_entry")
        return {
            "status": "already_applied",
            "applied": False,
            "user_id": clean_user_id,
            "credits": clean_credits,
            "balance_before": balance_before,
            "balance_after": balance_before,
            "external_id": clean_external_id,
            "credit_ledger_id": str(existing.get("id") or ""),
        }

    preview = {
        "status": "ready" if not apply else "applied",
        "applied": bool(apply),
        "user_id": clean_user_id,
        "credits": clean_credits,
        "balance_before": balance_before,
        "balance_after": balance_before + clean_credits,
        "external_id": clean_external_id,
        "credit_ledger_id": None,
    }
    if not apply:
        return preview

    ledger_id = str(uuid.uuid4())
    cursor.execute(
        """
        UPDATE users
        SET credits_balance = credits_balance + %s,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (clean_credits, clean_user_id),
    )
    cursor.execute(
        """
        INSERT INTO credit_ledger (
            id, user_id, subscription_id, delta, reason,
            period_start, period_end, external_id, created_at
        )
        VALUES (%s, %s, NULL, %s, %s, NULL, NULL, %s, CURRENT_TIMESTAMP)
        """,
        (
            ledger_id,
            clean_user_id,
            clean_credits,
            PILOT_CREDIT_GRANT_REASON,
            clean_external_id,
        ),
    )
    preview["credit_ledger_id"] = ledger_id
    return preview


def _uuid_text(value: Any, label: str) -> str:
    text = str(value or "").strip()
    try:
        return str(uuid.UUID(text))
    except (TypeError, ValueError, AttributeError):
        raise ValueError(f"{label}_must_be_uuid")


def _credit_amount(value: Any) -> int:
    if isinstance(value, bool):
        raise ValueError("credits_must_be_integer")
    try:
        credits = int(value)
    except (TypeError, ValueError):
        raise ValueError("credits_must_be_integer")
    if credits < 1 or credits > MAX_PILOT_CREDIT_GRANT:
        raise ValueError(f"credits_must_be_between_1_and_{MAX_PILOT_CREDIT_GRANT}")
    return credits


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return row
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    if columns and isinstance(row, (tuple, list)):
        return dict(zip(columns, row))
    return None
