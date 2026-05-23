from __future__ import annotations

from typing import Any

from services.operator_attention import build_attention_brief
from services.operator_paid_actions import build_paid_action_offer


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


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) AS table_ref", (f"public.{table_name}",))
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return bool(row.get("table_ref") or row.get("to_regclass"))


def _safe_int(value: Any) -> int:
    try:
        parsed = int(value or 0)
    except Exception:
        return 0
    return max(0, parsed)


def _load_ready_review_drafts(cursor: Any, *, business_id: str, limit: int = 5) -> list[dict[str, Any]]:
    if not _table_exists(cursor, "reviewreplydrafts"):
        return []
    cursor.execute(
        """
        SELECT id, review_id, author_name, review_text, generated_text, status, updated_at
        FROM reviewreplydrafts
        WHERE business_id = %s
          AND status IN ('draft', 'generated', 'pending_review')
        ORDER BY updated_at DESC
        LIMIT %s
        """,
        (business_id, limit),
    )
    drafts: list[dict[str, Any]] = []
    for row in cursor.fetchall() or []:
        item = _row_to_dict(cursor, row) or {}
        drafts.append(
            {
                "id": str(item.get("id") or ""),
                "kind": "review_reply_draft",
                "title": "Черновик ответа готов",
                "description": str(item.get("review_text") or "")[:240],
                "status": str(item.get("status") or "draft"),
                "priority": "medium",
                "primary_action": "copy_reply",
                "secondary_action": "mark_manual_published",
                "href": "/dashboard/card?tab=reviews&review_filter=needs_reply",
                "copy_text": str(item.get("generated_text") or ""),
                "metadata": {
                    "review_id": str(item.get("review_id") or ""),
                    "author_name": str(item.get("author_name") or "Клиент"),
                    "manual_publication_only": True,
                    "external_writes_performed": False,
                },
            }
        )
    return drafts


def _make_metric_item(kind: str, title: str, count: int, href: str, priority: str) -> dict[str, Any] | None:
    if count <= 0:
        return None
    return {
        "id": kind,
        "kind": kind,
        "title": title,
        "description": "Откройте связанный раздел, чтобы разобрать очередь вручную.",
        "status": "needs_attention",
        "priority": priority,
        "count": count,
        "primary_action": "open_section",
        "href": href,
        "copy_text": "",
        "metadata": {
            "manual_publication_only": True,
            "external_writes_performed": False,
        },
    }


def build_operator_inbox(cursor: Any, *, business_id: str, user_id: str) -> dict[str, Any]:
    brief = build_attention_brief(cursor, business_id, user_id)
    metrics = dict(brief.get("metrics") or {})
    items: list[dict[str, Any]] = []

    review_count = _safe_int(metrics.get("reviews_without_response"))
    review_item = _make_metric_item(
        "reviews_without_response",
        "Отзывы без ответа",
        review_count,
        "/dashboard/card?tab=reviews&review_filter=needs_reply",
        "high",
    )
    if review_item:
        items.append(review_item)

    items.extend(_load_ready_review_drafts(cursor, business_id=business_id))

    news_item = _make_metric_item(
        "pending_news",
        "Черновики новостей",
        _safe_int(metrics.get("pending_news")),
        "/dashboard/progress",
        "medium",
    )
    if news_item:
        items.append(news_item)

    partnership_item = _make_metric_item(
        "partnership_leads_ready",
        "Партнёрства к разбору",
        _safe_int(metrics.get("partnership_leads_ready")),
        "/dashboard/partnerships",
        "medium",
    )
    if partnership_item:
        items.append(partnership_item)

    paid_generation_offers = [
        build_paid_action_offer("review_replies_generate", business_id=business_id, estimated_credits=1),
        build_paid_action_offer("news_generate", business_id=business_id, estimated_credits=1),
        build_paid_action_offer("social_post_generate", business_id=business_id, estimated_credits=1),
        build_paid_action_offer("services_optimize", business_id=business_id, estimated_credits=1),
    ]

    return {
        "business_id": business_id,
        "status": "ready",
        "summary": {
            "title": "Operator Inbox",
            "text": f"В очереди {len(items)} рабочих пунктов. Внешние публикации выполняются вручную.",
            "items_count": len(items),
        },
        "items": items,
        "paid_generation_offers": paid_generation_offers,
        "limits": {
            "external_calls_performed": False,
            "external_writes_performed": False,
            "manual_publication_only": True,
        },
    }
