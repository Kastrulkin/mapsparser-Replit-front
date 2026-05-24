from __future__ import annotations

from typing import Any

from services.operator_map_refresh import enqueue_paid_operator_map_refresh
from services.operator_refresh_result import build_parse_reliability_state


RETRYABLE_RELIABILITY_STATUSES = {"failed", "captcha_required", "paused", "warning"}


def _clean_text(value: Any) -> str:
    return str(value or "").strip()


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
        return {columns[index]: row[index] for index in range(min(len(columns), len(row)))}
    return None


def _load_refresh_queue(cursor: Any, *, business_id: str, user_id: str, queue_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT id, business_id, user_id, url, status, source, task_type, error_message,
               retry_after, captcha_required, captcha_status, resume_requested,
               warnings, created_at, updated_at
        FROM parsequeue
        WHERE id = %s
          AND business_id = %s
          AND user_id = %s
        LIMIT 1
        """,
        (queue_id, business_id, user_id),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def build_refresh_retry_plan(
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
            "retry_allowed": False,
        }

    queue = _load_refresh_queue(cursor, business_id=business_id, user_id=user_id, queue_id=clean_queue_id)
    if not queue:
        return {
            "status": "blocked",
            "queue_id": clean_queue_id,
            "blocked_reasons": ["refresh_job_not_found"],
            "retry_allowed": False,
        }

    reliability = build_parse_reliability_state(queue)
    reliability_status = _clean_text(reliability.get("status"))
    queue_status = _clean_text(queue.get("status")).lower()
    blocked: list[str] = []
    if queue_status in {"pending", "processing"}:
        blocked.append("refresh_job_still_processing")
    if reliability_status not in RETRYABLE_RELIABILITY_STATUSES:
        blocked.append("refresh_job_not_retryable")
    if not _clean_text(queue.get("url")):
        blocked.append("refresh_job_url_missing")

    return {
        "status": "ready" if not blocked else "blocked",
        "queue_id": clean_queue_id,
        "business_id": business_id,
        "user_id": user_id,
        "source_queue": queue,
        "reliability_state": reliability,
        "retry_allowed": not blocked,
        "blocked_reasons": blocked,
        "side_effects": {
            "parsequeue_jobs_created": False,
            "credit_reserved": False,
            "credit_charged": False,
            "external_calls_performed": False,
            "external_writes_performed": False,
        },
    }


def request_refresh_retry(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    queue_id: str,
    estimated_credits: Any = None,
    confirm_retry: bool = False,
) -> dict[str, Any]:
    plan = build_refresh_retry_plan(
        cursor,
        business_id=business_id,
        user_id=user_id,
        queue_id=queue_id,
    )
    if plan.get("status") != "ready":
        return {
            **plan,
            "chat_response": "Повтор refresh сейчас недоступен: " + ", ".join(plan.get("blocked_reasons") or []),
            "retry_result": None,
        }

    if not confirm_retry:
        return {
            **plan,
            "status": "blocked",
            "retry_allowed": False,
            "blocked_reasons": ["explicit_retry_confirmation_required"],
            "retry_result": None,
            "billing_url": "/dashboard/billing",
            "chat_response": "Подтвердите платный read-only retry: отправьте confirm_retry=true.",
        }

    source_queue = plan.get("source_queue") if isinstance(plan.get("source_queue"), dict) else {}
    retry = enqueue_paid_operator_map_refresh(
        cursor,
        business_id=business_id,
        user_id=user_id,
        explicit_url=source_queue.get("url"),
        estimated_credits=estimated_credits,
    )
    if retry.get("status") != "queued":
        return {
            **plan,
            "status": "blocked",
            "retry_allowed": False,
            "blocked_reasons": list(retry.get("blocked_reasons") or ["refresh_retry_enqueue_failed"]),
            "retry_result": retry,
            "billing_url": retry.get("billing_url"),
            "chat_response": "Не удалось запустить повтор refresh: " + ", ".join(retry.get("blocked_reasons") or []),
            "side_effects": {
                "parsequeue_jobs_created": False,
                "credit_reserved": bool((retry.get("side_effects") or {}).get("credit_reserved")),
                "credit_charged": False,
                "external_calls_performed": False,
                "external_writes_performed": False,
            },
        }

    return {
        **plan,
        "status": "queued",
        "retry_allowed": True,
        "retry_result": retry,
        "new_queue_id": retry.get("queue_id"),
        "reservation_id": retry.get("reservation_id"),
        "estimated_credits": retry.get("estimated_credits"),
        "balance_credits": retry.get("balance_credits"),
        "billing_url": retry.get("billing_url"),
        "chat_response": "\n".join(
            [
                "Запустил повторное платное read-only обновление карты.",
                f"Новая задача: {retry.get('queue_id')}.",
                f"Зарезервировано до {retry.get('estimated_credits') or 'N'} кредитов; фактическое списание будет после результата Apify.",
                "Старый failed job не изменялся. Публикация в карты остаётся ручной.",
            ]
        ),
        "side_effects": {
            "parsequeue_jobs_created": True,
            "credit_reserved": bool((retry.get("side_effects") or {}).get("credit_reserved")),
            "credit_charged": False,
            "external_calls_performed": False,
            "external_writes_performed": False,
        },
    }
