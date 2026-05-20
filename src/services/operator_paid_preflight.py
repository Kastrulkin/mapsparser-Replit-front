from __future__ import annotations

from typing import Any

from services.operator_consent_policy import get_consent_policy, is_auto_execution_allowed
from services.operator_paid_actions import PAID_ACTIONS


EXECUTION_ENABLED = False


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
    value = row.get("credits_balance")
    try:
        return int(value or 0)
    except Exception:
        return None


def _limit_value(policy: dict[str, Any], key: str) -> int | None:
    return _positive_int(policy.get(key))


def _check_limits(policy: dict[str, Any], estimated_credits: int | None) -> list[str]:
    if estimated_credits is None:
        return []

    blocked: list[str] = []
    limit_pairs = (
        ("max_credits_per_action", "limit_per_action_exceeded"),
        ("max_credits_per_day", "limit_per_day_exceeded"),
        ("max_credits_per_month", "limit_per_month_exceeded"),
    )
    for field, reason in limit_pairs:
        limit = _limit_value(policy, field)
        if limit is not None and estimated_credits > limit:
            blocked.append(reason)
    return blocked


def build_paid_action_preflight(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    action_key: str,
    estimated_credits: Any = None,
    explicit_consent: bool = False,
) -> dict[str, Any]:
    estimated = _positive_int(estimated_credits)
    config = PAID_ACTIONS.get(action_key)
    blocked: list[str] = []
    warnings: list[str] = []

    if not config:
        blocked.append("unknown_action_key")
        return {
            "action_key": action_key,
            "business_id": business_id,
            "status": "blocked",
            "execution_status": "preflight_only",
            "execution_enabled": EXECUTION_ENABLED,
            "would_be_allowed": False,
            "can_execute_now": False,
            "blocked_reasons": blocked,
            "warnings": warnings,
            "paid_actions_performed": False,
        }

    policy = get_consent_policy(cursor, business_id, action_key)
    balance = _load_user_balance(cursor, user_id)

    if estimated is None:
        blocked.append("estimate_required")
    if balance is None:
        blocked.append("balance_unavailable")
    elif estimated is not None and balance < estimated:
        blocked.append("insufficient_balance")

    mode = str(policy.get("mode") or "ask_each_time")
    if mode == "disabled":
        blocked.append("consent_disabled")
    elif mode == "ask_each_time":
        if not explicit_consent:
            blocked.append("explicit_consent_required")
    elif mode == "auto_with_limits":
        if not is_auto_execution_allowed(policy):
            blocked.append("consent_limits_required")
        blocked.extend(_check_limits(policy, estimated))
        warnings.append("daily_monthly_usage_history_not_reserved")
    else:
        blocked.append("invalid_consent_mode")

    would_be_allowed = not blocked
    return {
        "action_key": action_key,
        "business_id": business_id,
        "label": config.get("label"),
        "action_class": config.get("action_class"),
        "status": "ready" if would_be_allowed else "blocked",
        "execution_status": "preflight_only",
        "execution_enabled": EXECUTION_ENABLED,
        "would_be_allowed": would_be_allowed,
        "can_execute_now": False,
        "blocked_reasons": blocked,
        "warnings": warnings,
        "estimated_credits": estimated,
        "balance_credits": balance,
        "consent_policy": policy,
        "requires_explicit_consent": mode == "ask_each_time",
        "paid_actions_performed": False,
        "credit_charged": False,
        "external_calls_performed": False,
        "next_step": "execution_runtime_not_enabled" if would_be_allowed else "resolve_blocked_reasons",
        "copy": {
            "title": "Preflight платного действия",
            "summary": "Проверил consent, лимиты и баланс. Платное действие не запускалось.",
            "ready": "Preflight пройден. Следующий Sprint сможет безопасно подключить execution runtime.",
            "blocked": "Нужно устранить причины блокировки перед запуском.",
        },
    }
