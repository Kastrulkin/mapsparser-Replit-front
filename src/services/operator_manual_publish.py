from __future__ import annotations

from typing import Any


def _row_to_dict(cursor: Any, row: Any) -> dict[str, Any] | None:
    if row is None:
        return None
    if isinstance(row, dict):
        return dict(row)
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


def mark_review_reply_draft_manual_published(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    draft_id: str,
) -> dict[str, Any]:
    clean_draft_id = str(draft_id or "").strip()
    if not clean_draft_id:
        return {
            "status": "blocked",
            "blocked_reasons": ["draft_id_required"],
            "external_writes_performed": False,
        }

    cursor.execute(
        """
        SELECT id, business_id, review_id, generated_text, edited_text, status
        FROM reviewreplydrafts
        WHERE id = %s
          AND business_id = %s
        LIMIT 1
        """,
        (clean_draft_id, business_id),
    )
    draft = _row_to_dict(cursor, cursor.fetchone()) or {}
    if not draft:
        return {
            "status": "blocked",
            "blocked_reasons": ["draft_not_found"],
            "external_writes_performed": False,
        }

    reply_text = str(draft.get("edited_text") or draft.get("generated_text") or "").strip()
    if not reply_text:
        return {
            "status": "blocked",
            "draft": draft,
            "blocked_reasons": ["empty_reply_text"],
            "external_writes_performed": False,
        }

    cursor.execute(
        """
        UPDATE reviewreplydrafts
        SET status = 'manual_published',
            updated_at = NOW()
        WHERE id = %s
          AND business_id = %s
        RETURNING id, review_id, status, updated_at
        """,
        (clean_draft_id, business_id),
    )
    updated = _row_to_dict(cursor, cursor.fetchone()) or {}

    cursor.execute(
        """
        UPDATE externalbusinessreviews
        SET response_text = COALESCE(NULLIF(response_text, ''), %s),
            response_at = COALESCE(response_at, NOW()),
            updated_at = NOW()
        WHERE id = %s
          AND business_id = %s
          AND COALESCE(BTRIM(response_text), '') = ''
        """,
        (reply_text, str(draft.get("review_id") or ""), business_id),
    )

    return {
        "status": "completed",
        "draft": updated or draft,
        "reply_text": reply_text,
        "user_id": user_id,
        "manual_publication_only": True,
        "external_writes_performed": False,
        "chat_response": "Отметил черновик как опубликованный вручную. LocalOS не публиковал ответ во внешние карты.",
        "ui_actions": [
            {
                "action": "open_reviews",
                "label": "Открыть отзывы",
                "href": "/dashboard/card?tab=reviews&review_filter=needs_reply",
                "payload": {},
            }
        ],
        "blocked_reasons": [],
    }
