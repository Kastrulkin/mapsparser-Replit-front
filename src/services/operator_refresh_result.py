from __future__ import annotations

from typing import Any

from services.operator_manual_review import _build_ui_action
from services.operator_news_generation import _clean_text, _row_to_dict


REVIEWS_URL = "/dashboard/card?tab=reviews&review_filter=needs_reply"


def _load_queue(cursor: Any, *, business_id: str, user_id: str, queue_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT id, business_id, user_id, status, source, task_type, error_message, created_at, updated_at
        FROM parsequeue
        WHERE id = %s
          AND business_id = %s
          AND user_id = %s
        LIMIT 1
        """,
        (queue_id, business_id, user_id),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _load_reviews_since(cursor: Any, *, business_id: str, since_value: Any, limit: int = 10) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, source, external_review_id, rating, author_name, text,
               response_text, published_at, created_at
        FROM externalbusinessreviews
        WHERE business_id = %s
          AND created_at >= %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (business_id, since_value, limit),
    )
    reviews: list[dict[str, Any]] = []
    for row in cursor.fetchall() or []:
        item = _row_to_dict(cursor, row) or {}
        reviews.append(
            {
                "id": item.get("id"),
                "source": item.get("source"),
                "external_review_id": item.get("external_review_id"),
                "rating": item.get("rating"),
                "author_name": item.get("author_name"),
                "text": item.get("text"),
                "has_response": bool(_clean_text(item.get("response_text"))),
                "published_at": item.get("published_at"),
                "created_at": item.get("created_at"),
            }
        )
    return reviews


def build_refresh_result_status(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    queue_id: str,
) -> dict[str, Any]:
    clean_queue_id = _clean_text(queue_id)
    if not clean_queue_id:
        return {
            "status": "blocked",
            "queue_id": "",
            "blocked_reasons": ["queue_id_required"],
            "chat_response": "Нужен id задачи обновления, чтобы проверить результат.",
        }

    queue = _load_queue(cursor, business_id=business_id, user_id=user_id, queue_id=clean_queue_id)
    if not queue:
        return {
            "status": "blocked",
            "queue_id": clean_queue_id,
            "blocked_reasons": ["refresh_job_not_found"],
            "chat_response": "Не нашёл задачу обновления для этого бизнеса.",
        }

    queue_status = _clean_text(queue.get("status")).lower()
    if queue_status in {"pending", "processing", "captcha"}:
        return {
            "status": "processing",
            "queue": queue,
            "queue_id": clean_queue_id,
            "queue_status": queue_status,
            "new_reviews_count": 0,
            "new_unanswered_reviews_count": 0,
            "new_reviews": [],
            "chat_response": "Обновление ещё выполняется. Проверьте результат чуть позже.",
            "blocked_reasons": [],
        }
    if queue_status not in {"completed", "done", "success"}:
        return {
            "status": "failed",
            "queue": queue,
            "queue_id": clean_queue_id,
            "queue_status": queue_status,
            "new_reviews_count": 0,
            "new_unanswered_reviews_count": 0,
            "new_reviews": [],
            "chat_response": "Обновление завершилось с ошибкой: " + (_clean_text(queue.get("error_message")) or queue_status),
            "blocked_reasons": ["refresh_job_failed"],
        }

    new_reviews = _load_reviews_since(cursor, business_id=business_id, since_value=queue.get("created_at"))
    new_unanswered = [item for item in new_reviews if not item.get("has_response")]
    count = len(new_reviews)
    unanswered_count = len(new_unanswered)
    if count > 0:
        chat_response = "\n".join(
            [
                f"Обновление завершено. Найдено новых отзывов: {count}.",
                f"Без ответа: {unanswered_count}.",
                "Можно подготовить ответы на отзывы прямо из Operator.",
            ]
        )
    else:
        chat_response = "Обновление завершено. Новых отзывов после запуска задачи не найдено."

    return {
        "status": "completed",
        "queue": queue,
        "queue_id": clean_queue_id,
        "queue_status": queue_status,
        "new_reviews_count": count,
        "new_unanswered_reviews_count": unanswered_count,
        "new_reviews": new_reviews,
        "chat_response": chat_response,
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_publication_only": True,
        "blocked_reasons": [],
        "ui_actions": [
            _build_ui_action("open_reviews", "Открыть отзывы", href=REVIEWS_URL),
            _build_ui_action("generate_review_replies", "Подготовить ответы", payload={"action_key": "review_replies_generate"}),
        ],
    }
