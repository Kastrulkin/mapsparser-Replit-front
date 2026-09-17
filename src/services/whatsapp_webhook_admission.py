"""Durable, fail-closed admission for inbound WhatsApp messages."""
from __future__ import annotations

import json
import uuid
from typing import Any

from database_manager import DatabaseManager


SOURCE = "whatsapp"
EVENT_TYPE = "whatsapp.message.received"
STATUS_PROCESSING = "processing"
STATUS_COMPLETED = "completed"
STATUS_NEEDS_RECONCILIATION = "needs_reconciliation"


def whatsapp_source_event_key(sender_phone: str, provider_message_id: str) -> str:
    return f"whatsapp:{sender_phone}:{provider_message_id}"


def _safe_payload(provider_message_id: str, sender_phone: str) -> dict[str, str]:
    return {
        "provider_message_id": provider_message_id[:256],
        "sender_phone_last4": sender_phone[-4:],
    }


def _row_value(row: Any, key: str, position: int) -> str:
    if hasattr(row, "get"):
        return str(row.get(key) or "")
    return str(row[position] or "") if len(row) > position else ""


def admit_whatsapp_message(
    business_id: str,
    sender_phone: str,
    provider_message_id: str,
    database: Any = None,
) -> dict[str, str]:
    """Commit an at-most-once admission before invoking AI or a provider send.

    A process crash after this commit deliberately remains ``processing``: a
    duplicate callback is never retried automatically and cannot claim that a
    provider send did not happen.
    """
    db = database or DatabaseManager()
    owns_database = database is None
    key = whatsapp_source_event_key(sender_phone, provider_message_id)
    event_id = str(uuid.uuid4())
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            """
            INSERT INTO agent_trigger_events (
                id, business_id, source, event_type, status, payload_json, reason_code, source_event_key
            )
            VALUES (%s, %s, %s, %s, %s, %s::jsonb, NULL, %s)
            ON CONFLICT (business_id, source, source_event_key) WHERE source_event_key IS NOT NULL
            DO NOTHING
            RETURNING id
            """,
            (
                event_id,
                business_id,
                SOURCE,
                EVENT_TYPE,
                STATUS_PROCESSING,
                json.dumps(_safe_payload(provider_message_id, sender_phone), ensure_ascii=False),
                key,
            ),
        )
        row = cursor.fetchone()
        if row:
            db.conn.commit()
            return {"state": "admitted", "event_id": _row_value(row, "id", 0) or event_id}

        cursor.execute(
            """
            SELECT id, status
            FROM agent_trigger_events
            WHERE business_id = %s AND source = %s AND source_event_key = %s
            FOR UPDATE
            """,
            (business_id, SOURCE, key),
        )
        existing = cursor.fetchone() or {}
        existing_id = _row_value(existing, "id", 0)
        status = _row_value(existing, "status", 1)
        if status == STATUS_COMPLETED:
            db.conn.commit()
            return {"state": "duplicate_completed", "event_id": existing_id}
        db.conn.commit()
        if status == STATUS_PROCESSING:
            return {"state": "duplicate_processing", "event_id": existing_id}
        return {"state": "needs_reconciliation", "event_id": existing_id}
    except Exception:
        db.conn.rollback()
        raise
    finally:
        if owns_database:
            db.close()


def mark_whatsapp_message_reconciliation(
    event_id: str,
    reason_code: str,
    database: Any = None,
) -> None:
    _set_whatsapp_message_status(event_id, STATUS_NEEDS_RECONCILIATION, reason_code, database)


def mark_whatsapp_message_completed(event_id: str, database: Any = None) -> bool:
    return _set_whatsapp_message_status(event_id, STATUS_COMPLETED, "", database)


def _set_whatsapp_message_status(
    event_id: str,
    status: str,
    reason_code: str,
    database: Any = None,
) -> bool:
    db = database or DatabaseManager()
    owns_database = database is None
    try:
        cursor = db.conn.cursor()
        cursor.execute(
            """
            UPDATE agent_trigger_events
            SET status = %s, reason_code = %s, updated_at = NOW()
            WHERE id = %s AND source = %s AND status = %s
            RETURNING id
            """,
            (
                status,
                reason_code or None,
                event_id,
                SOURCE,
                STATUS_PROCESSING,
            ),
        )
        changed = bool(cursor.fetchone())
        db.conn.commit()
        return changed
    except Exception:
        db.conn.rollback()
        raise
    finally:
        if owns_database:
            db.close()
