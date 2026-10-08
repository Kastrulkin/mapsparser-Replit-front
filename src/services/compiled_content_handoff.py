"""Immutable scope and standing-consent helpers for scheduled content handoffs."""

from __future__ import annotations

import hashlib
import json
from typing import Any


CAPABILITY = "content.publish_handoff"
ALLOWED_PLATFORMS = {"telegram", "vk", "max"}


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def handoff_scope(version: dict[str, Any], business_id: str) -> dict[str, Any] | None:
    """Return the only supported, static scheduled-send scope for a version."""
    if str(version.get("execution_mode") or "") != "scheduled" or str(version.get("trigger") or "") != "schedule.daily":
        return None
    steps = version.get("steps_json", version.get("steps"))
    if isinstance(steps, str):
        try:
            steps = json.loads(steps)
        except (TypeError, ValueError):
            return None
    if not isinstance(steps, list):
        return None
    matches = [step for step in steps if isinstance(step, dict) and step.get("capability") == CAPABILITY]
    if len(matches) != 1:
        return None
    payload = _json_object(matches[0].get("payload"))
    platforms = payload.get("platforms")
    recipient = str(payload.get("recipient_user_id") or "").strip()
    target_business = str(payload.get("business_id") or "").strip()
    lead_days = payload.get("lead_days")
    local_time = str(payload.get("time") or "")
    timezone_name = str(payload.get("timezone") or "").strip()
    schedule = _json_object(version.get("schedule_json") or version.get("schedule"))
    if (
        target_business != str(business_id or "")
        or not recipient
        or not isinstance(platforms, list)
        or not platforms
        or len(set(platforms)) != len(platforms)
        or not set(platforms).issubset(ALLOWED_PLATFORMS)
        or type(lead_days) is not int
        or not 0 <= lead_days <= 7
        or len(local_time) != 5
        or local_time[2] != ":"
        or not local_time[:2].isdigit()
        or not local_time[3:].isdigit()
        or int(local_time[:2]) > 23
        or int(local_time[3:]) > 59
        or not timezone_name
        or str(schedule.get("time") or "") != local_time
        or str(schedule.get("timezone") or "") != timezone_name
    ):
        return None
    return {
        "business_id": target_business,
        "recipient_user_id": recipient,
        "platforms": sorted(platforms),
        "lead_days": lead_days,
        "time": local_time,
        "timezone": timezone_name,
    }


def scope_digest(*, version_id: str, scope: dict[str, Any]) -> str:
    canonical = json.dumps(
        {"version_id": str(version_id), "scope": scope},
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def has_active_consent(metadata: Any, *, version_id: str, scope: dict[str, Any]) -> bool:
    value = _json_object(metadata).get("compiled_content_handoff_consent")
    return (
        isinstance(value, dict)
        and str(value.get("version_id") or "") == str(version_id)
        and value.get("scope") == scope
        and str(value.get("scope_digest") or "") == scope_digest(version_id=version_id, scope=scope)
    )
