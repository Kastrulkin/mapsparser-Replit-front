from __future__ import annotations

import os
import uuid
from typing import Any

from services.operator_credit_reservation import finalize_reserved_action_credits, reserve_paid_action_credits
from services.operator_paid_preflight import build_paid_action_preflight


OPERATOR_APIFY_REFRESH_ENABLED = False
OPERATOR_MAP_REFRESH_SOURCE = "apify_yandex"
MAP_REVIEWS_REFRESH_ACTION_KEY = "map_reviews_refresh"
DEFAULT_MAP_REFRESH_ESTIMATED_CREDITS = int(os.getenv("OPERATOR_MAP_REFRESH_ESTIMATED_CREDITS", "10") or "10")


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


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _load_latest_map_url(cursor: Any, *, business_id: str) -> str:
    cursor.execute(
        """
        SELECT url
        FROM businessmaplinks
        WHERE business_id = %s
          AND COALESCE(BTRIM(url), '') <> ''
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (business_id,),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return _clean_text(row.get("url"))


def build_operator_map_refresh_plan(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    explicit_url: Any = None,
    require_runtime_flag: bool = True,
) -> dict[str, Any]:
    blocked: list[str] = []
    url = _clean_text(explicit_url) or _load_latest_map_url(cursor, business_id=business_id)
    if not url:
        blocked.append("map_link_required")
    if require_runtime_flag and not OPERATOR_APIFY_REFRESH_ENABLED:
        blocked.append("operator_apify_refresh_disabled")

    return {
        "status": "ready" if not blocked else "blocked",
        "business_id": business_id,
        "user_id": user_id,
        "url": url,
        "source": OPERATOR_MAP_REFRESH_SOURCE,
        "task_type": "parse_card",
        "blocked_reasons": blocked,
        "side_effects": {
            "parsequeue_jobs_created": False,
            "external_calls_performed": False,
            "external_writes_performed": False,
            "credit_charged": False,
        },
    }


def enqueue_operator_map_refresh(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    explicit_url: Any = None,
    queue_id: str | None = None,
    require_runtime_flag: bool = True,
) -> dict[str, Any]:
    plan = build_operator_map_refresh_plan(
        cursor,
        business_id=business_id,
        user_id=user_id,
        explicit_url=explicit_url,
        require_runtime_flag=require_runtime_flag,
    )
    if plan["status"] != "ready":
        return plan

    clean_queue_id = _clean_text(queue_id) or str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO parsequeue (
            id, url, user_id, business_id, status, task_type, source, created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, 'pending', %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        RETURNING id, status, source, task_type
        """,
        (
            clean_queue_id,
            plan["url"],
            user_id,
            business_id,
            plan["task_type"],
            plan["source"],
        ),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    result = dict(plan)
    result.update(
        {
            "status": "queued",
            "queue_id": _clean_text(row.get("id")) or clean_queue_id,
            "queue_status": _clean_text(row.get("status")) or "pending",
            "side_effects": {
                "parsequeue_jobs_created": True,
                "external_calls_performed": False,
                "external_writes_performed": False,
                "credit_charged": False,
            },
        }
    )
    return result


def enqueue_paid_operator_map_refresh(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    explicit_url: Any = None,
    estimated_credits: Any = None,
    explicit_consent: bool = False,
) -> dict[str, Any]:
    clean_estimate = estimated_credits if estimated_credits not in (None, "") else DEFAULT_MAP_REFRESH_ESTIMATED_CREDITS
    queue_id = str(uuid.uuid4())
    preflight = build_paid_action_preflight(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=MAP_REVIEWS_REFRESH_ACTION_KEY,
        estimated_credits=clean_estimate,
        explicit_consent=explicit_consent,
    )
    if preflight.get("status") != "ready":
        return {
            "status": "blocked",
            "business_id": business_id,
            "user_id": user_id,
            "action_key": MAP_REVIEWS_REFRESH_ACTION_KEY,
            "queue_id": None,
            "preflight": preflight,
            "blocked_reasons": list(preflight.get("blocked_reasons") or []),
            "billing_url": preflight.get("billing_url"),
            "side_effects": {
                "reservation_created": False,
                "parsequeue_jobs_created": False,
                "external_calls_performed": False,
                "external_writes_performed": False,
                "credit_reserved": False,
                "credit_charged": False,
            },
        }

    reservation = reserve_paid_action_credits(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=MAP_REVIEWS_REFRESH_ACTION_KEY,
        estimated_credits=clean_estimate,
        idempotency_key=f"map_refresh:{business_id}:{queue_id}",
        metadata={
            "source": "operator_paid_map_refresh",
            "parsequeue_id": queue_id,
            "provider": "apify",
            "manual_publication_only": True,
        },
    )
    if reservation.get("status") != "reserved":
        return {
            "status": "blocked",
            "business_id": business_id,
            "user_id": user_id,
            "action_key": MAP_REVIEWS_REFRESH_ACTION_KEY,
            "queue_id": None,
            "preflight": preflight,
            "reservation_result": reservation,
            "blocked_reasons": list(reservation.get("blocked_reasons") or []),
            "billing_url": preflight.get("billing_url"),
            "side_effects": {
                "reservation_created": False,
                "parsequeue_jobs_created": False,
                "external_calls_performed": False,
                "external_writes_performed": False,
                "credit_reserved": False,
                "credit_charged": False,
            },
        }

    refresh = enqueue_operator_map_refresh(
        cursor,
        business_id=business_id,
        user_id=user_id,
        explicit_url=explicit_url,
        queue_id=queue_id,
        require_runtime_flag=False,
    )
    if refresh.get("status") != "queued":
        rollback = finalize_reserved_action_credits(
            cursor,
            reservation_id=str(reservation.get("reservation_id") or ""),
            business_id=business_id,
            user_id=user_id,
            finalization_mode="release",
            external_id=f"map_refresh_enqueue_failed:{queue_id}",
        )
        return {
            "status": "blocked",
            "business_id": business_id,
            "user_id": user_id,
            "action_key": MAP_REVIEWS_REFRESH_ACTION_KEY,
            "queue_id": None,
            "preflight": preflight,
            "reservation_result": reservation,
            "rollback_result": rollback,
            "refresh_result": refresh,
            "blocked_reasons": list(refresh.get("blocked_reasons") or ["map_refresh_enqueue_failed"]),
            "billing_url": preflight.get("billing_url"),
            "side_effects": {
                "reservation_created": True,
                "parsequeue_jobs_created": False,
                "external_calls_performed": False,
                "external_writes_performed": False,
                "credit_reserved": True,
                "credit_charged": False,
                "credit_released": bool((rollback.get("side_effects") or {}).get("credit_released")),
            },
        }

    result = dict(refresh)
    result.update(
        {
            "action_key": MAP_REVIEWS_REFRESH_ACTION_KEY,
            "preflight": preflight,
            "reservation_result": reservation,
            "reservation_id": reservation.get("reservation_id"),
            "estimated_credits": preflight.get("estimated_credits"),
            "balance_credits": preflight.get("balance_credits"),
            "billing_url": preflight.get("billing_url"),
            "paid_actions_performed": True,
            "manual_publication_only": True,
            "side_effects": {
                "reservation_created": True,
                "parsequeue_jobs_created": True,
                "external_calls_performed": False,
                "external_writes_performed": False,
                "credit_reserved": True,
                "credit_charged": False,
            },
        }
    )
    return result
