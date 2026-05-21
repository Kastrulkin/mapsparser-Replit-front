from __future__ import annotations

from typing import Any

from services.operator_consent_policy import get_consent_policy, is_auto_execution_allowed
from services.operator_paid_actions import PAID_ACTIONS


EXECUTION_ENABLED = False
BILLING_URL = "/dashboard/billing"


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


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    value = str(row.get("to_regclass") or row.get("table_ref") or row.get("?column?") or "")
    return value == table_name or value == f"public.{table_name}"


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


def _load_reserved_or_charged_usage(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    action_key: str,
    window: str,
) -> int | None:
    if not _table_exists(cursor, "operatorcreditreservations"):
        return None

    window_sql = "day" if window == "day" else "month"
    cursor.execute(
        f"""
        SELECT COALESCE(
            SUM(
                charged_credits
                + GREATEST(reserved_credits - charged_credits - released_credits, 0)
            ),
            0
        ) used_credits
        FROM operatorcreditreservations
        WHERE business_id = %s
          AND user_id = %s
          AND action_key = %s
          AND status IN ('reserved', 'charged')
          AND created_at >= DATE_TRUNC('{window_sql}', CURRENT_TIMESTAMP)
        """,
        (business_id, user_id, action_key),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    try:
        return int(row.get("used_credits") or 0)
    except Exception:
        return None


def build_paid_action_usage_window(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    action_key: str,
) -> dict[str, Any]:
    blocked: list[str] = []
    used_today = _load_reserved_or_charged_usage(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=action_key,
        window="day",
    )
    used_month = _load_reserved_or_charged_usage(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=action_key,
        window="month",
    )
    if used_today is None or used_month is None:
        blocked.append("usage_window_unavailable")

    return {
        "status": "ready" if not blocked else "blocked",
        "business_id": business_id,
        "user_id": user_id,
        "action_key": action_key,
        "used_credits_today": used_today,
        "used_credits_month": used_month,
        "blocked_reasons": blocked,
    }


def _check_limits(
    policy: dict[str, Any],
    estimated_credits: int | None,
    usage_window: dict[str, Any] | None = None,
) -> list[str]:
    if estimated_credits is None:
        return []

    blocked: list[str] = []
    action_limit = _limit_value(policy, "max_credits_per_action")
    day_limit = _limit_value(policy, "max_credits_per_day")
    month_limit = _limit_value(policy, "max_credits_per_month")

    if action_limit is not None and estimated_credits > action_limit:
        blocked.append("limit_per_action_exceeded")

    if usage_window and usage_window.get("status") != "ready":
        blocked.extend(list(usage_window.get("blocked_reasons") or []))
        return blocked

    used_today = 0
    used_month = 0
    if usage_window:
        try:
            used_today = int(usage_window.get("used_credits_today") or 0)
            used_month = int(usage_window.get("used_credits_month") or 0)
        except Exception:
            blocked.append("usage_window_unavailable")
            return blocked

    if day_limit is not None and used_today + estimated_credits > day_limit:
        blocked.append("limit_per_day_exceeded")
    if month_limit is not None and used_month + estimated_credits > month_limit:
        blocked.append("limit_per_month_exceeded")
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
    usage_window = build_paid_action_usage_window(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=action_key,
    )

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
        pass
    elif mode == "auto_with_limits":
        if not is_auto_execution_allowed(policy):
            blocked.append("consent_limits_required")
        blocked.extend(_check_limits(policy, estimated, usage_window))
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
        "billing_url": BILLING_URL,
        "usage_window": usage_window,
        "consent_policy": policy,
        "requires_explicit_consent": False,
        "paid_actions_performed": False,
        "credit_charged": False,
        "external_calls_performed": False,
        "next_step": "execution_runtime_not_enabled" if would_be_allowed else "top_up_credits" if "insufficient_balance" in blocked else "resolve_blocked_reasons",
        "copy": {
            "title": "Preflight платного действия",
            "summary": "Проверил баланс кредитов и лимиты. Платное действие не запускалось.",
            "ready": "Preflight пройден. Следующий Sprint сможет безопасно подключить execution runtime.",
            "blocked": "Недостаточно кредитов для платной функции. Пополните счёт или выберите тариф.",
            "billing_cta": "Пополнить счёт",
            "billing_url": BILLING_URL,
        },
    }
