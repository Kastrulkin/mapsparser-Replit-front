from __future__ import annotations

import hashlib
import json
import os
from typing import Any
from urllib.parse import urlencode

from psycopg2.extras import Json

from services.lead_journey_service import journey_enabled, reconcile_map_actions


MINI_APP_URL = os.getenv("TELEGRAM_MINI_APP_URL", "https://localos.pro/telegram/control")


def reconcile_completed_map_refreshes(conn: Any) -> int:
    if not journey_enabled("MAPS_JOURNEY_ENABLED"):
        return 0
    cursor = conn.cursor()
    cursor.execute(
        "SELECT DISTINCT business_id FROM journey_actions WHERE flow_type = 'maps' AND action_type = 'compare_snapshot' AND status = 'waiting' AND business_id IS NOT NULL"
    )
    business_ids = [str(_row(cursor, value).get("business_id") or "") for value in (cursor.fetchall() or [])]
    business_ids = [value for value in business_ids if value]
    if not business_ids:
        return 0
    reconcile_map_actions(cursor, business_ids=business_ids)
    changed = max(0, int(cursor.rowcount or 0))
    conn.commit()
    return changed


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "keys"):
        return dict(value)
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    return {columns[index]: value[index] for index in range(min(len(columns), len(value)))}


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


def _tasks_enabled(preferences: Any, business_id: str) -> bool:
    payload = _json_object(preferences)
    settings = payload.get(f"business:{business_id}")
    return isinstance(settings, dict) and bool(settings.get("tasks"))


def collect_due_journey_action_notifications(conn: Any) -> list[dict[str, Any]]:
    if not journey_enabled("JOURNEY_NOTIFICATIONS_ENABLED"):
        return []
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT action.id, action.version, action.business_id, action.user_id, action.title,
               action.description, action.cta_label, action.due_at,
               preference.telegram_id, preference.notification_preferences_json
        FROM journey_actions action
        JOIN telegramcontrolpreferences preference ON preference.user_id = action.user_id
        WHERE action.status IN ('ready', 'waiting', 'blocked')
          AND action.due_at IS NOT NULL AND action.due_at <= NOW()
          AND NULLIF(BTRIM(CAST(preference.telegram_id AS TEXT)), '') IS NOT NULL
        ORDER BY action.priority DESC, action.due_at
        LIMIT 100
        """
    )
    for value in cursor.fetchall() or []:
        action = _row(cursor, value)
        business_id = str(action.get("business_id") or "")
        if not _tasks_enabled(action.get("notification_preferences_json"), business_id):
            continue
        action_id = str(action.get("id") or "")
        version = int(action.get("version") or 1)
        dedupe_key = hashlib.sha256(f"journey-action:{action_id}:{version}:telegram".encode("utf-8")).hexdigest()
        message = f"ЛокалОС\n\n{action.get('title')}\n\n{action.get('description')}"
        link = f"{MINI_APP_URL}?{urlencode({'screen': 'today', 'item_type': 'journey_action', 'item_id': action_id, 'scope_type': 'business', 'scope_id': business_id})}"
        markup = {"inline_keyboard": [[{"text": str(action.get("cta_label") or "Открыть действие"), "web_app": {"url": link}}]]}
        cursor.execute(
            """
            INSERT INTO journey_action_notification_deliveries (
                dedupe_key, action_id, action_version, user_id, telegram_id, message_text, reply_markup_json
            ) VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON CONFLICT (dedupe_key) DO NOTHING
            """,
            (dedupe_key, action_id, version, action.get("user_id"), str(action.get("telegram_id")), message, Json(markup)),
        )
    cursor.execute(
        """
        SELECT delivery.dedupe_key, delivery.telegram_id, delivery.message_text, delivery.reply_markup_json
        FROM journey_action_notification_deliveries delivery
        JOIN journey_actions action ON action.id = delivery.action_id
        WHERE delivery.sent_at IS NULL
          AND action.version = delivery.action_version
          AND action.status IN ('ready', 'waiting', 'blocked')
        ORDER BY delivery.created_at LIMIT 100
        """
    )
    return [{"dedupe_key": str(item.get("dedupe_key") or ""), "telegram_id": str(item.get("telegram_id") or ""), "message": str(item.get("message_text") or ""), "reply_markup": _json_object(item.get("reply_markup_json"))} for item in (_row(cursor, value) for value in (cursor.fetchall() or []))]


def mark_journey_action_notification_sent(conn: Any, dedupe_key: str) -> bool:
    cursor = conn.cursor()
    cursor.execute("UPDATE journey_action_notification_deliveries SET sent_at = NOW() WHERE dedupe_key = %s AND sent_at IS NULL RETURNING dedupe_key", (dedupe_key,))
    updated = bool(cursor.fetchone())
    conn.commit()
    return updated
