from __future__ import annotations

from typing import Any

from services.operator_credit_reservation import finalize_reserved_action_credits
from services.operator_refresh_result import build_refresh_result_status
from services.operator_refresh_retry import RETRYABLE_RELIABILITY_STATUSES


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


def _int_value(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def build_refresh_recovery_plan(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    queue_id: str,
) -> dict[str, Any]:
    result = build_refresh_result_status(
        cursor,
        business_id=business_id,
        user_id=user_id,
        queue_id=queue_id,
    )
    billing = result.get("billing_state") if isinstance(result.get("billing_state"), dict) else {}
    reliability = result.get("reliability_state") if isinstance(result.get("reliability_state"), dict) else {}
    queue_status = _clean_text(result.get("queue_status") or result.get("status")).lower()
    reliability_status = _clean_text(reliability.get("status"))
    outstanding = _int_value(billing.get("outstanding_credits"))
    reservation_id = _clean_text(billing.get("reservation_id"))

    blocked: list[str] = []
    if result.get("status") in {"processing", "blocked"} or queue_status in {"pending", "processing", "captcha"}:
        blocked.append("refresh_job_not_terminal")

    retry_allowed = not blocked and reliability_status in RETRYABLE_RELIABILITY_STATUSES
    release_allowed = not blocked and outstanding > 0 and bool(reservation_id)

    return {
        "status": "ready" if retry_allowed or release_allowed else "blocked",
        "queue_id": queue_id,
        "queue_status": queue_status,
        "reliability_state": reliability,
        "billing_state": billing,
        "retry_allowed": retry_allowed,
        "release_allowed": release_allowed,
        "reservation_id": reservation_id or None,
        "outstanding_credits": outstanding,
        "blocked_reasons": blocked if blocked else ([] if retry_allowed or release_allowed else ["no_recovery_action_available"]),
        "next_step": "ask_user_to_retry" if retry_allowed else ("release_reserved_credits" if release_allowed else "no_action"),
        "side_effects": {
            "reservation_released": False,
            "retry_job_created": False,
            "external_calls_performed": False,
            "external_writes_performed": False,
            "credit_charged": False,
        },
    }


def release_failed_refresh_reservation(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    queue_id: str,
    confirm_release: bool = False,
) -> dict[str, Any]:
    plan = build_refresh_recovery_plan(
        cursor,
        business_id=business_id,
        user_id=user_id,
        queue_id=queue_id,
    )
    if not plan.get("release_allowed"):
        return {
            **plan,
            "status": "blocked",
            "blocked_reasons": list(plan.get("blocked_reasons") or ["release_not_allowed"]),
        }
    if not confirm_release:
        return {
            **plan,
            "status": "blocked",
            "blocked_reasons": ["explicit_release_confirmation_required"],
            "next_step": "confirm_release",
        }

    release = finalize_reserved_action_credits(
        cursor,
        reservation_id=str(plan.get("reservation_id") or ""),
        business_id=business_id,
        user_id=user_id,
        finalization_mode="release",
        external_id=f"failed_refresh_release:{queue_id}",
    )
    return {
        **plan,
        "status": "released" if release.get("status") in {"released", "completed"} else "blocked",
        "release_result": release,
        "blocked_reasons": [] if release.get("status") in {"released", "completed"} else list(release.get("blocked_reasons") or []),
        "side_effects": {
            "reservation_released": bool((release.get("side_effects") or {}).get("credit_released")),
            "retry_job_created": False,
            "external_calls_performed": False,
            "external_writes_performed": False,
            "credit_charged": False,
        },
    }
