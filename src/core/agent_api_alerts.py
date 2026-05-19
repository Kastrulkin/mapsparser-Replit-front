from __future__ import annotations

import os
from typing import Any

from core.channel_delivery import send_telegram_bot_message


def _row_get(row: Any, key: str, index: int = 0, default: Any = None) -> Any:
    if row is None:
        return default
    if hasattr(row, "get"):
        return row.get(key, default)
    if isinstance(row, (list, tuple)) and len(row) > index:
        return row[index]
    return default


def get_superadmin_telegram_ids(cursor) -> list[str]:
    env_ids = {
        value.strip()
        for value in str(os.getenv("OPENCLAW_SUPERADMIN_TELEGRAM_IDS", "")).split(",")
        if value and value.strip()
    }
    target_ids = set(env_ids)
    cursor.execute(
        """
        SELECT telegram_id
        FROM users
        WHERE is_superadmin = TRUE
          AND telegram_id IS NOT NULL
          AND NULLIF(TRIM(CAST(telegram_id AS TEXT)), '') IS NOT NULL
        """
    )
    for row in cursor.fetchall() or []:
        telegram_id = str(_row_get(row, "telegram_id", 0, "") or "").strip()
        if telegram_id:
            target_ids.add(telegram_id)
    return sorted(target_ids)


def _format_detail_lines(details: dict[str, Any] | None) -> list[str]:
    payload = details or {}
    lines = []
    for key in [
        "client",
        "client_id",
        "action_type",
        "risk_level",
        "status",
        "reason_code",
        "business_id",
        "approval_id",
        "decision",
    ]:
        value = str(payload.get(key) or "").strip()
        if value:
            lines.append(f"{key}: {value}")
    return lines


def notify_superadmins_agent_alert(cursor, title: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    bot_token = str(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    target_ids = get_superadmin_telegram_ids(cursor)
    if not bot_token or not target_ids:
        return {"sent": 0, "targets": len(target_ids), "configured": bool(bot_token)}
    detail_lines = _format_detail_lines(details)
    text = "🤖 Agent API alert\n" + str(title or "").strip()
    if detail_lines:
        text += "\n\n" + "\n".join(detail_lines)
    sent = 0
    for telegram_id in target_ids:
        result = send_telegram_bot_message(bot_token, telegram_id, text)
        if result.get("success"):
            sent += 1
    return {"sent": sent, "targets": len(target_ids), "configured": True}
