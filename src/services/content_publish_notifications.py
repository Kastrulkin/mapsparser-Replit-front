from __future__ import annotations

import json
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urlencode


TELEGRAM_MINI_APP_URL = "https://localos.pro/telegram/control"
HANDOFF_PLATFORMS = {"telegram", "vk"}
HANDOFF_STATUSES = {"approved", "needs_manual_publish"}


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    if isinstance(value, (tuple, list)):
        return {columns[index]: value[index] for index in range(min(len(columns), len(value)))}
    return {}


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


def _enabled_scopes(cursor: Any) -> list[dict[str, str]]:
    cursor.execute(
        """
        SELECT user_id, telegram_id, notification_preferences_json
        FROM telegramcontrolpreferences
        WHERE NULLIF(BTRIM(CAST(telegram_id AS TEXT)), '') IS NOT NULL
        """
    )
    scopes: list[dict[str, str]] = []
    for raw in cursor.fetchall() or []:
        preference = _row(cursor, raw)
        notifications = _json_object(preference.get("notification_preferences_json"))
        for scope_key, settings in notifications.items():
            if not isinstance(settings, dict) or not bool(settings.get("content_publications")):
                continue
            scope_type, separator, scope_id = str(scope_key).partition(":")
            if not separator or scope_type not in {"business", "network"} or not scope_id:
                continue
            scopes.append(
                {
                    "user_id": str(preference.get("user_id") or ""),
                    "telegram_id": str(preference.get("telegram_id") or ""),
                    "scope_type": scope_type,
                    "scope_id": scope_id,
                }
            )
    return scopes


def collect_due_content_publish_handoffs(
    conn: Any,
    *,
    now: datetime | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    cursor = conn.cursor()
    observed_at = now or datetime.now(timezone.utc)
    today = observed_at.date()
    result: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for scope in _enabled_scopes(cursor):
        scope_filter = "sp.business_id = %s" if scope["scope_type"] == "business" else "b.network_id = %s"
        cursor.execute(
            f"""
            SELECT sp.*, b.name business_name, COALESCE(b.address, '') business_address
            FROM social_posts sp
            JOIN businesses b ON b.id = sp.business_id
            WHERE {scope_filter}
              AND sp.platform = ANY(%s)
              AND sp.publish_mode = 'manual'
              AND sp.status = ANY(%s)
              AND COALESCE(sp.scheduled_for::date, %s) <= %s
            ORDER BY sp.scheduled_for, sp.created_at
            LIMIT %s
            """,
            (scope["scope_id"], list(HANDOFF_PLATFORMS), list(HANDOFF_STATUSES), today, today, max(1, limit)),
        )
        for raw in cursor.fetchall() or []:
            post = _row(cursor, raw)
            post_id = str(post.get("id") or "")
            user_id = scope["user_id"]
            identity = (post_id, user_id)
            metadata = _json_object(post.get("metadata_json"))
            deliveries = _json_object(_json_object(metadata.get("staff_handoff")).get("telegram_deliveries"))
            if not post_id or identity in seen or deliveries.get(user_id):
                continue
            seen.add(identity)
            result.append({**post, **scope})
            if len(result) >= max(1, limit):
                return result
    return result


def format_content_publish_handoff(item: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    platform = str(item.get("platform") or "").strip()
    platform_label = "Telegram" if platform == "telegram" else "VK"
    business_name = str(item.get("business_name") or "Бизнес").strip()
    address = str(item.get("business_address") or "").strip()
    text = str(item.get("platform_text") or item.get("base_text") or "").strip()
    scheduled = item.get("scheduled_for")
    if isinstance(scheduled, datetime):
        date_label = scheduled.date().strftime("%d.%m.%Y")
    elif isinstance(scheduled, date):
        date_label = scheduled.strftime("%d.%m.%Y")
    else:
        date_label = "сегодня"
    heading = f"Публикация для {platform_label} · {date_label}"
    location = " · ".join(value for value in (business_name, address) if value)
    message = "\n\n".join(
        [heading, location, text, "Разместите текст вручную и отметьте публикацию в ЛокалОС."]
    )
    query = urlencode(
        {
            "screen": "content",
            "scope_type": "business",
            "scope_id": str(item.get("business_id") or ""),
            "item_id": str(item.get("content_plan_item_id") or ""),
        }
    )
    reply_markup = {
        "inline_keyboard": [[{"text": "Открыть публикацию", "web_app": {"url": f"{TELEGRAM_MINI_APP_URL}?{query}"}}]]
    }
    return message[:4096], reply_markup


def mark_content_publish_handoff_sent(
    conn: Any,
    *,
    post_id: str,
    user_id: str,
    telegram_message_id: int,
    sent_at: datetime | None = None,
) -> bool:
    cursor = conn.cursor()
    cursor.execute("SELECT metadata_json FROM social_posts WHERE id = %s FOR UPDATE", (post_id,))
    row = _row(cursor, cursor.fetchone())
    if not row:
        return False
    metadata = _json_object(row.get("metadata_json"))
    handoff = _json_object(metadata.get("staff_handoff"))
    deliveries = _json_object(handoff.get("telegram_deliveries"))
    deliveries[str(user_id)] = {
        "sent_at": (sent_at or datetime.now(timezone.utc)).isoformat(),
        "telegram_message_id": int(telegram_message_id or 0),
    }
    metadata["staff_handoff"] = {**handoff, "telegram_deliveries": deliveries}
    cursor.execute(
        "UPDATE social_posts SET metadata_json = %s::jsonb, updated_at = NOW() WHERE id = %s",
        (json.dumps(metadata, ensure_ascii=False), post_id),
    )
    return bool(cursor.rowcount)
