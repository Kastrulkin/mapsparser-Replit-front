from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any


CANARY_METADATA_KEY = "certification_canary"
CANARY_SCHEMA = "localos_agent_canary_v1"


def evaluate_agent_canary_budget(
    cursor: Any,
    *,
    blueprint: dict[str, Any],
    requested_credits: int,
    now: datetime | None = None,
) -> dict[str, Any]:
    policy = _canary_policy(blueprint)
    if not policy or str(policy.get("status") or "") != "active":
        return {"enabled": False, "allowed": True, "reason": "not_configured"}

    canary_key = str(policy.get("key") or "").strip()
    starts_at = _parse_datetime(policy.get("starts_at"))
    ends_at = _parse_datetime(policy.get("ends_at"))
    max_reserved_credits = _positive_int(policy.get("max_reserved_credits"))
    current = _utc_datetime(now or datetime.now(timezone.utc))
    if (
        str(policy.get("schema") or "") != CANARY_SCHEMA
        or not canary_key
        or not starts_at
        or not ends_at
        or starts_at >= ends_at
        or not max_reserved_credits
    ):
        return {"enabled": True, "allowed": False, "reason": "invalid_policy"}
    if current < starts_at:
        return {
            "enabled": True,
            "allowed": False,
            "reason": "not_started",
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "max_reserved_credits": max_reserved_credits,
        }
    if current > ends_at:
        return {
            "enabled": True,
            "allowed": False,
            "reason": "ended",
            "starts_at": starts_at.isoformat(),
            "ends_at": ends_at.isoformat(),
            "max_reserved_credits": max_reserved_credits,
        }

    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"agent-canary:{canary_key}",))
    cursor.execute(
        """
        SELECT COALESCE(SUM(reservation.reserved_credits), 0) AS reserved_credits
        FROM agent_runs run
        JOIN agent_blueprints blueprint ON blueprint.id = run.blueprint_id
        JOIN operatorcreditreservations reservation ON reservation.id = run.billing_reservation_id
        WHERE blueprint.metadata_json->'certification_canary'->>'key' = %s
          AND run.queued_at >= %s
          AND run.queued_at <= %s
        """,
        (canary_key, starts_at, ends_at),
    )
    row = cursor.fetchone() or {}
    reserved_credits = max(int(row.get("reserved_credits") or 0), 0)
    requested = max(int(requested_credits or 0), 0)
    projected = reserved_credits + requested
    allowed = projected <= max_reserved_credits
    return {
        "enabled": True,
        "allowed": allowed,
        "reason": "ready" if allowed else "budget_exhausted",
        "key": canary_key,
        "starts_at": starts_at.isoformat(),
        "ends_at": ends_at.isoformat(),
        "reserved_credits": reserved_credits,
        "requested_credits": requested,
        "projected_reserved_credits": projected,
        "max_reserved_credits": max_reserved_credits,
    }


def pause_agent_canary_blueprint(
    cursor: Any,
    *,
    blueprint_id: str,
    reason: str,
    now: datetime | None = None,
) -> bool:
    paused_at = _utc_datetime(now or datetime.now(timezone.utc))
    cursor.execute(
        """
        UPDATE agent_blueprints
        SET status = 'paused',
            metadata_json = COALESCE(metadata_json, '{}'::jsonb)
                || jsonb_build_object(
                    'certification_canary',
                    COALESCE(metadata_json->'certification_canary', '{}'::jsonb)
                        || jsonb_build_object(
                            'status', 'paused',
                            'pause_reason', %s,
                            'paused_at', %s
                        )
                ),
            updated_at = NOW()
        WHERE id = %s
          AND status = 'active'
        RETURNING id
        """,
        (str(reason or "canary_stopped"), paused_at, str(blueprint_id or "")),
    )
    return bool(cursor.fetchone())


def _canary_policy(blueprint: dict[str, Any]) -> dict[str, Any]:
    metadata = blueprint.get("metadata_json")
    if isinstance(metadata, str):
        try:
            metadata = json.loads(metadata)
        except (TypeError, ValueError):
            metadata = {}
    if not isinstance(metadata, dict):
        return {}
    policy = metadata.get(CANARY_METADATA_KEY)
    return policy if isinstance(policy, dict) else {}


def _parse_datetime(value: Any) -> datetime | None:
    text = str(value or "").strip().replace("Z", "+00:00")
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _positive_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return None
    return parsed if parsed > 0 else None
