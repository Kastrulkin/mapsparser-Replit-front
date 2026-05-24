from __future__ import annotations

from typing import Any

from services.operator_manual_review import REVIEWS_URL, _build_ui_action
from services.operator_news_generation import NEWS_DRAFTS_URL, _clean_text, _row_to_dict
from services.operator_services_optimization import SERVICES_URL


CONTENT_HISTORY_DEFAULT_LIMIT = 20


def _positive_limit(value: Any) -> int:
    try:
        parsed = int(value or CONTENT_HISTORY_DEFAULT_LIMIT)
    except Exception:
        return CONTENT_HISTORY_DEFAULT_LIMIT
    if parsed <= 0:
        return CONTENT_HISTORY_DEFAULT_LIMIT
    return min(parsed, 50)


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return bool(row.get("to_regclass") or row.get("table_ref") or row.get("?column?"))


def _table_has_column(cursor: Any, table_name: str, column_name: str) -> bool:
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


def _short_text(value: Any, limit: int = 220) -> str:
    text = " ".join(_clean_text(value).split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "..."


def _history_item(
    *,
    item_id: Any,
    kind: str,
    status: Any,
    title: str,
    text: Any,
    created_at: Any,
    updated_at: Any,
    href: str,
    source: str,
    action_label: str,
    manual_publication_only: bool = True,
    external_writes_performed: bool = False,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    clean_status = _clean_text(status) or "draft"
    return {
        "id": _clean_text(item_id),
        "kind": kind,
        "status": clean_status,
        "title": title,
        "text": _short_text(text),
        "created_at": created_at,
        "updated_at": updated_at,
        "source": source,
        "href": href,
        "manual_publication_only": manual_publication_only,
        "external_writes_performed": external_writes_performed,
        "metadata": metadata or {},
        "ui_actions": [_build_ui_action("open_content_item", action_label, href=href)],
    }


def _load_review_reply_history(cursor: Any, *, business_id: str, limit: int) -> list[dict[str, Any]]:
    if not _table_exists(cursor, "reviewreplydrafts"):
        return []
    cursor.execute(
        """
        SELECT id, review_id, status, generated_text, edited_text, author_name, created_at, updated_at
        FROM reviewreplydrafts
        WHERE business_id = %s
        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
        LIMIT %s
        """,
        (business_id, limit),
    )
    items: list[dict[str, Any]] = []
    for row in cursor.fetchall() or []:
        item = _row_to_dict(cursor, row) or {}
        author = _clean_text(item.get("author_name")) or "клиента"
        items.append(
            _history_item(
                item_id=item.get("id"),
                kind="review_reply_draft",
                status=item.get("status") or "draft",
                title=f"Ответ на отзыв {author}",
                text=item.get("edited_text") or item.get("generated_text"),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
                href=REVIEWS_URL,
                source="reviewreplydrafts",
                action_label="Открыть отзывы",
                metadata={"review_id": item.get("review_id")},
            )
        )
    return items


def _load_usernews_history(cursor: Any, *, business_id: str, user_id: str, limit: int) -> list[dict[str, Any]]:
    if not _table_exists(cursor, "usernews"):
        return []
    has_business_id = _table_has_column(cursor, "usernews", "business_id")
    has_prompt_key = _table_has_column(cursor, "usernews", "prompt_key")
    prompt_select = "prompt_key" if has_prompt_key else "NULL AS prompt_key"
    business_select = "business_id" if has_business_id else "NULL AS business_id"
    where_clause = "business_id = %s" if has_business_id else "user_id = %s"
    where_param = business_id if has_business_id else user_id
    cursor.execute(
        f"""
        SELECT id, user_id, {business_select}, source_text, generated_text, approved,
               {prompt_select}, created_at, updated_at
        FROM usernews
        WHERE {where_clause}
        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
        LIMIT %s
        """,
        (where_param, limit),
    )
    items: list[dict[str, Any]] = []
    for row in cursor.fetchall() or []:
        item = _row_to_dict(cursor, row) or {}
        prompt_key = _clean_text(item.get("prompt_key"))
        kind = "social_post_draft" if prompt_key == "operator_social_post_generate" else "news_draft"
        title = "Черновик поста" if kind == "social_post_draft" else "Черновик новости"
        status = "approved" if str(item.get("approved") or "0") in {"1", "true", "True"} else "draft"
        items.append(
            _history_item(
                item_id=item.get("id"),
                kind=kind,
                status=status,
                title=title,
                text=item.get("generated_text"),
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
                href=NEWS_DRAFTS_URL,
                source="usernews",
                action_label="Открыть черновики",
                metadata={"prompt_key": prompt_key, "source_text": _short_text(item.get("source_text"), 120)},
            )
        )
    return items


def _load_service_history(cursor: Any, *, business_id: str, user_id: str, limit: int) -> list[dict[str, Any]]:
    if not _table_exists(cursor, "serviceregenerationjobs"):
        return []
    cursor.execute(
        """
        SELECT id, status, selected_count, fixed_count, failed_count, message, created_at, updated_at
        FROM serviceregenerationjobs
        WHERE business_id = %s
          AND user_id = %s
        ORDER BY updated_at DESC NULLS LAST, created_at DESC NULLS LAST
        LIMIT %s
        """,
        (business_id, user_id, limit),
    )
    items: list[dict[str, Any]] = []
    for row in cursor.fetchall() or []:
        item = _row_to_dict(cursor, row) or {}
        fixed_count = int(item.get("fixed_count") or 0)
        selected_count = int(item.get("selected_count") or 0)
        kind = "service_apply" if fixed_count > 0 else "service_suggestion"
        title = "Применение услуг" if kind == "service_apply" else "Предложения по услугам"
        text = item.get("message") or f"Предложений: {selected_count}. Применено: {fixed_count}."
        items.append(
            _history_item(
                item_id=item.get("id"),
                kind=kind,
                status=item.get("status"),
                title=title,
                text=text,
                created_at=item.get("created_at"),
                updated_at=item.get("updated_at"),
                href=SERVICES_URL,
                source="serviceregenerationjobs",
                action_label="Открыть услуги",
                manual_publication_only=False,
                metadata={
                    "selected_count": selected_count,
                    "fixed_count": fixed_count,
                    "failed_count": int(item.get("failed_count") or 0),
                },
            )
        )
    return items


def _sort_key(item: dict[str, Any]) -> str:
    return _clean_text(item.get("updated_at") or item.get("created_at"))


def list_operator_content_history(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    limit: Any = CONTENT_HISTORY_DEFAULT_LIMIT,
) -> dict[str, Any]:
    clean_limit = _positive_limit(limit)
    items: list[dict[str, Any]] = []
    items.extend(_load_review_reply_history(cursor, business_id=business_id, limit=clean_limit))
    items.extend(_load_usernews_history(cursor, business_id=business_id, user_id=user_id, limit=clean_limit))
    items.extend(_load_service_history(cursor, business_id=business_id, user_id=user_id, limit=clean_limit))
    items = sorted(items, key=_sort_key, reverse=True)[:clean_limit]

    type_counts: dict[str, int] = {}
    status_counts: dict[str, int] = {}
    for item in items:
        kind = _clean_text(item.get("kind")) or "unknown"
        status = _clean_text(item.get("status")) or "unknown"
        type_counts[kind] = type_counts.get(kind, 0) + 1
        status_counts[status] = status_counts.get(status, 0) + 1

    return {
        "status": "completed",
        "business_id": business_id,
        "items": items,
        "summary": {
            "title": "История черновиков и предложений",
            "text": "Новости, соцпосты, ответы на отзывы и предложения по услугам разделены по типам.",
            "items_count": len(items),
            "type_counts": type_counts,
            "status_counts": status_counts,
        },
        "limits": {
            "external_calls_performed": False,
            "external_writes_performed": False,
            "manual_publication_only": True,
        },
    }
