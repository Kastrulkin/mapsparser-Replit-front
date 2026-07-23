"""Sales-room proposal review and message helpers."""
from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

from psycopg2.extras import Json


def _to_json_compatible(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, inner in value.items():
            normalized[str(key)] = _to_json_compatible(inner)
        return normalized
    if isinstance(value, list):
        return [_to_json_compatible(item) for item in value]
    if isinstance(value, tuple):
        return [_to_json_compatible(item) for item in value]
    return value


def serialize_sales_room_message(row: dict[str, Any]) -> dict[str, Any]:
    attachments = row.get("attachments_json")
    if not isinstance(attachments, list):
        attachments = []
    return _to_json_compatible(
        {
            "id": row.get("id"),
            "author_type": row.get("author_type") or "visitor",
            "author_name": row.get("author_name") or "Гость",
            "author_contact": row.get("author_contact") or "",
            "body_text": row.get("body_text") or "",
            "attachments": attachments,
            "direction": row.get("direction") or "room",
            "source_channel": row.get("source_channel"),
            "provider_event_id": row.get("provider_event_id"),
            "campaign_id": row.get("campaign_id"),
            "campaign_touch_id": row.get("campaign_touch_id"),
            "delivery_status": row.get("delivery_status") or "recorded",
            "occurred_at": row.get("occurred_at"),
            "created_at": row.get("created_at"),
        }
    )


def serialize_sales_room_version(row: dict[str, Any]) -> dict[str, Any]:
    return _to_json_compatible(
        {
            "id": row.get("id"),
            "version_no": int(row.get("version_no") or 0),
            "body_text": row.get("body_text") or "",
            "created_by_name": row.get("created_by_name") or "",
            "created_by_contact": row.get("created_by_contact") or "",
            "created_at": row.get("created_at"),
        }
    )


def serialize_sales_room_suggestion(row: dict[str, Any]) -> dict[str, Any]:
    return _to_json_compatible(
        {
            "id": row.get("id"),
            "version_id": row.get("version_id"),
            "suggestion_type": row.get("suggestion_type") or "replace",
            "selection_text": row.get("selection_text") or "",
            "selection_start": row.get("selection_start"),
            "selection_end": row.get("selection_end"),
            "replacement_text": row.get("replacement_text") or "",
            "comment_text": row.get("comment_text") or "",
            "author_name": row.get("author_name") or "Гость",
            "author_contact": row.get("author_contact") or "",
            "status": row.get("status") or "pending",
            "resolved_by_name": row.get("resolved_by_name") or "",
            "resolved_by_contact": row.get("resolved_by_contact") or "",
            "resolved_at": row.get("resolved_at"),
            "created_at": row.get("created_at"),
            "updated_at": row.get("updated_at"),
        }
    )


def load_sales_room_messages(cur, room_id: str, limit: int = 50) -> list[dict[str, Any]]:
    cur.execute(
        """
        SELECT id, author_type, author_name, author_contact, body_text, attachments_json,
               direction, source_channel, provider_event_id, campaign_id,
               campaign_touch_id, delivery_status, occurred_at, created_at
        FROM sales_room_messages
        WHERE room_id = %s
        ORDER BY created_at ASC
        LIMIT %s
        """,
        (room_id, limit),
    )
    rows = cur.fetchall() or []
    return [serialize_sales_room_message(dict(row)) for row in rows]


def load_sales_room_latest_version(cur, room_id: str) -> dict[str, Any]:
    cur.execute(
        """
        SELECT id, version_no, body_text, created_by_name, created_by_contact, metadata_json, created_at
        FROM sales_room_proposal_versions
        WHERE room_id = %s
        ORDER BY version_no DESC
        LIMIT 1
        """,
        (room_id,),
    )
    row = cur.fetchone()
    return dict(row) if row and hasattr(row, "keys") else {}


def load_sales_room_review(cur, room_id: str) -> dict[str, Any]:
    latest = load_sales_room_latest_version(cur, room_id)
    cur.execute(
        """
        SELECT id, version_id, suggestion_type, selection_text, selection_start, selection_end,
               replacement_text, comment_text, author_name, author_contact, status,
               resolved_by_name, resolved_by_contact, resolved_at, created_at, updated_at
        FROM sales_room_proposal_suggestions
        WHERE room_id = %s
        ORDER BY
          CASE WHEN status = 'pending' THEN 0 ELSE 1 END,
          created_at DESC
        LIMIT 100
        """,
        (room_id,),
    )
    suggestions = [serialize_sales_room_suggestion(dict(row)) for row in (cur.fetchall() or [])]
    return {
        "latest_version": serialize_sales_room_version(latest) if latest else None,
        "suggestions": suggestions,
    }


def ensure_sales_room_proposal_version(
    cur,
    *,
    room_id: str,
    body_text: str,
    author_name: str = "",
    author_contact: str = "",
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    current = load_sales_room_latest_version(cur, room_id)
    if current:
        return current
    version_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO sales_room_proposal_versions (
            id, room_id, version_no, body_text, created_by_name, created_by_contact, metadata_json, created_at
        ) VALUES (
            %s, %s, 1, %s, %s, %s, %s, NOW()
        )
        RETURNING id, version_no, body_text, created_by_name, created_by_contact, metadata_json, created_at
        """,
        (version_id, room_id, body_text, author_name, author_contact, Json(metadata or {"source": "initial_room_proposal"})),
    )
    return dict(cur.fetchone())


def create_sales_room_proposal_version(
    cur,
    *,
    room_id: str,
    body_text: str,
    author_name: str,
    author_contact: str,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    latest = load_sales_room_latest_version(cur, room_id)
    next_version_no = int(latest.get("version_no") or 0) + 1 if latest else 1
    version_id = str(uuid.uuid4())
    cur.execute(
        """
        INSERT INTO sales_room_proposal_versions (
            id, room_id, version_no, body_text, created_by_name, created_by_contact, metadata_json, created_at
        ) VALUES (
            %s, %s, %s, %s, %s, %s, %s, NOW()
        )
        RETURNING id, version_no, body_text, created_by_name, created_by_contact, metadata_json, created_at
        """,
        (version_id, room_id, next_version_no, body_text, author_name, author_contact, Json(metadata or {})),
    )
    return dict(cur.fetchone())


def replace_text_for_sales_room_suggestion(current_text: str, suggestion: dict[str, Any]) -> tuple[str, bool, str]:
    selection_text = str(suggestion.get("selection_text") or "")
    replacement_text = str(suggestion.get("replacement_text") or "")
    start_value = suggestion.get("selection_start")
    end_value = suggestion.get("selection_end")
    try:
        start = int(start_value) if start_value is not None else -1
        end = int(end_value) if end_value is not None else -1
    except (TypeError, ValueError):
        start = -1
        end = -1
    if start >= 0 and end > start and current_text[start:end] == selection_text:
        return f"{current_text[:start]}{replacement_text}{current_text[end:]}", True, "range"
    if selection_text and selection_text in current_text:
        return current_text.replace(selection_text, replacement_text, 1), True, "text"
    return current_text, False, "selection_not_found"


def update_sales_room_proposal_body(cur, *, room_id: str, body_text: str) -> None:
    cur.execute(
        """
        UPDATE sales_rooms
        SET room_json = jsonb_set(
                COALESCE(room_json, '{}'),
                '{proposal,body_text}',
                to_jsonb(%s::text),
                TRUE
            ),
            proposal_json = jsonb_set(
                COALESCE(proposal_json, '{}'),
                '{body_text}',
                to_jsonb(%s::text),
                TRUE
            ),
            updated_at = NOW()
        WHERE id = %s
        """,
        (body_text, body_text, room_id),
    )


def load_sales_room_by_slug(cur, slug: str) -> dict[str, Any]:
    cur.execute(
        """
        SELECT id, slug, business_id, mode, lead_id, room_json, status,
               visibility, updated_at
        FROM sales_rooms
        WHERE slug = %s
        LIMIT 1
        """,
        (slug,),
    )
    row = cur.fetchone()
    return dict(row) if row and hasattr(row, "keys") else {}


def can_edit_sales_room(cur, room: dict[str, Any], user_data: dict[str, Any] | None) -> bool:
    if not user_data:
        return False
    if bool(user_data.get("is_superadmin")):
        return True
    user_id = str(user_data.get("user_id") or user_data.get("id") or "").strip()
    business_id = str(room.get("business_id") or "").strip()
    if not user_id or not business_id:
        return False
    cur.execute(
        """
        SELECT id
        FROM businesses
        WHERE id = %s
          AND owner_id = %s
        LIMIT 1
        """,
        (business_id, user_id),
    )
    return bool(cur.fetchone())
