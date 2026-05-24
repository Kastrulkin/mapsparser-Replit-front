from __future__ import annotations

from typing import Any

from services.operator_manual_review import _build_ui_action
from services.operator_news_generation import _clean_text, _row_to_dict


REVIEWS_URL = "/dashboard/card?tab=reviews&review_filter=needs_reply"
MAP_REFRESH_SOURCE = "apify_yandex"
MAP_REFRESH_TASK_TYPE = "parse_card"


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


def _normalize_refresh_job_status(value: Any) -> str:
    status = _clean_text(value).lower()
    if status in {"pending", "processing", "captcha"}:
        return "processing"
    if status in {"completed", "done", "success"}:
        return "completed"
    if status:
        return "failed"
    return "processing"


def _load_recent_refresh_queues(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    limit: int,
) -> list[dict[str, Any]]:
    cursor.execute(
        """
        SELECT id, business_id, user_id, status, source, task_type, error_message, created_at, updated_at
        FROM parsequeue
        WHERE business_id = %s
          AND user_id = %s
          AND source = %s
          AND task_type = %s
        ORDER BY created_at DESC
        LIMIT %s
        """,
        (business_id, user_id, MAP_REFRESH_SOURCE, MAP_REFRESH_TASK_TYPE, limit),
    )
    return [_row_to_dict(cursor, row) or {} for row in cursor.fetchall() or []]


def list_refresh_jobs(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    limit: Any = 10,
) -> dict[str, Any]:
    try:
        clean_limit = int(limit)
    except (TypeError, ValueError):
        clean_limit = 10
    clean_limit = max(1, min(clean_limit, 25))

    queues = _load_recent_refresh_queues(
        cursor,
        business_id=business_id,
        user_id=user_id,
        limit=clean_limit,
    )
    jobs: list[dict[str, Any]] = []
    status_counts = {"processing": 0, "completed": 0, "failed": 0}
    total_new_reviews = 0
    total_new_unanswered = 0

    for queue in queues:
        queue_id = _clean_text(queue.get("id"))
        result = build_refresh_result_status(
            cursor,
            business_id=business_id,
            user_id=user_id,
            queue_id=queue_id,
        )
        status = _normalize_refresh_job_status(result.get("status") or queue.get("status"))
        status_counts[status] = status_counts.get(status, 0) + 1
        new_reviews_count = int(result.get("new_reviews_count") or 0)
        new_unanswered_count = int(result.get("new_unanswered_reviews_count") or 0)
        total_new_reviews += new_reviews_count
        total_new_unanswered += new_unanswered_count
        jobs.append(
            {
                "queue_id": queue_id,
                "status": status,
                "queue_status": result.get("queue_status") or queue.get("status"),
                "created_at": queue.get("created_at"),
                "updated_at": queue.get("updated_at"),
                "error_message": queue.get("error_message"),
                "new_reviews_count": new_reviews_count,
                "new_unanswered_reviews_count": new_unanswered_count,
                "new_reviews": list(result.get("new_reviews") or [])[:5],
                "chat_response": result.get("chat_response"),
                "blocked_reasons": list(result.get("blocked_reasons") or []),
                "ui_actions": [
                    _build_ui_action("check_refresh_result", "Проверить результат", payload={"queue_id": queue_id}),
                    _build_ui_action("open_reviews", "Открыть отзывы", href=REVIEWS_URL),
                    _build_ui_action("generate_review_replies", "Подготовить ответы", payload={"action_key": "review_replies_generate"}),
                ],
                "external_calls_performed": False,
                "external_writes_performed": False,
                "manual_publication_only": True,
            }
        )

    return {
        "status": "completed",
        "business_id": business_id,
        "jobs": jobs,
        "summary": {
            "title": "История обновлений отзывов",
            "text": "Последние read-only обновления карт и найденные после них отзывы.",
            "jobs_count": len(jobs),
            "processing_count": status_counts.get("processing", 0),
            "completed_count": status_counts.get("completed", 0),
            "failed_count": status_counts.get("failed", 0),
            "new_reviews_count": total_new_reviews,
            "new_unanswered_reviews_count": total_new_unanswered,
        },
        "limits": {
            "external_calls_performed": False,
            "external_writes_performed": False,
            "manual_publication_only": True,
        },
    }
