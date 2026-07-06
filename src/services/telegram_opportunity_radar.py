from __future__ import annotations

import json
import os
import re
import uuid
from datetime import datetime, timezone
from typing import Any

from core.channel_delivery import send_telegram_bot_message


STATUSES = {"new", "useful", "ignored", "answered", "saved_as_content_idea"}

SIGNAL_RULES: tuple[tuple[str, int, tuple[str, ...]], ...] = (
    (
        "sales_request",
        70,
        (
            "посоветуйте",
            "порекомендуйте",
            "ищу",
            "нужен",
            "нужна",
            "кто может",
            "куда обратиться",
            "записаться",
            "стоимость",
            "цена",
            "сколько стоит",
        ),
    ),
    (
        "owner_pain",
        65,
        (
            "налоги",
            "ндс",
            "усн",
            "патент",
            "самозанят",
            "кассовый разрыв",
            "нет мастеров",
            "мастера уходят",
            "клиентов меньше",
            "заявки дорогие",
            "не тяну",
            "выгорание",
        ),
    ),
    (
        "expertise_window",
        55,
        (
            "как вы делаете",
            "как настроить",
            "что работает",
            "какой канал",
            "яндекс карты",
            "2гис",
            "контент",
            "посты",
            "продвижение",
            "маркетинг",
        ),
    ),
    (
        "competitor_signal",
        45,
        (
            "конкуренты",
            "соседний салон",
            "другая студия",
            "увели клиента",
            "демпинг",
            "скидки",
        ),
    ),
)


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    if hasattr(row, "keys"):
        return {key: row[key] for key in row.keys()}
    if hasattr(row, "get"):
        return dict(row)
    columns = [desc[0] for desc in getattr(cursor, "description", [])]
    return dict(zip(columns, row))


def _parse_datetime(value: Any) -> datetime | None:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def score_message(text: str) -> dict[str, Any] | None:
    normalized = re.sub(r"\s+", " ", str(text or "").lower()).strip()
    if len(normalized) < 12:
        return None

    best: dict[str, Any] | None = None
    for signal_type, base_score, markers in SIGNAL_RULES:
        hits = [marker for marker in markers if marker in normalized]
        if not hits:
            continue
        score = min(100, base_score + max(0, len(hits) - 1) * 8)
        candidate = {
            "signal_type": signal_type,
            "score": score,
            "reason": "Найдены маркеры: " + ", ".join(hits[:4]),
        }
        if best is None or candidate["score"] > best["score"]:
            best = candidate
    return best


def build_reply_draft(signal_type: str, text: str) -> str:
    if signal_type == "sales_request":
        return "Можно ответить коротко: уточнить район/услугу, дать полезный критерий выбора и мягко предложить помощь."
    if signal_type == "owner_pain":
        return "Можно ответить как эксперт: назвать проблему, дать один практический шаг и предложить разобрать ситуацию."
    if signal_type == "expertise_window":
        return "Можно показать экспертизу: дать 2-3 конкретных наблюдения без продажи в лоб."
    return "Можно сохранить как идею для поста или ответить с коротким практическим комментарием."


def upsert_source(cursor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    source = payload.get("source") or {}
    account_id = str(payload.get("account_id") or source.get("account_id") or "").strip() or None
    business_id = str(payload.get("business_id") or source.get("business_id") or "").strip()
    if not business_id:
        raise ValueError("business_id is required")
    telegram_chat_id = str(source.get("telegram_chat_id") or source.get("chat_id") or payload.get("telegram_chat_id") or "").strip()
    if not telegram_chat_id:
        raise ValueError("source.telegram_chat_id is required")
    title = str(source.get("title") or payload.get("chat_title") or telegram_chat_id).strip() or telegram_chat_id
    source_type = str(source.get("source_type") or source.get("type") or "chat").strip() or "chat"
    username = str(source.get("telegram_username") or source.get("username") or "").strip().lstrip("@") or None
    monitor_config = source.get("monitor_config") if isinstance(source.get("monitor_config"), dict) else {}
    source_id = str(uuid.uuid4())

    cursor.execute(
        """
        INSERT INTO telegram_opportunity_sources (
            id, business_id, user_id, account_id, source_type, title,
            telegram_chat_id, telegram_username, monitor_config_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (business_id, telegram_chat_id)
        DO UPDATE SET
            title = EXCLUDED.title,
            telegram_username = EXCLUDED.telegram_username,
            source_type = EXCLUDED.source_type,
            monitor_config_json = telegram_opportunity_sources.monitor_config_json || EXCLUDED.monitor_config_json,
            updated_at = NOW()
        RETURNING id, business_id, user_id, account_id, source_type, title,
                  telegram_chat_id, telegram_username, is_active, monitor_config_json,
                  last_message_id, last_checked_at, needs_attention_reason, created_at, updated_at
        """,
        (
            source_id,
            business_id,
            str(payload.get("user_id") or source.get("user_id") or "").strip() or None,
            account_id,
            source_type,
            title,
            telegram_chat_id,
            username,
            json.dumps(monitor_config, ensure_ascii=False),
        ),
    )
    row = cursor.fetchone()
    return _row_to_dict(cursor, row) or {}


def ingest_opportunity(cursor: Any, payload: dict[str, Any]) -> dict[str, Any]:
    source_row = upsert_source(cursor, payload)
    message = payload.get("message") or {}
    text = str(message.get("text") or payload.get("message_text") or "").strip()
    score_payload = {
        "signal_type": payload.get("signal_type"),
        "score": payload.get("score"),
        "reason": payload.get("reason"),
    }
    local_score = score_message(text) or {}
    signal_type = str(score_payload.get("signal_type") or local_score.get("signal_type") or "other")
    score = int(score_payload.get("score") or local_score.get("score") or 0)
    reason = str(score_payload.get("reason") or local_score.get("reason") or "").strip() or None
    if score <= 0:
        return {"created": False, "ignored": True, "reason": "score_below_threshold"}

    business_id = str(payload.get("business_id") or source_row.get("business_id") or "").strip()
    account_id = str(payload.get("account_id") or source_row.get("account_id") or "").strip() or None
    chat_id = str(source_row.get("telegram_chat_id") or payload.get("telegram_chat_id") or "").strip()
    message_id = str(message.get("id") or message.get("message_id") or payload.get("telegram_message_id") or "").strip()
    if not message_id:
        raise ValueError("message.id is required")

    opportunity_id = str(uuid.uuid4())
    raw_payload = payload.get("raw_payload") if isinstance(payload.get("raw_payload"), dict) else payload
    cursor.execute(
        """
        INSERT INTO telegram_opportunities (
            id, business_id, user_id, source_id, account_id, telegram_chat_id,
            telegram_message_id, chat_title, sender_id, message_date, message_text,
            message_link, signal_type, score, reason, reply_draft, raw_payload_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (business_id, account_id, telegram_chat_id, telegram_message_id)
        DO NOTHING
        RETURNING id, business_id, user_id, source_id, account_id, telegram_chat_id,
                  telegram_message_id, chat_title, sender_id, message_date, message_text,
                  message_link, signal_type, score, reason, reply_draft, status,
                  raw_payload_json, alerted_at, created_at, updated_at
        """,
        (
            opportunity_id,
            business_id,
            str(payload.get("user_id") or source_row.get("user_id") or "").strip() or None,
            source_row.get("id"),
            account_id,
            chat_id,
            message_id,
            str(source_row.get("title") or payload.get("chat_title") or chat_id),
            str(message.get("sender_id") or payload.get("sender_id") or "").strip() or None,
            _parse_datetime(message.get("date") or payload.get("message_date")),
            text,
            str(message.get("link") or payload.get("message_link") or "").strip() or None,
            signal_type,
            score,
            reason,
            str(payload.get("reply_draft") or build_reply_draft(signal_type, text)).strip(),
            json.dumps(raw_payload, ensure_ascii=False, default=str),
        ),
    )
    row = cursor.fetchone()
    if not row:
        return {"created": False, "duplicate": True}
    opportunity = _row_to_dict(cursor, row) or {}
    cursor.execute(
        """
        UPDATE telegram_opportunity_sources
        SET last_message_id = %s, last_checked_at = NOW(), updated_at = NOW()
        WHERE id = %s
        """,
        (message_id, source_row.get("id")),
    )
    return {"created": True, "opportunity": serialize_opportunity(opportunity)}


def list_sources(cursor: Any, business_id: str) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, business_id, user_id, account_id, source_type, title,
               telegram_chat_id, telegram_username, is_active, monitor_config_json,
               last_message_id, last_checked_at, needs_attention_reason, created_at, updated_at
        FROM telegram_opportunity_sources
        WHERE business_id = %s
        ORDER BY is_active DESC, updated_at DESC NULLS LAST, title ASC
        """,
        (business_id,),
    )
    return [serialize_source(_row_to_dict(cursor, row) or {}) for row in cursor.fetchall() or []]


def list_opportunities(cursor: Any, business_id: str, *, status: str | None = None, limit: int = 50) -> list[dict[str, Any]]:
    params: list[Any] = [business_id]
    where = "business_id = %s"
    if status and status in STATUSES:
        where += " AND status = %s"
        params.append(status)
    params.append(max(1, min(int(limit or 50), 200)))
    cursor.execute(
        f"""
        SELECT id, business_id, user_id, source_id, account_id, telegram_chat_id,
               telegram_message_id, chat_title, sender_id, message_date, message_text,
               message_link, signal_type, score, reason, reply_draft, status,
               raw_payload_json, alerted_at, created_at, updated_at
        FROM telegram_opportunities
        WHERE {where}
        ORDER BY created_at DESC
        LIMIT %s
        """,
        tuple(params),
    )
    return [serialize_opportunity(_row_to_dict(cursor, row) or {}) for row in cursor.fetchall() or []]


def update_status(cursor: Any, opportunity_id: str, business_id: str, status: str, user_id: str | None = None, note: str | None = None) -> dict[str, Any]:
    if status not in STATUSES:
        raise ValueError("invalid status")
    cursor.execute(
        """
        SELECT status FROM telegram_opportunities
        WHERE id = %s AND business_id = %s
        LIMIT 1
        """,
        (opportunity_id, business_id),
    )
    row = cursor.fetchone()
    current = _row_to_dict(cursor, row)
    if not current:
        raise LookupError("opportunity not found")
    previous_status = str(current.get("status") or "")
    cursor.execute(
        """
        UPDATE telegram_opportunities
        SET status = %s, updated_at = NOW()
        WHERE id = %s AND business_id = %s
        RETURNING id, business_id, user_id, source_id, account_id, telegram_chat_id,
                  telegram_message_id, chat_title, sender_id, message_date, message_text,
                  message_link, signal_type, score, reason, reply_draft, status,
                  raw_payload_json, alerted_at, created_at, updated_at
        """,
        (status, opportunity_id, business_id),
    )
    updated = _row_to_dict(cursor, cursor.fetchone()) or {}
    cursor.execute(
        """
        INSERT INTO telegram_opportunity_events (id, opportunity_id, user_id, event_type, from_status, to_status, note)
        VALUES (%s, %s, %s, 'status_changed', %s, %s, %s)
        """,
        (str(uuid.uuid4()), opportunity_id, user_id, previous_status, status, note),
    )
    return serialize_opportunity(updated)


def notify_owner_for_opportunity(cursor: Any, opportunity: dict[str, Any]) -> dict[str, Any]:
    bot_token = str(os.getenv("TELEGRAM_BOT_TOKEN") or "").strip()
    if not bot_token:
        return {"sent": False, "reason": "telegram_bot_token_missing"}
    business_id = str(opportunity.get("business_id") or "").strip()
    cursor.execute(
        """
        SELECT u.telegram_id
        FROM businesses b
        JOIN users u ON u.id = b.owner_id
        WHERE b.id = %s
        LIMIT 1
        """,
        (business_id,),
    )
    row = cursor.fetchone()
    owner = _row_to_dict(cursor, row) if row else {}
    telegram_id = str((owner or {}).get("telegram_id") or "").strip()
    if not telegram_id:
        return {"sent": False, "reason": "owner_telegram_id_missing"}
    text = format_owner_alert(opportunity)
    result = send_telegram_bot_message(bot_token, telegram_id, text)
    if result.get("success"):
        cursor.execute("UPDATE telegram_opportunities SET alerted_at = NOW() WHERE id = %s", (opportunity.get("id"),))
    return {"sent": bool(result.get("success")), **result}


def format_owner_alert(opportunity: dict[str, Any]) -> str:
    text = str(opportunity.get("message_text") or "").strip()
    if len(text) > 700:
        text = text[:697].rstrip() + "..."
    parts = [
        "Новая возможность в Telegram",
        f"Чат: {opportunity.get('chat_title') or opportunity.get('telegram_chat_id')}",
        f"Сигнал: {opportunity.get('signal_type')} · score {opportunity.get('score')}",
    ]
    reason = str(opportunity.get("reason") or "").strip()
    if reason:
        parts.append(f"Почему: {reason}")
    if text:
        parts.append(f"Сообщение:\n{text}")
    draft = str(opportunity.get("reply_draft") or "").strip()
    if draft:
        parts.append(f"Как ответить:\n{draft}")
    link = str(opportunity.get("message_link") or "").strip()
    if link:
        parts.append(link)
    return "\n\n".join(parts)


def serialize_source(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    for key in ("created_at", "updated_at", "last_checked_at"):
        if result.get(key) is not None:
            result[key] = str(result[key])
    return result


def serialize_opportunity(row: dict[str, Any]) -> dict[str, Any]:
    result = dict(row)
    for key in ("message_date", "alerted_at", "created_at", "updated_at"):
        if result.get(key) is not None:
            result[key] = str(result[key])
    raw_payload = result.get("raw_payload_json")
    if isinstance(raw_payload, str):
        try:
            result["raw_payload_json"] = json.loads(raw_payload)
        except Exception:
            pass
    return result
