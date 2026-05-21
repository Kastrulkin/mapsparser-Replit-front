from __future__ import annotations

import hashlib
from typing import Any

from services.operator_paid_actions import PAID_ACTIONS


ADAPTER_STAGES = ("estimate", "reserve", "execute", "finalize")
ADAPTER_RUNTIME_MODE = "internal_stub"


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


def _stage_result(stage: str, *, action_key: str, dry_run: bool, status: str = "planned", details: dict[str, Any] | None = None) -> dict[str, Any]:
    return {
        "stage": stage,
        "status": status,
        "dry_run": dry_run,
        "action_key": action_key,
        "details": dict(details or {}),
    }


def build_paid_action_adapter_plan(
    *,
    action_key: str,
    business_id: str,
    user_id: str,
    estimated_credits: Any = None,
    idempotency_key: str | None = None,
) -> dict[str, Any]:
    config = PAID_ACTIONS.get(action_key)
    clean_estimate = _positive_int(estimated_credits)
    clean_idempotency_key = str(idempotency_key or "").strip() or _stable_id(action_key, business_id, user_id, clean_estimate)

    if not config:
        return {
            "action_key": action_key,
            "business_id": business_id,
            "adapter_status": "unsupported_action",
            "runtime_mode": ADAPTER_RUNTIME_MODE,
            "dry_run": True,
            "idempotency_key": clean_idempotency_key,
            "stages": [
                _stage_result(
                    stage,
                    action_key=action_key,
                    dry_run=True,
                    status="skipped",
                    details={"reason": "unsupported_action"},
                )
                for stage in ADAPTER_STAGES
            ],
            "side_effects": _empty_side_effects(),
        }

    provider = str(config.get("provider") or "")
    cost_source = str(config.get("cost_source") or "")
    stages = [
        _stage_result(
            "estimate",
            action_key=action_key,
            dry_run=True,
            details={
                "cost_source": cost_source,
                "estimated_credits": clean_estimate,
                "provider": provider,
            },
        ),
        _stage_result(
            "reserve",
            action_key=action_key,
            dry_run=True,
            details={
                "credit_reservation_required": True,
                "credit_reserved": False,
            },
        ),
        _stage_result(
            "execute",
            action_key=action_key,
            dry_run=True,
            details={
                "adapter": "internal_stub",
                "provider_call_allowed": False,
                "external_call_performed": False,
            },
        ),
        _stage_result(
            "finalize",
            action_key=action_key,
            dry_run=True,
            details={
                "actual_credits_charged": 0,
                "credit_released": False,
                "final_status": "dry_run_only",
            },
        ),
    ]

    return {
        "action_key": action_key,
        "business_id": business_id,
        "adapter_status": "planned",
        "runtime_mode": ADAPTER_RUNTIME_MODE,
        "dry_run": True,
        "idempotency_key": clean_idempotency_key,
        "stages": stages,
        "side_effects": _empty_side_effects(),
    }


def run_paid_action_adapter_stub(plan: dict[str, Any]) -> dict[str, Any]:
    stages = []
    for item in list(plan.get("stages") or []):
        stage = dict(item or {})
        if stage.get("status") == "planned":
            stage["status"] = "dry_run_completed"
        stages.append(stage)

    return {
        "action_key": plan.get("action_key"),
        "business_id": plan.get("business_id"),
        "adapter_status": "dry_run_completed" if plan.get("adapter_status") == "planned" else plan.get("adapter_status"),
        "runtime_mode": ADAPTER_RUNTIME_MODE,
        "dry_run": True,
        "idempotency_key": plan.get("idempotency_key"),
        "stages": stages,
        "side_effects": _empty_side_effects(),
    }


def _empty_side_effects() -> dict[str, bool]:
    return {
        "paid_actions_performed": False,
        "credit_reserved": False,
        "credit_charged": False,
        "external_calls_performed": False,
        "external_writes_performed": False,
        "parsequeue_jobs_created": False,
        "ai_generation_performed": False,
    }
