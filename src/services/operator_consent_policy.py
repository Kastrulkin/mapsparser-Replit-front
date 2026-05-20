from __future__ import annotations

import sys
import uuid
from typing import Any

from services.operator_paid_actions import CONSENT_MODES, PAID_ACTIONS


AUTO_WITH_LIMITS_REQUIRED_FIELDS = ("max_credits_per_action", "max_credits_per_day")
LIMIT_FIELDS = (
    "max_credits_per_action",
    "max_credits_per_day",
    "max_credits_per_month",
    "low_balance_warning_threshold",
)


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


def _table_exists(cursor: Any) -> bool:
    cursor.execute("SELECT to_regclass(%s) AS table_ref", ("public.operatorconsentpolicies",))
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return bool(row.get("table_ref"))


def _clean_optional_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except Exception:
        return None
    if parsed < 0:
        return None
    return parsed


def default_consent_policy(business_id: str, action_key: str) -> dict[str, Any]:
    return {
        "business_id": business_id,
        "action_key": action_key,
        "mode": "ask_each_time",
        "max_credits_per_action": None,
        "max_credits_per_day": None,
        "max_credits_per_month": None,
        "low_balance_warning_threshold": None,
        "is_persisted": False,
        "execution_allowed_without_prompt": False,
    }


def normalize_consent_policy_row(business_id: str, action_key: str, row: dict[str, Any] | None) -> dict[str, Any]:
    if not row:
        return default_consent_policy(business_id, action_key)

    mode = str(row.get("mode") or "ask_each_time").strip()
    if mode not in CONSENT_MODES:
        mode = "ask_each_time"

    policy = default_consent_policy(business_id, action_key)
    policy.update(
        {
            "id": row.get("id"),
            "mode": mode,
            "max_credits_per_action": _clean_optional_int(row.get("max_credits_per_action")),
            "max_credits_per_day": _clean_optional_int(row.get("max_credits_per_day")),
            "max_credits_per_month": _clean_optional_int(row.get("max_credits_per_month")),
            "low_balance_warning_threshold": _clean_optional_int(row.get("low_balance_warning_threshold")),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
            "is_persisted": True,
        }
    )
    policy["execution_allowed_without_prompt"] = is_auto_execution_allowed(policy)
    return policy


def is_auto_execution_allowed(policy: dict[str, Any]) -> bool:
    if str(policy.get("mode") or "") != "auto_with_limits":
        return False
    for field in AUTO_WITH_LIMITS_REQUIRED_FIELDS:
        value = _clean_optional_int(policy.get(field))
        if value is None or value <= 0:
            return False
    return True


def validate_consent_policy_payload(action_key: str, payload: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    errors: list[str] = []
    if action_key not in PAID_ACTIONS:
        errors.append("unknown_action_key")

    mode = str(payload.get("mode") or "ask_each_time").strip()
    if mode not in CONSENT_MODES:
        errors.append("invalid_mode")
        mode = "ask_each_time"

    cleaned: dict[str, Any] = {"mode": mode}
    for field in LIMIT_FIELDS:
        raw_value = payload.get(field)
        clean_value = _clean_optional_int(raw_value)
        if raw_value not in (None, "") and clean_value is None:
            errors.append(f"invalid_{field}")
        cleaned[field] = clean_value

    if mode == "auto_with_limits":
        for field in AUTO_WITH_LIMITS_REQUIRED_FIELDS:
            value = cleaned.get(field)
            if value is None or int(value or 0) <= 0:
                errors.append(f"required_{field}")

    if errors:
        return None, errors
    return cleaned, []


def get_consent_policy(cursor: Any, business_id: str, action_key: str) -> dict[str, Any]:
    if action_key not in PAID_ACTIONS:
        return default_consent_policy(business_id, action_key)
    if not _table_exists(cursor):
        return default_consent_policy(business_id, action_key)

    cursor.execute(
        """
        SELECT
            id,
            business_id,
            action_key,
            mode,
            max_credits_per_action,
            max_credits_per_day,
            max_credits_per_month,
            low_balance_warning_threshold,
            created_at,
            updated_at
        FROM operatorconsentpolicies
        WHERE business_id = %s
          AND action_key = %s
        LIMIT 1
        """,
        (business_id, action_key),
    )
    return normalize_consent_policy_row(business_id, action_key, _row_to_dict(cursor, cursor.fetchone()))


def list_consent_policies(cursor: Any, business_id: str) -> list[dict[str, Any]]:
    return [get_consent_policy(cursor, business_id, action_key) for action_key in PAID_ACTIONS.keys()]


def upsert_consent_policy(
    cursor: Any,
    business_id: str,
    action_key: str,
    user_id: str,
    payload: dict[str, Any],
) -> tuple[dict[str, Any] | None, list[str]]:
    cleaned, errors = validate_consent_policy_payload(action_key, payload)
    if errors or cleaned is None:
        return None, errors
    if not _table_exists(cursor):
        return None, ["operatorconsentpolicies_missing"]

    policy_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO operatorconsentpolicies (
            id,
            business_id,
            action_key,
            mode,
            max_credits_per_action,
            max_credits_per_day,
            max_credits_per_month,
            low_balance_warning_threshold,
            created_by_user_id,
            updated_by_user_id,
            created_at,
            updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (business_id, action_key)
        DO UPDATE SET
            mode = EXCLUDED.mode,
            max_credits_per_action = EXCLUDED.max_credits_per_action,
            max_credits_per_day = EXCLUDED.max_credits_per_day,
            max_credits_per_month = EXCLUDED.max_credits_per_month,
            low_balance_warning_threshold = EXCLUDED.low_balance_warning_threshold,
            updated_by_user_id = EXCLUDED.updated_by_user_id,
            updated_at = CURRENT_TIMESTAMP
        """,
        (
            policy_id,
            business_id,
            action_key,
            cleaned["mode"],
            cleaned["max_credits_per_action"],
            cleaned["max_credits_per_day"],
            cleaned["max_credits_per_month"],
            cleaned["low_balance_warning_threshold"],
            user_id,
            user_id,
        ),
    )
    try:
        getattr(cursor, "connection").commit()
    except Exception:
        _ = sys.exc_info()
    return get_consent_policy(cursor, business_id, action_key), []
