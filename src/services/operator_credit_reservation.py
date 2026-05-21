from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any


ACTIVE_RESERVATION_STATUSES = ("reserved",)


def _stable_id(*parts: Any) -> str:
    raw = "|".join(str(part or "").strip() for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _positive_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except Exception:
        return None
    if parsed <= 0:
        return None
    return parsed


def _nonnegative_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except Exception:
        return None
    if parsed < 0:
        return None
    return parsed


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
    if hasattr(row, "keys"):
        try:
            return dict(row)
        except Exception:
            pass
    description = getattr(cursor, "description", None) or []
    columns = [col[0] for col in description]
    if isinstance(row, (list, tuple)) and columns:
        return {columns[idx]: row[idx] for idx in range(min(len(columns), len(row)))}
    return None


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
    row = cursor.fetchone()
    if row is None:
        return False
    if isinstance(row, dict):
        value = row.get("to_regclass") or row.get("table_ref") or row.get("?column?")
        return bool(value)
    if isinstance(row, (list, tuple)) and row:
        return bool(row[0])
    return bool(row)


def _table_has_column(cursor: Any, table_name: str, column_name: str) -> bool:
    cursor.execute(
        """
        SELECT 1
        FROM information_schema.columns
        WHERE table_schema = 'public'
          AND table_name = %s
          AND column_name = %s
        LIMIT 1
        """,
        (table_name, column_name),
    )
    return bool(cursor.fetchone())


def _load_user_balance(cursor: Any, user_id: str) -> int | None:
    if not user_id:
        return None
    if not _table_has_column(cursor, "users", "credits_balance"):
        return None
    cursor.execute("SELECT credits_balance FROM users WHERE id = %s LIMIT 1", (user_id,))
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    try:
        return int(row.get("credits_balance") or 0)
    except Exception:
        return None


def _load_active_reserved_credits(cursor: Any, *, business_id: str, user_id: str) -> int | None:
    if not _table_exists(cursor, "operatorcreditreservations"):
        return None
    cursor.execute(
        """
        SELECT COALESCE(SUM(reserved_credits - charged_credits - released_credits), 0) reserved_credits
        FROM operatorcreditreservations
        WHERE business_id = %s
          AND user_id = %s
          AND status IN ('reserved')
        """,
        (business_id, user_id),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    try:
        return max(int(row.get("reserved_credits") or 0), 0)
    except Exception:
        return None


def _load_reservation(cursor: Any, *, reservation_id: str, business_id: str, user_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT
            id,
            business_id,
            user_id,
            action_key,
            status,
            estimated_credits,
            reserved_credits,
            charged_credits,
            released_credits,
            credit_ledger_id
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


def _reservation_summary(row: dict[str, Any]) -> dict[str, Any]:
    reserved = _int_field(row, "reserved_credits")
    charged = _int_field(row, "charged_credits")
    released = _int_field(row, "released_credits")
    outstanding = max(reserved - charged - released, 0)
    return {
        "reservation_id": row.get("id"),
        "business_id": row.get("business_id"),
        "user_id": row.get("user_id"),
        "action_key": row.get("action_key"),
        "status": row.get("status"),
        "reserved_credits": reserved,
        "charged_credits": charged,
        "released_credits": released,
        "outstanding_credits": outstanding,
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
    }


def build_credit_reservation_plan(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    action_key: str,
    estimated_credits: Any = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    requested = _positive_int(estimated_credits)
    clean_idempotency_key = str(idempotency_key or "").strip() or _stable_id(
        "operator_credit_reservation",
        action_key,
        business_id,
        user_id,
        requested,
    )
    blocked: list[str] = []
    warnings: list[str] = []

    table_available = _table_exists(cursor, "operatorcreditreservations")
    balance = _load_user_balance(cursor, user_id)
    active_reserved = _load_active_reserved_credits(cursor, business_id=business_id, user_id=user_id) if table_available else None

    if requested is None:
        blocked.append("estimate_required")
    if not table_available:
        blocked.append("reservation_ledger_unavailable")
    if balance is None:
        blocked.append("balance_unavailable")
    if active_reserved is None and table_available:
        blocked.append("active_reservations_unavailable")

    available_after_reservations = None
    if balance is not None and active_reserved is not None:
        available_after_reservations = max(balance - active_reserved, 0)
        if requested is not None and available_after_reservations < requested:
            blocked.append("insufficient_unreserved_balance")

    status = "ready" if not blocked else "blocked"
    return {
        "status": status,
        "reservation_required": True,
        "reservation_would_be_created": status == "ready",
        "reservation_id": None,
        "idempotency_key": clean_idempotency_key,
        "business_id": business_id,
        "user_id": user_id,
        "action_key": action_key,
        "requested_credits": requested,
        "balance_credits": balance,
        "active_reserved_credits": active_reserved,
        "available_after_reservations": available_after_reservations,
        "blocked_reasons": blocked,
        "warnings": warnings,
        "side_effects": {
            "reservation_created": False,
            "credit_reserved": False,
            "credit_charged": False,
            "credit_released": False,
        },
    }


def reserve_paid_action_credits(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    action_key: str,
    estimated_credits: Any,
    idempotency_key: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    plan = build_credit_reservation_plan(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=action_key,
        estimated_credits=estimated_credits,
        idempotency_key=idempotency_key,
    )
    if plan["status"] != "ready":
        return plan

    reservation_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO operatorcreditreservations (
            id, business_id, user_id, action_key, idempotency_key, status,
            estimated_credits, reserved_credits, metadata, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, 'reserved', %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (business_id, action_key, idempotency_key)
        DO UPDATE SET updated_at = operatorcreditreservations.updated_at
        RETURNING id, status, reserved_credits
        """,
        (
            reservation_id,
            business_id,
            user_id,
            action_key,
            plan["idempotency_key"],
            plan["requested_credits"],
            plan["requested_credits"],
            json.dumps(metadata or {}, ensure_ascii=False),
        ),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    stored_id = str(row.get("id") or reservation_id)
    reserved_credits = int(row.get("reserved_credits") or plan["requested_credits"] or 0)

    result = dict(plan)
    result.update(
        {
            "status": "reserved",
            "reservation_would_be_created": False,
            "reservation_id": stored_id,
            "reserved_credits": reserved_credits,
            "blocked_reasons": [],
            "side_effects": {
                "reservation_created": True,
                "credit_reserved": True,
                "credit_charged": False,
                "credit_released": False,
            },
        }
    )
    return result


def _load_stale_reserved_candidates(
    cursor: Any,
    *,
    older_than_minutes: int,
    limit: int,
    business_id: str | None = None,
    user_id: str | None = None,
) -> list[dict[str, Any]]:
    clauses = [
        "status = 'reserved'",
        "(reserved_credits - charged_credits - released_credits) > 0",
        "created_at <= CURRENT_TIMESTAMP - (%s * INTERVAL '1 minute')",
    ]
    params: list[Any] = [older_than_minutes]
    if business_id:
        clauses.append("business_id = %s")
        params.append(business_id)
    if user_id:
        clauses.append("user_id = %s")
        params.append(user_id)
    params.append(limit)
    where_sql = " AND ".join(clauses)
    cursor.execute(
        f"""
        SELECT
            id,
            business_id,
            user_id,
            action_key,
            status,
            reserved_credits,
            charged_credits,
            released_credits,
            created_at,
            updated_at
        FROM operatorcreditreservations
        WHERE {where_sql}
        ORDER BY created_at ASC
        LIMIT %s
        """,
        tuple(params),
    )
    if hasattr(cursor, "fetchall"):
        rows = cursor.fetchall() or []
    else:
        first = cursor.fetchone()
        rows = [first] if first else []
    candidates: list[dict[str, Any]] = []
    for row in rows:
        item = _row_to_dict(cursor, row)
        if item:
            candidates.append(_reservation_summary(item))
    return candidates


def build_stale_reservation_recovery_plan(
    cursor: Any,
    *,
    older_than_minutes: Any = 60,
    limit: Any = 50,
    business_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    clean_minutes = _positive_int(older_than_minutes)
    clean_limit = _positive_int(limit)
    blocked: list[str] = []

    if clean_minutes is None:
        blocked.append("invalid_stale_window")
    if clean_limit is None:
        blocked.append("invalid_limit")

    table_available = _table_exists(cursor, "operatorcreditreservations")
    if not table_available:
        blocked.append("reservation_ledger_unavailable")

    candidates: list[dict[str, Any]] = []
    if not blocked and clean_minutes is not None and clean_limit is not None:
        candidates = _load_stale_reserved_candidates(
            cursor,
            older_than_minutes=clean_minutes,
            limit=clean_limit,
            business_id=business_id,
            user_id=user_id,
        )

    release_credits = sum(int(item.get("outstanding_credits") or 0) for item in candidates)
    return {
        "status": "ready" if not blocked else "blocked",
        "older_than_minutes": clean_minutes,
        "limit": clean_limit,
        "business_id": business_id,
        "user_id": user_id,
        "candidate_count": len(candidates),
        "release_credits": release_credits,
        "candidates": candidates,
        "blocked_reasons": blocked,
        "side_effects": {
            "reservations_released": False,
            "credit_charged": False,
            "credit_ledger_entries_created": False,
        },
    }


def release_stale_reserved_credits(
    cursor: Any,
    *,
    older_than_minutes: Any = 60,
    limit: Any = 50,
    business_id: str | None = None,
    user_id: str | None = None,
) -> dict[str, Any]:
    plan = build_stale_reservation_recovery_plan(
        cursor,
        older_than_minutes=older_than_minutes,
        limit=limit,
        business_id=business_id,
        user_id=user_id,
    )
    if plan["status"] != "ready":
        return plan

    released_ids: list[str] = []
    released_credits = 0
    for item in list(plan.get("candidates") or []):
        reservation_id = str(item.get("reservation_id") or "")
        outstanding = int(item.get("outstanding_credits") or 0)
        if not reservation_id or outstanding <= 0:
            continue
        cursor.execute(
            """
            UPDATE operatorcreditreservations
            SET status = 'released',
                released_credits = released_credits + %s,
                finalized_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
              AND status = 'reserved'
              AND (reserved_credits - charged_credits - released_credits) > 0
            """,
            (outstanding, reservation_id),
        )
        released_ids.append(reservation_id)
        released_credits += outstanding

    result = dict(plan)
    result.update(
        {
            "status": "released" if released_ids else "nothing_to_release",
            "released_count": len(released_ids),
            "released_credits": released_credits,
            "released_reservation_ids": released_ids,
            "side_effects": {
                "reservations_released": bool(released_ids),
                "credit_charged": False,
                "credit_ledger_entries_created": False,
            },
        }
    )
    return result


def build_credit_finalization_plan(
    cursor: Any,
    *,
    reservation_id: str,
    business_id: str,
    user_id: str,
    actual_credits: Any = None,
    finalization_mode: str = "charge",
) -> dict[str, Any]:
    mode = str(finalization_mode or "").strip() or "charge"
    requested_actual = _nonnegative_int(actual_credits)
    blocked: list[str] = []
    warnings: list[str] = []

    table_available = _table_exists(cursor, "operatorcreditreservations")
    if not table_available:
        blocked.append("reservation_ledger_unavailable")

    reservation = _load_reservation(cursor, reservation_id=reservation_id, business_id=business_id, user_id=user_id) if table_available else None
    if table_available and not reservation:
        blocked.append("reservation_not_found")

    if mode not in {"charge", "release"}:
        blocked.append("invalid_finalization_mode")
    if mode == "charge" and requested_actual is None:
        blocked.append("actual_credits_required")

    reserved = _int_field(reservation or {}, "reserved_credits")
    already_charged = _int_field(reservation or {}, "charged_credits")
    already_released = _int_field(reservation or {}, "released_credits")
    outstanding = max(reserved - already_charged - already_released, 0)
    reservation_status = str((reservation or {}).get("status") or "")

    if reservation_status in {"charged", "released", "failed"}:
        return {
            "status": "already_finalized",
            "finalization_mode": mode,
            "reservation_id": reservation_id,
            "business_id": business_id,
            "user_id": user_id,
            "action_key": (reservation or {}).get("action_key"),
            "requested_actual_credits": requested_actual,
            "reserved_credits": reserved,
            "already_charged_credits": already_charged,
            "already_released_credits": already_released,
            "charge_credits": 0,
            "release_credits": 0,
            "blocked_reasons": [],
            "warnings": ["reservation_already_finalized"],
            "credit_ledger_id": (reservation or {}).get("credit_ledger_id"),
            "side_effects": _finalization_side_effects(),
        }
    if reservation and reservation_status != "reserved":
        blocked.append("reservation_not_reserved")

    charge_credits = requested_actual if mode == "charge" and requested_actual is not None else 0
    release_credits = outstanding if mode == "release" else max(outstanding - charge_credits, 0)

    if charge_credits > outstanding:
        blocked.append("actual_exceeds_reserved")
    balance = _load_user_balance(cursor, user_id) if mode == "charge" and charge_credits > 0 else None
    if balance is not None and charge_credits > balance:
        blocked.append("insufficient_balance_at_finalization")
    if balance is None and mode == "charge" and charge_credits > 0:
        blocked.append("balance_unavailable")

    status = "ready" if not blocked else "blocked"
    return {
        "status": status,
        "finalization_mode": mode,
        "reservation_id": reservation_id,
        "business_id": business_id,
        "user_id": user_id,
        "action_key": (reservation or {}).get("action_key"),
        "requested_actual_credits": requested_actual,
        "reserved_credits": reserved,
        "already_charged_credits": already_charged,
        "already_released_credits": already_released,
        "balance_credits": balance,
        "charge_credits": charge_credits,
        "release_credits": release_credits,
        "blocked_reasons": blocked,
        "warnings": warnings,
        "credit_ledger_id": (reservation or {}).get("credit_ledger_id"),
        "side_effects": _finalization_side_effects(),
    }


def finalize_reserved_action_credits(
    cursor: Any,
    *,
    reservation_id: str,
    business_id: str,
    user_id: str,
    actual_credits: Any = None,
    finalization_mode: str = "charge",
    external_id: str | None = None,
) -> dict[str, Any]:
    plan = build_credit_finalization_plan(
        cursor,
        reservation_id=reservation_id,
        business_id=business_id,
        user_id=user_id,
        actual_credits=actual_credits,
        finalization_mode=finalization_mode,
    )
    if plan["status"] != "ready":
        return plan

    charge_credits = int(plan.get("charge_credits") or 0)
    release_credits = int(plan.get("release_credits") or 0)
    ledger_id = None

    if charge_credits > 0:
        ledger_id = str(uuid.uuid4())
        cursor.execute(
            """
            UPDATE users
            SET credits_balance = credits_balance - %s,
                updated_at = CURRENT_TIMESTAMP
            WHERE id = %s
            """,
            (charge_credits, user_id),
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
                -charge_credits,
                "operator_paid_action",
                str(external_id or reservation_id),
            ),
        )

    final_status = "charged" if charge_credits > 0 else "released"
    cursor.execute(
        """
        UPDATE operatorcreditreservations
        SET status = %s,
            charged_credits = charged_credits + %s,
            released_credits = released_credits + %s,
            credit_ledger_id = COALESCE(%s, credit_ledger_id),
            finalized_at = CURRENT_TIMESTAMP,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
          AND business_id = %s
          AND user_id = %s
          AND status = 'reserved'
        """,
        (
            final_status,
            charge_credits,
            release_credits,
            ledger_id,
            reservation_id,
            business_id,
            user_id,
        ),
    )

    result = dict(plan)
    result.update(
        {
            "status": final_status,
            "credit_ledger_id": ledger_id,
            "side_effects": {
                "reservation_created": False,
                "credit_reserved": False,
                "credit_charged": charge_credits > 0,
                "credit_released": release_credits > 0,
                "credit_ledger_entry_created": ledger_id is not None,
            },
        }
    )
    return result


def _finalization_side_effects() -> dict[str, bool]:
    return {
        "reservation_created": False,
        "credit_reserved": False,
        "credit_charged": False,
        "credit_released": False,
        "credit_ledger_entry_created": False,
    }
