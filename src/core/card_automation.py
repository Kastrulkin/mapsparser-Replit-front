from __future__ import annotations

import json
import re
import uuid
from datetime import date, datetime, time as dt_time, timedelta, timezone
from typing import Any
from zoneinfo import ZoneInfo

from core.ai_learning import record_ai_learning_event
from services.gigachat_client import analyze_text_with_gigachat


ACTION_NEWS = "news"
ACTION_REVIEW_SYNC = "review_sync"
ACTION_REVIEW_REPLY = "review_reply"

SUPPORTED_ACTIONS = {
    ACTION_NEWS,
    ACTION_REVIEW_SYNC,
    ACTION_REVIEW_REPLY,
}

ACTION_COLUMN_PREFIX = {
    ACTION_NEWS: "news",
    ACTION_REVIEW_SYNC: "review_sync",
    ACTION_REVIEW_REPLY: "review_reply",
}

DEFAULT_TIMEZONE = "Europe/Moscow"
DEFAULT_DIGEST_TIME = "08:00"
WEEKDAY_NAME_MAP = {
    1: "пн",
    2: "вт",
    3: "ср",
    4: "чт",
    5: "пт",
    6: "сб",
    7: "вс",
}


def _row_to_dict(cursor, row) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return row
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


def _table_has_column(cursor, table_name: str, column_name: str) -> bool:
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


def _json_payload(payload: Any) -> str | None:
    if payload is None:
        return None
    try:
        return json.dumps(payload, ensure_ascii=False)
    except Exception:
        return json.dumps({"value": str(payload)}, ensure_ascii=False)


def _now() -> datetime:
    return datetime.utcnow()


def _normalize_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is not None:
            return value.astimezone(timezone.utc).replace(tzinfo=None)
        return value
    try:
        parsed = datetime.fromisoformat(str(value))
        if parsed.tzinfo is not None:
            return parsed.astimezone(timezone.utc).replace(tzinfo=None)
        return parsed
    except Exception:
        return None


def _load_json_if_needed(value: Any) -> Any:
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return value
    return value


def _coerce_schedule_mode(value: Any, default_value: str = "interval") -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"interval", "weekly"}:
        return normalized
    return default_value


def _coerce_schedule_days(value: Any, default_value: list[int] | None = None) -> list[int]:
    payload = _load_json_if_needed(value)
    items: list[int] = []
    if isinstance(payload, (list, tuple, set)):
        source_items = list(payload)
    elif isinstance(payload, str):
        source_items = [part.strip() for part in payload.split(",") if part.strip()]
    else:
        source_items = []
    for item in source_items:
        try:
            day = int(item)
        except (TypeError, ValueError):
            continue
        if 1 <= day <= 7 and day not in items:
            items.append(day)
    if items:
        return sorted(items)
    return list(default_value or [])


def _coerce_time_text(value: Any, default_value: str) -> str:
    raw = str(value or "").strip()
    if not raw:
        return default_value
    match = re.match(r"^([01]?\d|2[0-3]):([0-5]\d)$", raw)
    if not match:
        return default_value
    return f"{int(match.group(1)):02d}:{match.group(2)}"


def _coerce_reply_trigger(value: Any, default_value: str = "schedule") -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"schedule", "after_review_sync"}:
        return normalized
    return default_value


def _zoneinfo(timezone_name: str | None) -> ZoneInfo:
    try:
        return ZoneInfo(str(timezone_name or "").strip() or DEFAULT_TIMEZONE)
    except Exception:
        return ZoneInfo(DEFAULT_TIMEZONE)


def _parse_time_value(time_text: str) -> dt_time:
    normalized = _coerce_time_text(time_text, DEFAULT_DIGEST_TIME)
    hour_text, minute_text = normalized.split(":", 1)
    return dt_time(hour=int(hour_text), minute=int(minute_text))


def _business_timezone_name(conn, business_id: str) -> str:
    cursor = conn.cursor()
    if not _table_has_column(cursor, "businesses", "timezone"):
        return DEFAULT_TIMEZONE
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT timezone
        FROM businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    row = cursor.fetchone()
    if not row:
        return DEFAULT_TIMEZONE
    if isinstance(row, (list, tuple)):
        value = row[0]
    elif isinstance(row, dict):
        value = row.get("timezone")
    else:
        try:
            value = row["timezone"]
        except Exception:
            value = None
    tz_name = str(value or "").strip()
    return tz_name or DEFAULT_TIMEZONE


def _compute_weekly_next_run(now_utc: datetime, timezone_name: str, weekdays: list[int], time_text: str) -> datetime:
    tz = _zoneinfo(timezone_name)
    now_local = now_utc.replace(tzinfo=timezone.utc).astimezone(tz)
    schedule_time = _parse_time_value(time_text)
    for offset in range(0, 15):
        candidate_date = now_local.date() + timedelta(days=offset)
        if candidate_date.isoweekday() not in weekdays:
            continue
        candidate_local = datetime.combine(candidate_date, schedule_time, tzinfo=tz)
        if candidate_local > now_local + timedelta(seconds=30):
            return candidate_local.astimezone(timezone.utc).replace(tzinfo=None)
    fallback = now_local + timedelta(days=7)
    fallback_local = datetime.combine(fallback.date(), schedule_time, tzinfo=tz)
    return fallback_local.astimezone(timezone.utc).replace(tzinfo=None)


def _compute_next_run_at(
    *,
    now_utc: datetime,
    timezone_name: str,
    enabled: bool,
    schedule_mode: str,
    interval_hours: int,
    schedule_days: list[int],
    schedule_time: str,
    current_enabled: bool,
    current_interval: Any,
    current_mode: Any,
    current_days: Any,
    current_time: Any,
    current_value: Any,
) -> datetime | None:
    if not enabled:
        return None
    normalized_current = _normalize_datetime(current_value)
    if schedule_mode == "weekly":
        current_days_normalized = _coerce_schedule_days(current_days, schedule_days)
        current_time_normalized = _coerce_time_text(current_time, schedule_time)
        schedule_changed = (
            not current_enabled
            or str(current_mode or "interval").strip().lower() != "weekly"
            or current_days_normalized != schedule_days
            or current_time_normalized != schedule_time
            or not normalized_current
        )
        if schedule_changed:
            return _compute_weekly_next_run(now_utc, timezone_name, schedule_days, schedule_time)
        return normalized_current
    interval_changed = int(current_interval or interval_hours) != interval_hours or str(current_mode or "interval").strip().lower() != "interval"
    if not current_enabled or interval_changed or not normalized_current:
        return now_utc + timedelta(hours=interval_hours)
    return normalized_current


def _coerce_enabled(value: Any) -> bool:
    return bool(value)


def _coerce_interval_hours(value: Any, default_value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return default_value
    return max(1, min(parsed, 24 * 30))


def ensure_card_automation_tables(conn) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS businesscardautomationsettings (
            business_id TEXT PRIMARY KEY REFERENCES businesses(id) ON DELETE CASCADE,
            news_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            news_interval_hours INTEGER NOT NULL DEFAULT 168,
            news_schedule_mode TEXT NOT NULL DEFAULT 'interval',
            news_schedule_days JSONB,
            news_schedule_time TEXT,
            news_content_source TEXT NOT NULL DEFAULT 'services',
            news_next_run_at TIMESTAMPTZ,
            news_last_run_at TIMESTAMPTZ,
            news_last_status TEXT,
            review_sync_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            review_sync_interval_hours INTEGER NOT NULL DEFAULT 24,
            review_sync_schedule_mode TEXT NOT NULL DEFAULT 'interval',
            review_sync_schedule_days JSONB,
            review_sync_schedule_time TEXT,
            review_sync_next_run_at TIMESTAMPTZ,
            review_sync_last_run_at TIMESTAMPTZ,
            review_sync_last_status TEXT,
            review_reply_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            review_reply_interval_hours INTEGER NOT NULL DEFAULT 24,
            review_reply_trigger TEXT NOT NULL DEFAULT 'schedule',
            review_reply_next_run_at TIMESTAMPTZ,
            review_reply_last_run_at TIMESTAMPTZ,
            review_reply_last_status TEXT,
            digest_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            digest_time TEXT NOT NULL DEFAULT '08:00',
            digest_last_sent_on DATE,
            created_by TEXT,
            updated_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS businesscardautomationevents (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            action_type TEXT NOT NULL,
            status TEXT NOT NULL,
            triggered_by TEXT NOT NULL DEFAULT 'scheduler',
            message TEXT,
            payload_json JSONB,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_businesscardautomationevents_business_created
        ON businesscardautomationevents(business_id, created_at DESC)
        """
    )
    cursor.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS news_schedule_mode TEXT NOT NULL DEFAULT 'interval'")
    cursor.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS news_schedule_days JSONB")
    cursor.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS news_schedule_time TEXT")
    cursor.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS news_content_source TEXT NOT NULL DEFAULT 'services'")
    cursor.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS review_sync_schedule_mode TEXT NOT NULL DEFAULT 'interval'")
    cursor.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS review_sync_schedule_days JSONB")
    cursor.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS review_sync_schedule_time TEXT")
    cursor.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS review_reply_trigger TEXT NOT NULL DEFAULT 'schedule'")
    cursor.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS digest_enabled BOOLEAN NOT NULL DEFAULT FALSE")
    cursor.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS digest_time TEXT NOT NULL DEFAULT '08:00'")
    cursor.execute("ALTER TABLE businesscardautomationsettings ADD COLUMN IF NOT EXISTS digest_last_sent_on DATE")
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS reviewreplydrafts (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            review_id TEXT NOT NULL,
            user_id TEXT,
            source TEXT,
            rating INTEGER,
            author_name TEXT,
            review_text TEXT,
            generated_text TEXT NOT NULL,
            edited_text TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            tone TEXT,
            prompt_key TEXT,
            prompt_version TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    cursor.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS idx_reviewreplydrafts_review_unique
        ON reviewreplydrafts(review_id)
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_reviewreplydrafts_business_status
        ON reviewreplydrafts(business_id, status, created_at DESC)
        """
    )
    cursor.execute(
        """
        ALTER TABLE usernews
        ADD COLUMN IF NOT EXISTS business_id TEXT
        """
    )
    cursor.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_usernews_business_created
        ON usernews(business_id, created_at DESC)
        """
    )
    conn.commit()


def _default_settings_payload() -> dict[str, Any]:
    return {
        "business_id": None,
        "news_enabled": False,
        "news_interval_hours": 168,
        "news_schedule_mode": "interval",
        "news_schedule_days": None,
        "news_schedule_time": None,
        "news_content_source": "services",
        "news_next_run_at": None,
        "news_last_run_at": None,
        "news_last_status": None,
        "review_sync_enabled": False,
        "review_sync_interval_hours": 24,
        "review_sync_schedule_mode": "interval",
        "review_sync_schedule_days": None,
        "review_sync_schedule_time": None,
        "review_sync_next_run_at": None,
        "review_sync_last_run_at": None,
        "review_sync_last_status": None,
        "review_reply_enabled": False,
        "review_reply_interval_hours": 24,
        "review_reply_trigger": "schedule",
        "review_reply_next_run_at": None,
        "review_reply_last_run_at": None,
        "review_reply_last_status": None,
        "digest_enabled": False,
        "digest_time": DEFAULT_DIGEST_TIME,
        "digest_last_sent_on": None,
        "created_at": None,
        "updated_at": None,
    }


def _load_settings_row(conn, business_id: str) -> dict[str, Any]:
    ensure_card_automation_tables(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM businesscardautomationsettings
        WHERE business_id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    row = _row_to_dict(cursor, cursor.fetchone())
    payload = _default_settings_payload()
    payload["business_id"] = business_id
    if row:
        payload.update(row)
    return payload


def _ensure_settings_row(conn, business_id: str) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO businesscardautomationsettings (business_id, created_at, updated_at)
        VALUES (%s, NOW(), NOW())
        ON CONFLICT (business_id) DO NOTHING
        """,
        (business_id,),
    )


def _event_counts(conn, business_id: str) -> dict[str, int]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM usernews
        WHERE business_id = %s
          AND COALESCE(approved, 0) = 0
        """,
        (business_id,),
    )
    news_row = _row_to_dict(cursor, cursor.fetchone()) or {}
    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM reviewreplydrafts
        WHERE business_id = %s
          AND status = 'draft'
        """,
        (business_id,),
    )
    reply_row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return {
        "pending_news_drafts": int(news_row.get("cnt") or 0),
        "pending_review_reply_drafts": int(reply_row.get("cnt") or 0),
    }


def _recent_events(conn, business_id: str, limit: int = 10) -> list[dict[str, Any]]:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, action_type, status, triggered_by, message, payload_json, created_at
        FROM businesscardautomationevents
        WHERE business_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (business_id, limit),
    )
    items: list[dict[str, Any]] = []
    for row in cursor.fetchall() or []:
        rd = _row_to_dict(cursor, row) or {}
        payload = rd.get("payload_json")
        if isinstance(payload, str):
            try:
                payload = json.loads(payload)
            except Exception:
                payload = {"raw": payload}
        items.append(
            {
                "id": rd.get("id"),
                "action_type": rd.get("action_type"),
                "status": rd.get("status"),
                "triggered_by": rd.get("triggered_by"),
                "message": rd.get("message"),
                "payload_json": payload,
                "created_at": rd.get("created_at"),
            }
        )
    return items


def get_card_automation_snapshot(conn, business_id: str) -> dict[str, Any]:
    settings = _load_settings_row(conn, business_id)
    return {
        "settings": settings,
        "counters": _event_counts(conn, business_id),
        "recent_events": _recent_events(conn, business_id, limit=12),
    }


def save_card_automation_settings(conn, business_id: str, actor_user_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    ensure_card_automation_tables(conn)
    current = _load_settings_row(conn, business_id)
    now = _now()
    timezone_name = _business_timezone_name(conn, business_id)

    news_enabled = _coerce_enabled(payload.get("news_enabled"))
    review_sync_enabled = _coerce_enabled(payload.get("review_sync_enabled"))
    review_reply_enabled = _coerce_enabled(payload.get("review_reply_enabled"))
    digest_enabled = _coerce_enabled(payload.get("digest_enabled"))

    news_interval_hours = _coerce_interval_hours(payload.get("news_interval_hours"), 168)
    review_sync_interval_hours = _coerce_interval_hours(payload.get("review_sync_interval_hours"), 24)
    review_reply_interval_hours = _coerce_interval_hours(payload.get("review_reply_interval_hours"), 24)
    news_schedule_mode = _coerce_schedule_mode(payload.get("news_schedule_mode"), str(current.get("news_schedule_mode") or "interval"))
    review_sync_schedule_mode = _coerce_schedule_mode(payload.get("review_sync_schedule_mode"), str(current.get("review_sync_schedule_mode") or "interval"))
    news_schedule_days = _coerce_schedule_days(payload.get("news_schedule_days"), [3] if news_schedule_mode == "weekly" else [])
    review_sync_schedule_days = _coerce_schedule_days(payload.get("review_sync_schedule_days"), [1, 3] if review_sync_schedule_mode == "weekly" else [])
    news_schedule_time = _coerce_time_text(payload.get("news_schedule_time"), "09:00")
    review_sync_schedule_time = _coerce_time_text(payload.get("review_sync_schedule_time"), "08:30")
    review_reply_trigger = _coerce_reply_trigger(payload.get("review_reply_trigger"), str(current.get("review_reply_trigger") or "schedule"))
    digest_time = _coerce_time_text(payload.get("digest_time"), str(current.get("digest_time") or DEFAULT_DIGEST_TIME or DEFAULT_DIGEST_TIME))
    news_content_source = str(payload.get("news_content_source") or current.get("news_content_source") or "services").strip().lower() or "services"

    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO businesscardautomationsettings (
            business_id,
            news_enabled,
            news_interval_hours,
            news_schedule_mode,
            news_schedule_days,
            news_schedule_time,
            news_content_source,
            news_next_run_at,
            review_sync_enabled,
            review_sync_interval_hours,
            review_sync_schedule_mode,
            review_sync_schedule_days,
            review_sync_schedule_time,
            review_sync_next_run_at,
            review_reply_enabled,
            review_reply_interval_hours,
            review_reply_trigger,
            review_reply_next_run_at,
            digest_enabled,
            digest_time,
            created_by,
            updated_by,
            created_at,
            updated_at
        )
        VALUES (
            %s, %s, %s, %s, %s::jsonb, %s, %s, %s,
            %s, %s, %s, %s::jsonb, %s, %s,
            %s, %s, %s, %s,
            %s, %s,
            %s, %s, NOW(), NOW()
        )
        ON CONFLICT (business_id) DO UPDATE
        SET news_enabled = EXCLUDED.news_enabled,
            news_interval_hours = EXCLUDED.news_interval_hours,
            news_schedule_mode = EXCLUDED.news_schedule_mode,
            news_schedule_days = EXCLUDED.news_schedule_days,
            news_schedule_time = EXCLUDED.news_schedule_time,
            news_content_source = EXCLUDED.news_content_source,
            news_next_run_at = EXCLUDED.news_next_run_at,
            review_sync_enabled = EXCLUDED.review_sync_enabled,
            review_sync_interval_hours = EXCLUDED.review_sync_interval_hours,
            review_sync_schedule_mode = EXCLUDED.review_sync_schedule_mode,
            review_sync_schedule_days = EXCLUDED.review_sync_schedule_days,
            review_sync_schedule_time = EXCLUDED.review_sync_schedule_time,
            review_sync_next_run_at = EXCLUDED.review_sync_next_run_at,
            review_reply_enabled = EXCLUDED.review_reply_enabled,
            review_reply_interval_hours = EXCLUDED.review_reply_interval_hours,
            review_reply_trigger = EXCLUDED.review_reply_trigger,
            review_reply_next_run_at = EXCLUDED.review_reply_next_run_at,
            digest_enabled = EXCLUDED.digest_enabled,
            digest_time = EXCLUDED.digest_time,
            updated_by = EXCLUDED.updated_by,
            updated_at = NOW()
        """,
        (
            business_id,
            news_enabled,
            news_interval_hours,
            news_schedule_mode,
            _json_payload(news_schedule_days),
            news_schedule_time,
            news_content_source,
            _compute_next_run_at(
                now_utc=now,
                timezone_name=timezone_name,
                enabled=news_enabled,
                schedule_mode=news_schedule_mode,
                interval_hours=news_interval_hours,
                schedule_days=news_schedule_days,
                schedule_time=news_schedule_time,
                current_enabled=bool(current.get("news_enabled")),
                current_interval=current.get("news_interval_hours"),
                current_mode=current.get("news_schedule_mode"),
                current_days=current.get("news_schedule_days"),
                current_time=current.get("news_schedule_time"),
                current_value=current.get("news_next_run_at"),
            ),
            review_sync_enabled,
            review_sync_interval_hours,
            review_sync_schedule_mode,
            _json_payload(review_sync_schedule_days),
            review_sync_schedule_time,
            _compute_next_run_at(
                now_utc=now,
                timezone_name=timezone_name,
                enabled=review_sync_enabled,
                schedule_mode=review_sync_schedule_mode,
                interval_hours=review_sync_interval_hours,
                schedule_days=review_sync_schedule_days,
                schedule_time=review_sync_schedule_time,
                current_enabled=bool(current.get("review_sync_enabled")),
                current_interval=current.get("review_sync_interval_hours"),
                current_mode=current.get("review_sync_schedule_mode"),
                current_days=current.get("review_sync_schedule_days"),
                current_time=current.get("review_sync_schedule_time"),
                current_value=current.get("review_sync_next_run_at"),
            ),
            review_reply_enabled,
            review_reply_interval_hours,
            review_reply_trigger,
            _compute_next_run_at(
                now_utc=now,
                timezone_name=timezone_name,
                enabled=review_reply_enabled,
                schedule_mode="interval",
                interval_hours=review_reply_interval_hours,
                schedule_days=[],
                schedule_time="09:00",
                current_enabled=bool(current.get("review_reply_enabled")),
                current_interval=current.get("review_reply_interval_hours"),
                current_mode="interval",
                current_days=[],
                current_time="09:00",
                current_value=None if review_reply_trigger == "after_review_sync" else current.get("review_reply_next_run_at"),
            ) if review_reply_trigger != "after_review_sync" else None,
            digest_enabled,
            digest_time,
            actor_user_id,
            actor_user_id,
        ),
    )
    conn.commit()
    return get_card_automation_snapshot(conn, business_id)


def _record_event(
    conn,
    *,
    business_id: str,
    action_type: str,
    status: str,
    triggered_by: str,
    message: str,
    payload: Any = None,
) -> None:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO businesscardautomationevents (
            id, business_id, action_type, status, triggered_by, message, payload_json, created_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, NOW())
        """,
        (
            str(uuid.uuid4()),
            business_id,
            action_type,
            status,
            triggered_by,
            message,
            _json_payload(payload),
        ),
    )


def _update_action_runtime(
    conn,
    *,
    business_id: str,
    action_type: str,
    status: str,
    interval_hours: int,
) -> None:
    prefix = ACTION_COLUMN_PREFIX[action_type]
    settings = _load_settings_row(conn, business_id)
    timezone_name = _business_timezone_name(conn, business_id)
    schedule_mode = str(settings.get(f"{prefix}_schedule_mode") or "interval").strip().lower()
    schedule_days = _coerce_schedule_days(settings.get(f"{prefix}_schedule_days"))
    schedule_time = _coerce_time_text(settings.get(f"{prefix}_schedule_time"), "09:00" if action_type == ACTION_NEWS else "08:30")
    reply_trigger = str(settings.get("review_reply_trigger") or "schedule").strip().lower()
    if action_type == ACTION_REVIEW_REPLY and reply_trigger == "after_review_sync":
        next_run_at = None
    elif schedule_mode == "weekly" and schedule_days:
        next_run_at = _compute_weekly_next_run(_now(), timezone_name, schedule_days, schedule_time)
    else:
        next_hours = interval_hours if status != "error" else min(max(1, interval_hours), 6)
        next_run_at = _now() + timedelta(hours=next_hours)
    cursor = conn.cursor()
    cursor.execute(
        f"""
        UPDATE businesscardautomationsettings
        SET {prefix}_last_run_at = NOW(),
            {prefix}_last_status = %s,
            {prefix}_next_run_at = %s,
            updated_at = NOW()
        WHERE business_id = %s
        """,
        (status, next_run_at, business_id),
    )


def _business_context(conn, business_id: str) -> dict[str, Any]:
    cursor = conn.cursor()
    language_select = (
        "ai_agent_language AS language,"
        if _table_has_column(cursor, "businesses", "ai_agent_language")
        else ("language," if _table_has_column(cursor, "businesses", "language") else "'ru' AS language,")
    )
    cursor.execute(
        f"""
        SELECT id, owner_id, name, {language_select} address
        FROM businesses
        WHERE id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    row = _row_to_dict(cursor, cursor.fetchone())
    if not row:
        raise ValueError("Бизнес не найден")
    return row


def _prompt_from_db(conn, prompt_type: str, fallback: str) -> str:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT prompt_text
        FROM aiprompts
        WHERE prompt_type = %s
        LIMIT 1
        """,
        (prompt_type,),
    )
    row = cursor.fetchone()
    if not row:
        return fallback
    if isinstance(row, (list, tuple)):
        value = row[0]
    elif isinstance(row, dict):
        value = row.get("prompt_text")
    else:
        try:
            value = row["prompt_text"]
        except Exception:
            value = fallback
    text = str(value or "").strip()
    return text or fallback


def _extract_json_field(raw_text: Any, field_name: str) -> str:
    text = str(raw_text or "").strip()
    if not text:
        return ""
    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            value = parsed.get(field_name)
            return str(value or "").strip()
    except Exception:
        pass
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx != -1 and end_idx > start_idx:
        try:
            parsed = json.loads(text[start_idx : end_idx + 1])
            if isinstance(parsed, dict):
                value = parsed.get(field_name)
                return str(value or "").strip()
        except Exception:
            pass
    match = re.search(rf'"{re.escape(field_name)}"\s*:\s*"(.*)"', text, re.DOTALL)
    if match:
        return str(match.group(1) or "").strip()
    return text


def _load_user_examples(conn, user_id: str, example_type: str, limit: int = 5) -> str:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT example_text
        FROM userexamples
        WHERE user_id = %s
          AND example_type = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (user_id, example_type, limit),
    )
    items: list[str] = []
    for row in cursor.fetchall() or []:
        if isinstance(row, (list, tuple)):
            text = row[0]
        elif isinstance(row, dict):
            text = row.get("example_text")
        else:
            try:
                text = row["example_text"]
            except Exception:
                text = ""
        normalized = str(text or "").strip()
        if normalized:
            items.append(normalized)
    return "\n".join(items)


def _service_context(conn, business_id: str, limit: int = 5) -> str:
    cursor = conn.cursor()
    if _table_has_column(cursor, "userservices", "business_id"):
        cursor.execute(
            """
            SELECT name, description
            FROM userservices
            WHERE business_id = %s
            ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
            LIMIT %s
            """,
            (business_id, limit),
        )
    else:
        cursor.execute(
            """
            SELECT s.name, s.description
            FROM userservices s
            JOIN businesses b ON b.owner_id = s.user_id
            WHERE b.id = %s
            ORDER BY s.updated_at DESC NULLS LAST, s.created_at DESC NULLS LAST
            LIMIT %s
            """,
            (business_id, limit),
        )
    chunks: list[str] = []
    for row in cursor.fetchall() or []:
        if isinstance(row, (list, tuple)):
            name, description = row[0], row[1] if len(row) > 1 else ""
        else:
            name = row.get("name")
            description = row.get("description")
        name_text = str(name or "").strip()
        description_text = str(description or "").strip()
        if not name_text:
            continue
        if description_text:
            chunks.append(f"{name_text}: {description_text}")
        else:
            chunks.append(name_text)
    return "\n".join(chunks)


def _latest_transaction_context(conn, user_id: str) -> str:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT transaction_date, amount, services, notes
        FROM financialtransactions
        WHERE user_id = %s
        ORDER BY transaction_date DESC NULLS LAST, created_at DESC NULLS LAST
        LIMIT 1
        """,
        (user_id,),
    )
    row = cursor.fetchone()
    if not row:
        return ""
    if isinstance(row, (list, tuple)):
        transaction_date, amount, services_raw, notes = row
    else:
        transaction_date = row.get("transaction_date")
        amount = row.get("amount")
        services_raw = row.get("services")
        notes = row.get("notes")
    services_list: list[str] = []
    if services_raw:
        try:
            parsed = json.loads(services_raw) if isinstance(services_raw, str) else services_raw
            if isinstance(parsed, list):
                services_list = [str(item or "").strip() for item in parsed if str(item or "").strip()]
        except Exception:
            services_list = []
    services_text = ", ".join(services_list) if services_list else "Услуги"
    parts = [f"Последняя выполненная работа: {services_text}."]
    if transaction_date:
        parts.append(f"Дата: {transaction_date}.")
    if amount:
        parts.append(f"Сумма: {amount}.")
    if notes:
        parts.append(str(notes).strip())
    return " ".join(part for part in parts if part).strip()


def _map_link_for_business(conn, business_id: str) -> str:
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT url
        FROM businessmaplinks
        WHERE business_id = %s
          AND url IS NOT NULL
          AND BTRIM(url) <> ''
        ORDER BY CASE map_type
            WHEN 'yandex' THEN 1
            WHEN '2gis' THEN 2
            WHEN 'google' THEN 3
            WHEN 'apple' THEN 4
            ELSE 9
        END, created_at DESC NULLS LAST
        LIMIT 1
        """,
        (business_id,),
    )
    row = cursor.fetchone()
    if not row:
        return ""
    if isinstance(row, (list, tuple)):
        return str(row[0] or "").strip()
    if isinstance(row, dict):
        return str(row.get("url") or "").strip()
    try:
        return str(row["url"] or "").strip()
    except Exception:
        return ""


def _generate_news_for_business(conn, business_id: str) -> dict[str, Any]:
    ctx = _business_context(conn, business_id)
    owner_id = str(ctx.get("owner_id") or "").strip()
    if not owner_id:
        raise ValueError("У бизнеса не найден owner_id")
    business_name = str(ctx.get("name") or "Бизнес").strip() or "Бизнес"
    language = str(ctx.get("language") or "ru").strip() or "ru"
    language_names = {
        "ru": "Russian",
        "en": "English",
        "es": "Spanish",
        "de": "German",
        "fr": "French",
        "it": "Italian",
        "pt": "Portuguese",
        "zh": "Chinese",
        "tr": "Turkish",
        "ar": "Arabic",
    }
    settings = _load_settings_row(conn, business_id)
    news_content_source = str(settings.get("news_content_source") or "services").strip().lower() or "services"
    service_text = _service_context(conn, business_id, limit=5)
    transaction_text = _latest_transaction_context(conn, owner_id)
    news_examples = _load_user_examples(conn, owner_id, "news", limit=5)
    raw_info = (
        f"Регулярный черновик для карточки бизнеса {business_name}. "
        "Нужен короткий нейтральный апдейт для карт, без выдуманных акций и обещаний."
    )
    if news_content_source == "services":
        raw_info += " Основу новости нужно брать из услуг бизнеса, если не указано иное."
    default_prompt = """Ты - маркетолог локального бизнеса. Сгенерируй короткую новость для публикации на картах.
Требования: до 1200 символов, без хештегов, без конкурентов, без выдуманных фактов.
Write all generated text in {language_name}.
Верни СТРОГО JSON: {{"news": "текст новости"}}

Бизнес: {business_name}
Контекст услуг:
{service_context}

Контекст последней работы/транзакции:
{transaction_context}

Свободный контекст:
{raw_info}

Если есть, ориентируйся на стиль этих примеров:
{news_examples}
"""
    prompt_template = _prompt_from_db(conn, "news_generation", default_prompt)
    prompt = prompt_template.format(
        language_name=language_names.get(language, "Russian"),
        business_name=business_name,
        service_context=service_text or "Нет уточнённых услуг",
        transaction_context=transaction_text or "Нет данных",
        raw_info=raw_info,
        news_examples=news_examples or "Примеров нет",
    )
    generated = analyze_text_with_gigachat(
        prompt,
        task_type="news_generation",
        business_id=business_id,
        user_id=owner_id,
    )
    generated_text = _extract_json_field(generated, "news").strip()
    if not generated_text:
        raise ValueError("AI не вернул текст новости")
    cursor = conn.cursor()
    has_business_id = _table_has_column(cursor, "usernews", "business_id")
    news_id = str(uuid.uuid4())
    if has_business_id:
        cursor.execute(
            """
            INSERT INTO usernews (
                id, user_id, business_id, service_id, source_text, generated_text,
                original_generated_text, edited_before_approve, approved, prompt_key, prompt_version, created_at
            )
            VALUES (%s, %s, %s, NULL, %s, %s, %s, FALSE, 0, %s, %s, NOW())
            """,
            (
                news_id,
                owner_id,
                business_id,
                "scheduled_card_automation",
                generated_text,
                generated_text,
                "news_generation_auto",
                "v1",
            ),
        )
    else:
        cursor.execute(
            """
            INSERT INTO usernews (
                id, user_id, service_id, source_text, generated_text,
                original_generated_text, edited_before_approve, approved, prompt_key, prompt_version, created_at
            )
            VALUES (%s, %s, NULL, %s, %s, %s, FALSE, 0, %s, %s, NOW())
            """,
            (
                news_id,
                owner_id,
                "scheduled_card_automation",
                generated_text,
                generated_text,
                "news_generation_auto",
                "v1",
            ),
        )
    record_ai_learning_event(
        capability="news.generate",
        event_type="generated",
        intent="operations",
        user_id=owner_id,
        business_id=business_id,
        prompt_key="news_generation_auto",
        prompt_version="v1",
        draft_text=generated_text,
        metadata={"source": "card_automation"},
    )
    return {"news_id": news_id, "generated_text": generated_text}


def _generate_review_reply_drafts(conn, business_id: str, batch_size: int = 5) -> dict[str, Any]:
    ctx = _business_context(conn, business_id)
    owner_id = str(ctx.get("owner_id") or "").strip()
    if not owner_id:
        raise ValueError("У бизнеса не найден owner_id")
    language = str(ctx.get("language") or "ru").strip() or "ru"
    language_names = {
        "ru": "Russian",
        "en": "English",
        "es": "Spanish",
        "de": "German",
        "fr": "French",
        "it": "Italian",
        "pt": "Portuguese",
        "zh": "Chinese",
        "tr": "Turkish",
        "ar": "Arabic",
    }
    examples_text = _load_user_examples(conn, owner_id, "review", limit=5)
    default_prompt = """Ты - вежливый менеджер локального бизнеса. Сгенерируй короткий ответ на отзыв.
Тон: {tone}. До 250 символов. Без лишних обещаний и без выдуманных деталей.
Write the reply in {language_name}.
Верни СТРОГО JSON: {{"reply": "текст ответа"}}

Примеры стиля:
{examples_text}

Отзыв клиента:
{review_text}
"""
    prompt_template = _prompt_from_db(conn, "review_reply", default_prompt)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT r.id, r.source, r.rating, r.author_name, r.text, r.published_at
        FROM externalbusinessreviews r
        LEFT JOIN reviewreplydrafts d ON d.review_id = r.id
        WHERE r.business_id = %s
          AND COALESCE(BTRIM(r.response_text), '') = ''
          AND COALESCE(BTRIM(r.text), '') <> ''
          AND d.id IS NULL
        ORDER BY COALESCE(r.published_at, r.created_at) DESC, r.created_at DESC
        LIMIT %s
        """,
        (business_id, batch_size),
    )
    rows = cursor.fetchall() or []
    created_items: list[dict[str, Any]] = []
    for row in rows:
        rd = _row_to_dict(cursor, row) or {}
        review_text = str(rd.get("text") or "").strip()
        if not review_text:
            continue
        prompt = prompt_template.format(
            tone="professional",
            language_name=language_names.get(language, "Russian"),
            examples_text=examples_text or "Примеров нет",
            review_text=review_text[:1000],
            seo_keywords="",
            seo_keywords_top10="",
        )
        generated = analyze_text_with_gigachat(
            prompt,
            task_type="review_reply",
            business_id=business_id,
            user_id=owner_id,
        )
        generated_text = _extract_json_field(generated, "reply").strip()
        if not generated_text:
            continue
        draft_id = str(uuid.uuid4())
        cursor.execute(
            """
            INSERT INTO reviewreplydrafts (
                id, business_id, review_id, user_id, source, rating, author_name, review_text,
                generated_text, status, tone, prompt_key, prompt_version, created_at, updated_at
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', %s, %s, %s, NOW(), NOW())
            ON CONFLICT (review_id) DO NOTHING
            """,
            (
                draft_id,
                business_id,
                rd.get("id"),
                owner_id,
                rd.get("source"),
                rd.get("rating"),
                rd.get("author_name"),
                review_text,
                generated_text,
                "professional",
                "review_reply_auto",
                "v1",
            ),
        )
        if cursor.rowcount <= 0:
            continue
        created_items.append(
            {
                "draft_id": draft_id,
                "review_id": rd.get("id"),
                "author_name": rd.get("author_name"),
            }
        )
        record_ai_learning_event(
            capability="reviews.reply",
            event_type="generated",
            intent="operations",
            user_id=owner_id,
            business_id=business_id,
            prompt_key="review_reply_auto",
            prompt_version="v1",
            draft_text=generated_text,
            metadata={"source": "card_automation", "review_id": rd.get("id")},
        )
    return {"created_count": len(created_items), "items": created_items}


def _enqueue_review_sync(conn, business_id: str) -> dict[str, Any]:
    ctx = _business_context(conn, business_id)
    owner_id = str(ctx.get("owner_id") or "").strip()
    if not owner_id:
        raise ValueError("У бизнеса не найден owner_id")
    source_url = _map_link_for_business(conn, business_id)
    if not source_url:
        raise ValueError("Для бизнеса не найдена ссылка на карту")
    from api.admin_prospecting import _enqueue_parse_task_for_business

    task = _enqueue_parse_task_for_business(business_id, owner_id, source_url)
    return {
        "task_id": task.get("id"),
        "existing": bool(task.get("existing")),
        "source": task.get("source"),
        "task_type": task.get("task_type"),
        "source_url": source_url,
    }


def run_card_automation_action(
    conn,
    *,
    business_id: str,
    action_type: str,
    triggered_by: str = "scheduler",
) -> dict[str, Any]:
    ensure_card_automation_tables(conn)
    _ensure_settings_row(conn, business_id)
    if action_type not in SUPPORTED_ACTIONS:
        raise ValueError(f"Unsupported action_type: {action_type}")

    settings = _load_settings_row(conn, business_id)
    interval_hours = int(settings.get(f"{ACTION_COLUMN_PREFIX[action_type]}_interval_hours") or 24)
    result_status = "success"
    result_message = ""
    result_payload: dict[str, Any] | None = None

    try:
        if action_type == ACTION_REVIEW_SYNC:
            result_payload = _enqueue_review_sync(conn, business_id)
            if result_payload.get("existing"):
                result_status = "noop"
                result_message = "Задача синхронизации уже есть в очереди"
            else:
                result_message = "Синхронизация отзывов поставлена в очередь"
        elif action_type == ACTION_NEWS:
            result_payload = _generate_news_for_business(conn, business_id)
            result_message = "Черновик новости создан"
        elif action_type == ACTION_REVIEW_REPLY:
            result_payload = _generate_review_reply_drafts(conn, business_id, batch_size=5)
            created_count = int(result_payload.get("created_count") or 0)
            if created_count <= 0:
                result_status = "noop"
                result_message = "Новых отзывов без draft-ответов не найдено"
            else:
                result_message = f"Подготовлено draft-ответов: {created_count}"

        _record_event(
            conn,
            business_id=business_id,
            action_type=action_type,
            status=result_status,
            triggered_by=triggered_by,
            message=result_message,
            payload=result_payload,
        )
        _update_action_runtime(
            conn,
            business_id=business_id,
            action_type=action_type,
            status=result_status,
            interval_hours=interval_hours,
        )
        conn.commit()
        return {
            "success": True,
            "status": result_status,
            "message": result_message,
            "payload": result_payload,
        }
    except Exception as exc:
        error_message = str(exc or "").strip() or "automation_error"
        try:
            conn.rollback()
        except Exception:
            pass
        try:
            _record_event(
                conn,
                business_id=business_id,
                action_type=action_type,
                status="error",
                triggered_by=triggered_by,
                message=error_message,
                payload={"error": error_message},
            )
            _update_action_runtime(
                conn,
                business_id=business_id,
                action_type=action_type,
                status="error",
                interval_hours=interval_hours,
            )
            conn.commit()
        except Exception:
            try:
                conn.rollback()
            except Exception:
                pass
        return {
            "success": False,
            "status": "error",
            "message": error_message,
            "payload": {"error": error_message},
        }


def run_due_card_automation(conn, batch_size: int = 20) -> dict[str, Any]:
    ensure_card_automation_tables(conn)
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT *
        FROM businesscardautomationsettings
        WHERE news_enabled = TRUE
           OR review_sync_enabled = TRUE
           OR review_reply_enabled = TRUE
        ORDER BY updated_at ASC NULLS FIRST
        LIMIT %s
        """,
        (batch_size,),
    )
    rows = cursor.fetchall() or []
    now = _now()
    processed = 0
    success = 0
    noop = 0
    errors = 0
    details: list[dict[str, Any]] = []
    for row in rows:
        settings = _row_to_dict(cursor, row) or {}
        business_id = str(settings.get("business_id") or "").strip()
        if not business_id:
            continue
        due_actions: list[str] = []
        for action_type, prefix in ACTION_COLUMN_PREFIX.items():
            enabled = bool(settings.get(f"{prefix}_enabled"))
            if not enabled:
                continue
            next_run_at = _normalize_datetime(settings.get(f"{prefix}_next_run_at"))
            reply_trigger = str(settings.get("review_reply_trigger") or "schedule").strip().lower()
            if action_type == ACTION_REVIEW_REPLY and reply_trigger == "after_review_sync":
                continue
            if not next_run_at or next_run_at <= now:
                due_actions.append(action_type)
        for action_type in due_actions:
            processed += 1
            result = run_card_automation_action(
                conn,
                business_id=business_id,
                action_type=action_type,
                triggered_by="scheduler",
            )
            if result.get("status") == "success":
                success += 1
            elif result.get("status") == "noop":
                noop += 1
            else:
                errors += 1
            details.append(
                {
                    "business_id": business_id,
                    "action_type": action_type,
                    "status": result.get("status"),
                    "message": result.get("message"),
                }
            )
    return {
        "processed": processed,
        "success": success,
        "noop": noop,
        "errors": errors,
        "details": details,
    }


def handle_review_sync_completion(conn, business_id: str, triggered_by: str = "parser") -> dict[str, Any] | None:
    ensure_card_automation_tables(conn)
    settings = _load_settings_row(conn, business_id)
    if not bool(settings.get("review_sync_enabled")):
        return None

    _record_event(
        conn,
        business_id=business_id,
        action_type=ACTION_REVIEW_SYNC,
        status="success",
        triggered_by=triggered_by,
        message="Синхронизация отзывов завершена",
        payload={"business_id": business_id},
    )
    conn.commit()

    if not bool(settings.get("review_reply_enabled")):
        return None
    if str(settings.get("review_reply_trigger") or "schedule").strip().lower() != "after_review_sync":
        return None
    return run_card_automation_action(
        conn,
        business_id=business_id,
        action_type=ACTION_REVIEW_REPLY,
        triggered_by="review_sync_completed",
    )


def _action_planned_for_local_day(settings: dict[str, Any], action_type: str, local_today: date) -> tuple[bool, str]:
    prefix = ACTION_COLUMN_PREFIX[action_type]
    if not bool(settings.get(f"{prefix}_enabled")):
        return False, ""
    if action_type == ACTION_REVIEW_REPLY and str(settings.get("review_reply_trigger") or "schedule").strip().lower() == "after_review_sync":
        if _action_planned_for_local_day(settings, ACTION_REVIEW_SYNC, local_today)[0]:
            return True, "после завершения синхронизации"
        return False, ""
    schedule_mode = str(settings.get(f"{prefix}_schedule_mode") or "interval").strip().lower()
    if schedule_mode == "weekly":
        weekdays = _coerce_schedule_days(settings.get(f"{prefix}_schedule_days"))
        if local_today.isoweekday() not in weekdays:
            return False, ""
        schedule_time = _coerce_time_text(settings.get(f"{prefix}_schedule_time"), "09:00" if action_type == ACTION_NEWS else "08:30")
        return True, schedule_time
    next_run_at = _normalize_datetime(settings.get(f"{prefix}_next_run_at"))
    if not next_run_at:
        return False, ""
    return next_run_at.date() == local_today, next_run_at.strftime("%H:%M")


def _action_label(action_type: str) -> str:
    if action_type == ACTION_REVIEW_SYNC:
        return "Собрать новые отзывы"
    if action_type == ACTION_REVIEW_REPLY:
        return "Подготовить draft-ответы на отзывы"
    return "Сгенерировать draft-новость"


def _format_event_line(event: dict[str, Any]) -> str:
    action_label = _action_label(str(event.get("action_type") or ""))
    status = str(event.get("status") or "").strip().lower()
    if status == "error":
        return f"• {action_label}: ошибка — {event.get('message') or 'без деталей'}"
    if status == "noop":
        return f"• {action_label}: без изменений"
    return f"• {action_label}: {event.get('message') or 'выполнено'}"


def collect_due_telegram_digest_messages(conn) -> list[dict[str, Any]]:
    ensure_card_automation_tables(conn)
    cursor = conn.cursor()
    business_timezone_select = (
        "b.timezone AS business_timezone,"
        if _table_has_column(cursor, "businesses", "timezone")
        else f"'{DEFAULT_TIMEZONE}' AS business_timezone,"
    )
    cursor.execute(
        f"""
        SELECT
            s.business_id,
            s.digest_time,
            s.digest_last_sent_on,
            b.name AS business_name,
            {business_timezone_select}
            b.owner_id,
            u.telegram_id,
            u.name AS owner_name
        FROM businesscardautomationsettings s
        JOIN businesses b ON b.id = s.business_id
        JOIN users u ON u.id = b.owner_id
        WHERE s.digest_enabled = TRUE
          AND COALESCE(b.is_active, TRUE) = TRUE
          AND u.telegram_id IS NOT NULL
          AND NULLIF(BTRIM(CAST(u.telegram_id AS TEXT)), '') IS NOT NULL
        ORDER BY u.id, b.name
        """
    )
    rows = cursor.fetchall() or []
    grouped: dict[str, dict[str, Any]] = {}
    now_utc = _now()
    for row in rows:
        rd = _row_to_dict(cursor, row) or {}
        business_id = str(rd.get("business_id") or "").strip()
        owner_id = str(rd.get("owner_id") or "").strip()
        if not business_id or not owner_id:
            continue
        timezone_name = str(rd.get("business_timezone") or DEFAULT_TIMEZONE).strip() or DEFAULT_TIMEZONE
        tz = _zoneinfo(timezone_name)
        now_local = now_utc.replace(tzinfo=timezone.utc).astimezone(tz)
        digest_time = _coerce_time_text(rd.get("digest_time"), DEFAULT_DIGEST_TIME)
        digest_clock = _parse_time_value(digest_time)
        now_local_clock = now_local.timetz().replace(tzinfo=None)
        if now_local_clock < digest_clock:
            continue
        digest_last_sent_on = rd.get("digest_last_sent_on")
        if isinstance(digest_last_sent_on, datetime):
            digest_last_sent_on = digest_last_sent_on.date()
        elif isinstance(digest_last_sent_on, str):
            try:
                digest_last_sent_on = date.fromisoformat(digest_last_sent_on)
            except Exception:
                digest_last_sent_on = None
        if digest_last_sent_on == now_local.date():
            continue

        settings = _load_settings_row(conn, business_id)
        planned_lines: list[str] = []
        for action_type in [ACTION_REVIEW_SYNC, ACTION_REVIEW_REPLY, ACTION_NEWS]:
            planned, when_text = _action_planned_for_local_day(settings, action_type, now_local.date())
            if not planned:
                continue
            if when_text == "после завершения синхронизации":
                planned_lines.append(f"• {_action_label(action_type)} — {when_text}")
            elif when_text:
                planned_lines.append(f"• {when_text} — {_action_label(action_type)}")
            else:
                planned_lines.append(f"• {_action_label(action_type)}")

        recent_events = _recent_events(conn, business_id, limit=20)
        completed_today = []
        for event in recent_events:
            event_dt = _normalize_datetime(event.get("created_at"))
            if not event_dt:
                continue
            event_local = event_dt.replace(tzinfo=timezone.utc).astimezone(tz)
            if event_local.date() != now_local.date():
                continue
            completed_today.append(_format_event_line(event))

        owner_bucket = grouped.setdefault(
            owner_id,
            {
                "owner_id": owner_id,
                "telegram_id": str(rd.get("telegram_id") or "").strip(),
                "owner_name": str(rd.get("owner_name") or "").strip() or "владелец",
                "businesses": [],
            },
        )
        owner_bucket["businesses"].append(
            {
                "business_id": business_id,
                "business_name": str(rd.get("business_name") or "Бизнес").strip() or "Бизнес",
                "planned_lines": planned_lines,
                "completed_lines": completed_today,
                "local_today": now_local.date(),
            }
        )

    messages: list[dict[str, Any]] = []
    for bucket in grouped.values():
        business_sections: list[str] = []
        sent_business_ids: list[str] = []
        sent_date: date | None = None
        for item in bucket["businesses"]:
            sent_business_ids.append(item["business_id"])
            sent_date = item["local_today"]
            planned_block = "\n".join(item["planned_lines"]) if item["planned_lines"] else "• На сегодня действий не запланировано"
            completed_block = "\n".join(item["completed_lines"]) if item["completed_lines"] else "• Сегодня ещё ничего не выполнено"
            business_sections.append(
                f"🏢 {item['business_name']}\n"
                f"План на сегодня:\n{planned_block}\n\n"
                f"Что уже сделано:\n{completed_block}"
            )
        if not business_sections or not sent_date:
            continue
        text = (
            f"Доброе утро. План LocalOS на {sent_date.strftime('%d.%m.%Y')}.\n\n"
            + "\n\n".join(business_sections)
        )
        messages.append(
            {
                "owner_id": bucket["owner_id"],
                "telegram_id": bucket["telegram_id"],
                "message": text,
                "business_ids": sent_business_ids,
                "sent_date": sent_date,
            }
        )
    return messages


def mark_telegram_digest_sent(conn, business_ids: list[str], sent_date: date) -> None:
    if not business_ids:
        return
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE businesscardautomationsettings
        SET digest_last_sent_on = %s,
            updated_at = NOW()
        WHERE business_id = ANY(%s)
        """,
        (sent_date, business_ids),
    )
    conn.commit()
