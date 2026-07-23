from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from typing import Any
from urllib.parse import parse_qsl


def validate_telegram_webapp_init_data(
    init_data: Any,
    *,
    bot_token: str | None = None,
    max_age_seconds: int = 86400,
) -> dict[str, Any] | None:
    raw = str(init_data or "").strip()
    token = str(bot_token or os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not raw or not token:
        return None
    values = dict(parse_qsl(raw, keep_blank_values=True))
    received_hash = str(values.pop("hash", "") or "").strip().lower()
    if not received_hash:
        return None
    data_check_string = "\n".join(f"{key}={values[key]}" for key in sorted(values))
    secret_key = hmac.new(b"WebAppData", token.encode("utf-8"), hashlib.sha256).digest()
    expected_hash = hmac.new(secret_key, data_check_string.encode("utf-8"), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(received_hash, expected_hash):
        return None
    try:
        auth_date = int(values.get("auth_date") or 0)
    except (TypeError, ValueError):
        return None
    if auth_date <= 0 or abs(int(time.time()) - auth_date) > max(60, int(max_age_seconds or 86400)):
        return None
    try:
        user = json.loads(values.get("user") or "{}")
    except Exception:
        return None
    if not isinstance(user, dict) or not user.get("id"):
        return None
    return {
        "telegram_id": str(user.get("id")),
        "username": str(user.get("username") or ""),
        "first_name": str(user.get("first_name") or ""),
        "last_name": str(user.get("last_name") or ""),
        "auth_date": auth_date,
        "query_id": str(values.get("query_id") or ""),
    }


def load_localos_user_for_telegram(cursor: Any, telegram_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT id, email, name, COALESCE(is_superadmin, FALSE) AS is_superadmin,
               COALESCE(is_active, TRUE) AS is_active
        FROM users
        WHERE telegram_id = %s
        LIMIT 1
        """,
        (str(telegram_id or "").strip(),),
    )
    row = cursor.fetchone()
    if row is None:
        return None
    if isinstance(row, dict):
        result = dict(row)
    elif hasattr(row, "keys"):
        result = dict(row)
    else:
        columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
        result = {columns[index]: row[index] for index in range(min(len(columns), len(row)))}
    return result if result.get("is_active") else None
