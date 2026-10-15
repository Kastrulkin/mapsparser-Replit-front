"""MAX launch signatures; intentionally independent of Telegram identities."""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from urllib.parse import parse_qsl


def max_enabled() -> bool:
    return os.getenv("MAX_ENABLED", "false").lower() in {"1", "true", "yes", "on"}


def validate_max_init_data(raw, *, bot_token=None, now=None, max_age_seconds=3600):
    token = bot_token or os.getenv("MAX_BOT_TOKEN", "")
    if not isinstance(raw, str) or not raw or len(raw) > 32768 or not token:
        return None
    try:
        pairs = parse_qsl(raw, keep_blank_values=True, strict_parsing=True)
        if len({key for key, _ in pairs}) != len(pairs):
            return None
        values = dict(pairs)
        supplied = values.pop("hash", "")
        secret = hmac.new(b"WebAppData", token.encode(), hashlib.sha256).digest()
        check = "\n".join(f"{key}={values[key]}" for key in sorted(values))
        expected = hmac.new(secret, check.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(supplied, expected):
            return None
        age = (time.time() if now is None else now) - int(values.get("auth_date", "0"))
        if not 0 <= age <= max_age_seconds:
            return None
        user = json.loads(values.get("user", "{}"))
        if not isinstance(user, dict) or type(user.get("id")) is not int or user["id"] <= 0:
            return None
        return {"max_id": str(user["id"]), "first_name": str(user.get("first_name") or ""),
                "auth_date": int(values["auth_date"])}
    except (ValueError, TypeError, UnicodeError):
        return None


def load_localos_user_for_max(cursor, max_id):
    cursor.execute("""SELECT u.id, u.email, u.name, COALESCE(u.is_superadmin,FALSE) AS is_superadmin,
        u.is_active FROM users u JOIN max_identities m ON m.user_id=u.id
        WHERE m.max_id=%s AND m.revoked_at IS NULL AND COALESCE(u.is_active,TRUE)=TRUE""", (str(max_id),))
    row = cursor.fetchone()
    if not row:
        return None
    return dict(row) if hasattr(row, "keys") else dict(zip([col[0] for col in cursor.description], row))


def max_session_user_agent(cursor, user_id):
    """Bind sessions to an exact server-side identity version, independent of clocks."""
    from datetime import timezone
    cursor.execute("SELECT max_id,linked_at FROM max_identities WHERE user_id=%s AND revoked_at IS NULL", (str(user_id),))
    row = cursor.fetchone()
    if not row:
        return None
    identity = row['max_id'] if hasattr(row, 'keys') else row[0]
    linked = row['linked_at'] if hasattr(row, 'keys') else row[1]
    if hasattr(linked, 'astimezone'):
        linked = linked.astimezone(timezone.utc).isoformat()
    digest = hashlib.sha256((str(identity) + '\n' + str(linked)).encode()).hexdigest()
    return 'localos-max-mini-app:' + digest
