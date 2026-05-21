from __future__ import annotations

import json
from typing import Any

from core.agent_api_security import ensure_agent_security_tables, log_agent_action


OPERATOR_CAPABILITY = "localos.operator"

OPERATOR_EVENT_TYPES = {
    "operator_context_built",
    "operator_consent_decision",
    "operator_execution_blocked",
    "operator_paid_action_estimated",
}


def _safe_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list, tuple)):
        try:
            return json.dumps(value, ensure_ascii=False, sort_keys=True)
        except Exception:
            return str(value)
    return str(value)


def _to_int(value: Any, default: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        return default
    if parsed <= 0:
        return default
    return parsed


def _decode_json(value: Any, default: Any) -> Any:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return default
    return default


def _row_value(row: Any, index: int, key: str) -> Any:
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    if hasattr(row, "keys"):
        try:
            return row[key]
        except Exception:
            return None
    if isinstance(row, (list, tuple)) and len(row) > index:
        return row[index]
    return None


def record_operator_event(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    event_type: str,
    channel: str = "web",
    action_key: str | None = None,
    status: str = "recorded",
    reason_code: str | None = None,
    input_summary: Any = "",
    output_summary: Any = "",
    metadata: dict[str, Any] | None = None,
) -> str | None:
    normalized_event = str(event_type or "").strip()
    if normalized_event not in OPERATOR_EVENT_TYPES:
        return None

    clean_metadata = dict(metadata or {})
    clean_metadata.update(
        {
            "operator_event_type": normalized_event,
            "operator_channel": str(channel or "web").strip() or "web",
            "operator_user_id": str(user_id or "").strip(),
            "action_key": str(action_key or "").strip(),
            "credit_charged": False,
            "paid_actions_performed": False,
            "external_calls_performed": False,
            "external_writes_performed": False,
        }
    )

    risk_level = "medium" if normalized_event in {"operator_consent_decision", "operator_execution_blocked", "operator_paid_action_estimated"} else "low"
    return log_agent_action(
        cursor,
        agent_client_id=None,
        business_id=str(business_id or "").strip() or None,
        action_type=normalized_event,
        capability=OPERATOR_CAPABILITY,
        required_scope=None,
        risk_level=risk_level,
        input_summary=input_summary,
        output_summary=output_summary,
        approval_id=None,
        status=str(status or "recorded"),
        reason_code=reason_code,
        ip=None,
        user_agent=None,
        metadata=clean_metadata,
    )


def list_operator_events(cursor: Any, *, business_id: str, limit: Any = 20) -> list[dict[str, Any]]:
    ensure_agent_security_tables(cursor)
    clean_limit = min(_to_int(limit, 20), 100)
    cursor.execute(
        """
        SELECT id, action_type, risk_level, input_summary, output_summary,
               status, reason_code, metadata_json, created_at
        FROM agent_action_ledger
        WHERE business_id = %s
          AND capability = %s
          AND action_type = ANY(%s)
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (str(business_id or "").strip(), OPERATOR_CAPABILITY, sorted(OPERATOR_EVENT_TYPES), clean_limit),
    )

    events: list[dict[str, Any]] = []
    for row in cursor.fetchall() or []:
        metadata = _decode_json(_row_value(row, 7, "metadata_json"), {})
        events.append(
            {
                "id": str(_row_value(row, 0, "id") or ""),
                "event_type": str(_row_value(row, 1, "action_type") or ""),
                "risk_level": str(_row_value(row, 2, "risk_level") or ""),
                "input_summary": _safe_text(_row_value(row, 3, "input_summary")),
                "output_summary": _safe_text(_row_value(row, 4, "output_summary")),
                "status": str(_row_value(row, 5, "status") or ""),
                "reason_code": str(_row_value(row, 6, "reason_code") or ""),
                "metadata": metadata if isinstance(metadata, dict) else {},
                "created_at": str(_row_value(row, 8, "created_at") or ""),
            }
        )
    return events
