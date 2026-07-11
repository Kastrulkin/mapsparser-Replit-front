from __future__ import annotations

import hashlib
import json
import uuid
from typing import Any


def _clean(value: Any) -> str:
    return str(value or "").strip()


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


def get_or_create_operator_conversation(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    channel: str,
    conversation_id: Any = None,
    transport_key: Any = None,
) -> dict[str, Any]:
    requested_id = _clean(conversation_id)
    clean_transport_key = _clean(transport_key) or None
    if requested_id:
        cursor.execute(
            """
            SELECT * FROM operatorconversations
            WHERE id = %s AND business_id = %s AND user_id = %s
            """,
            (requested_id, business_id, user_id),
        )
        existing = _row(cursor, cursor.fetchone())
        if existing:
            return existing
    if clean_transport_key:
        cursor.execute(
            """
            SELECT * FROM operatorconversations
            WHERE business_id = %s AND user_id = %s AND channel = %s AND transport_key = %s
            """,
            (business_id, user_id, channel, clean_transport_key),
        )
        existing = _row(cursor, cursor.fetchone())
        if existing:
            return existing
    created_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO operatorconversations (id, business_id, user_id, channel, transport_key)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING *
        """,
        (created_id, business_id, user_id, channel, clean_transport_key),
    )
    return _row(cursor, cursor.fetchone()) or {
        "id": created_id,
        "business_id": business_id,
        "user_id": user_id,
        "channel": channel,
        "pending_context": {},
    }


def conversation_pending_context(conversation: dict[str, Any]) -> dict[str, Any]:
    value = conversation.get("pending_context")
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


def set_operator_pending_context(cursor: Any, conversation_id: str, context: dict[str, Any] | None) -> None:
    cursor.execute(
        """
        UPDATE operatorconversations
        SET pending_context = %s::jsonb, updated_at = NOW()
        WHERE id = %s
        """,
        (json.dumps(context or {}, ensure_ascii=False), conversation_id),
    )


def append_operator_message(
    cursor: Any,
    *,
    conversation_id: str,
    business_id: str,
    user_id: str,
    role: str,
    content: Any,
    capability: Any = None,
    status: Any = None,
    result: dict[str, Any] | None = None,
) -> str:
    message_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO operatormessages (
            id, conversation_id, business_id, user_id, role, content,
            capability, status, result_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb)
        """,
        (
            message_id,
            conversation_id,
            business_id,
            user_id,
            role,
            _clean(content),
            _clean(capability) or None,
            _clean(status) or None,
            json.dumps(result or {}, ensure_ascii=False, default=str),
        ),
    )
    cursor.execute("UPDATE operatorconversations SET updated_at = NOW() WHERE id = %s", (conversation_id,))
    return message_id


def list_operator_messages(cursor: Any, *, conversation_id: str, business_id: str, limit: int = 100) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, role, content, capability, status, result_json, created_at
        FROM operatormessages
        WHERE conversation_id = %s AND business_id = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (conversation_id, business_id, max(1, min(int(limit or 100), 200))),
    )
    items = [_row(cursor, value) for value in (cursor.fetchall() or [])]
    items.reverse()
    return items


def find_latest_operator_conversation(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    channel: str,
) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT * FROM operatorconversations
        WHERE business_id = %s AND user_id = %s AND channel = %s AND status = 'active'
        ORDER BY updated_at DESC
        LIMIT 1
        """,
        (business_id, user_id, channel),
    )
    return _row(cursor, cursor.fetchone())


def create_pending_operator_action(
    cursor: Any,
    *,
    conversation_id: str,
    business_id: str,
    user_id: str,
    capability: str,
    envelope: dict[str, Any],
) -> dict[str, Any]:
    stable_source = json.dumps(envelope, ensure_ascii=False, sort_keys=True, default=str)
    idempotency_key = hashlib.sha256(
        f"{business_id}|{user_id}|{capability}|{stable_source}".encode("utf-8")
    ).hexdigest()[:32]
    action_id = str(uuid.uuid4())
    cursor.execute(
        """
        INSERT INTO operatoractions (
            id, conversation_id, business_id, user_id, capability,
            idempotency_key, envelope_json
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb)
        ON CONFLICT (business_id, idempotency_key)
        DO UPDATE SET updated_at = NOW()
        RETURNING *
        """,
        (
            action_id,
            conversation_id,
            business_id,
            user_id,
            capability,
            idempotency_key,
            json.dumps(envelope, ensure_ascii=False, default=str),
        ),
    )
    return _row(cursor, cursor.fetchone())


def get_operator_action(cursor: Any, *, action_id: str, business_id: str, user_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT * FROM operatoractions
        WHERE id = %s AND business_id = %s AND user_id = %s
        """,
        (action_id, business_id, user_id),
    )
    return _row(cursor, cursor.fetchone())


def finish_operator_action(cursor: Any, *, action_id: str, result: dict[str, Any]) -> None:
    cursor.execute(
        """
        UPDATE operatoractions
        SET status = 'completed', confirmed_at = COALESCE(confirmed_at, NOW()),
            executed_at = COALESCE(executed_at, NOW()), result_json = %s::jsonb,
            updated_at = NOW()
        WHERE id = %s
        """,
        (json.dumps(result, ensure_ascii=False, default=str), action_id),
    )
