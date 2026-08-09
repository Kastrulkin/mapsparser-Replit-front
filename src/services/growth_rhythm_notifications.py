from __future__ import annotations

import hashlib
import json
import os
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable
from urllib.parse import urlencode

from psycopg2.extras import Json

from services.growth_overview_service import load_growth_overview_for_scope
from services.telegram_control_scope import resolve_control_scope


TELEGRAM_MINI_APP_URL = os.getenv("TELEGRAM_MINI_APP_URL", "https://localos.pro/telegram/control")


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "keys"):
        try:
            return dict(value)
        except Exception:
            return {}
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
        except Exception:
            return {}
    return {}


def _date(value: Any) -> date | None:
    if isinstance(value, datetime):
        return value.astimezone(timezone.utc).date() if value.tzinfo else value.date()
    if isinstance(value, date):
        return value
    if value:
        try:
            return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
        except ValueError:
            return None
    return None


def _due_locations(data_rhythm: dict[str, Any], today: date) -> dict[str, list[dict[str, Any]]]:
    result: dict[str, list[dict[str, Any]]] = {"before_due": [], "overdue": []}
    for item in data_rhythm.get("locations") or []:
        if not isinstance(item, dict):
            continue
        status = str(item.get("status") or "missing")
        due_on = _date(item.get("next_due_at"))
        enriched = {**item, "due_on": due_on.isoformat() if due_on else None}
        if due_on == today + timedelta(days=1):
            result["before_due"].append(enriched)
        elif (due_on and due_on < today and status in {"due", "stale"}) or (not due_on and status == "missing"):
            result["overdue"].append(enriched)
    return result


def _message(scope: dict[str, Any], kind: str, locations: list[dict[str, Any]]) -> str:
    scope_name = str(scope.get("name") or "Бизнес")
    title = "Завтра пора обновить статистику" if kind == "before_due" else "Пора обновить статистику"
    lines = [f"ЛокалОС · {scope_name}", title]
    if len(locations) == 1:
        lines.append(str(locations[0].get("name") or "Точка"))
    else:
        lines.extend(f"• {item.get('name') or 'Точка'}" for item in locations[:10])
        if len(locations) > 10:
            lines.append(f"• ещё {len(locations) - 10}")
    lines.append("Добавьте сводку за неделю — ЛокалОС пересчитает средний чек, допродажи и свободную загрузку.")
    return "\n\n".join(lines)


def collect_due_growth_rhythm_reminders(
    conn: Any,
    *,
    now: datetime | None = None,
    growth_loader: Callable[[dict[str, Any]], dict[str, Any]] = load_growth_overview_for_scope,
) -> list[dict[str, Any]]:
    observed_at = now or datetime.now(timezone.utc)
    today = observed_at.astimezone(timezone.utc).date() if observed_at.tzinfo else observed_at.date()
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT user_id, telegram_id, notification_preferences_json
        FROM telegramcontrolpreferences
        WHERE telegram_id IS NOT NULL
          AND NULLIF(BTRIM(CAST(telegram_id AS TEXT)), '') IS NOT NULL
        """
    )
    for value in cursor.fetchall() or []:
        preference = _row(cursor, value)
        user_id = str(preference.get("user_id") or "")
        telegram_id = str(preference.get("telegram_id") or "")
        notifications = _json_object(preference.get("notification_preferences_json"))
        for preference_key, settings in notifications.items():
            if not isinstance(settings, dict) or not bool(settings.get("finance_rhythm")):
                continue
            kind, separator, scope_id = str(preference_key).partition(":")
            if not separator or kind not in {"business", "network"} or not scope_id:
                continue
            scope = resolve_control_scope(cursor, user_id=user_id, requested_kind=kind, requested_id=scope_id)
            if not scope:
                continue
            try:
                overview = growth_loader(scope)
            except Exception:
                continue
            rhythm = overview.get("data_rhythm") if isinstance(overview.get("data_rhythm"), dict) else {}
            for reminder_kind, locations in _due_locations(rhythm, today).items():
                if not locations:
                    continue
                identity = "|".join(
                    sorted(f"{item.get('location_id')}:{item.get('due_on') or 'missing'}" for item in locations)
                )
                period_key = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:20]
                dedupe_key = f"growth-rhythm:{user_id}:{kind}:{scope_id}:{reminder_kind}:{period_key}"
                link = f"{TELEGRAM_MINI_APP_URL}?{urlencode({'screen': 'finance_import', 'scope_type': kind, 'scope_id': scope_id})}"
                reply_markup = {"inline_keyboard": [[{"text": "Обновить данные", "web_app": {"url": link}}]]}
                cursor.execute(
                    """
                    INSERT INTO growth_rhythm_reminder_deliveries
                        (dedupe_key, user_id, telegram_id, scope_type, scope_id,
                         period_key, reminder_kind, message_text, reply_markup_json)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (dedupe_key) DO NOTHING
                    """,
                    (
                        dedupe_key, user_id, telegram_id, kind, scope_id,
                        period_key, reminder_kind, _message(scope, reminder_kind, locations), Json(reply_markup),
                    ),
                )
    cursor.execute(
        """
        SELECT dedupe_key, telegram_id, message_text, reply_markup_json
        FROM growth_rhythm_reminder_deliveries
        WHERE sent_at IS NULL
        ORDER BY created_at
        LIMIT 100
        """
    )
    return [
        {
            "dedupe_key": str(item.get("dedupe_key") or ""),
            "telegram_id": str(item.get("telegram_id") or ""),
            "message": str(item.get("message_text") or ""),
            "reply_markup": _json_object(item.get("reply_markup_json")),
        }
        for item in (_row(cursor, value) for value in (cursor.fetchall() or []))
    ]


def mark_growth_rhythm_reminder_sent(conn: Any, dedupe_key: str) -> bool:
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE growth_rhythm_reminder_deliveries
        SET sent_at = NOW()
        WHERE dedupe_key = %s AND sent_at IS NULL
        RETURNING dedupe_key
        """,
        (dedupe_key,),
    )
    updated = bool(cursor.fetchone())
    conn.commit()
    return updated
