from __future__ import annotations

import json
from datetime import datetime
from typing import Any, Callable

from services.operator_refresh_result import build_refresh_result_status


MAP_REVIEWS_REFRESH_ACTION_KEY = "map_reviews_refresh"
FOLLOWUP_ATTEMPTED_AT_KEY = "telegram_refresh_followup_attempted_at"
FOLLOWUP_DELIVERED_AT_KEY = "telegram_refresh_followup_delivered_at"
FOLLOWUP_STATUS_KEY = "telegram_refresh_followup_status"


def _json_dict(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            return {}
    return {}


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


def _utc_now_iso() -> str:
    return datetime.utcnow().replace(microsecond=0).isoformat() + "Z"


def _load_refresh_reservation(cursor: Any, *, business_id: str, user_id: str, queue_id: str) -> dict[str, Any] | None:
    cursor.execute(
        """
        SELECT id, status, metadata
        FROM operatorcreditreservations
        WHERE business_id = %s
          AND user_id = %s
          AND action_key = %s
          AND metadata ->> 'parsequeue_id' = %s
        ORDER BY created_at DESC
        LIMIT 1
        """,
        (business_id, user_id, MAP_REVIEWS_REFRESH_ACTION_KEY, queue_id),
    )
    return _row_to_dict(cursor, cursor.fetchone())


def _load_owner_contact(cursor: Any, *, business_id: str, user_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT b.name AS business_name, u.telegram_id
        FROM businesses b
        JOIN users u ON u.id = b.owner_id
        WHERE b.id = %s
          AND u.id = %s
        LIMIT 1
        """,
        (business_id, user_id),
    )
    return _row_to_dict(cursor, cursor.fetchone()) or {}


def _store_followup_metadata(cursor: Any, *, reservation_id: str, patch: dict[str, Any]) -> None:
    cursor.execute(
        """
        UPDATE operatorcreditreservations
        SET metadata = COALESCE(metadata, '{}'::jsonb) || %s::jsonb,
            updated_at = CURRENT_TIMESTAMP
        WHERE id = %s
        """,
        (json.dumps(patch, ensure_ascii=False), reservation_id),
    )


def format_refresh_followup_text(result: dict[str, Any], *, business_name: str) -> str:
    status = _clean_text(result.get("status"))
    billing_state = result.get("billing_state") if isinstance(result.get("billing_state"), dict) else {}
    billing_label = _clean_text(billing_state.get("label")) or "Оплата уточняется"
    lines = [
        "LocalOS Operator",
        "Обновление отзывов",
        f"Бизнес: {_clean_text(business_name) or 'Бизнес'}",
        "",
    ]

    if status == "completed":
        new_reviews = int(result.get("new_reviews_count") or 0)
        unanswered = int(result.get("new_unanswered_reviews_count") or 0)
        lines.extend(
            [
                "Обновление завершено.",
                f"Новых отзывов: {new_reviews}.",
                f"Без ответа: {unanswered}.",
                f"Оплата: {billing_label}.",
            ]
        )
        reviews = result.get("new_reviews") if isinstance(result.get("new_reviews"), list) else []
        if reviews:
            lines.extend(["", "Последние новые отзывы:"])
            for review in reviews[:2]:
                if not isinstance(review, dict):
                    continue
                author = _clean_text(review.get("author_name")) or "Новый отзыв"
                text = _clean_text(review.get("text"))
                if text:
                    snippet = text[:180] + ("..." if len(text) > 180 else "")
                    lines.append(f"• {author}: {snippet}")
    elif status == "failed":
        lines.extend(
            [
                "Обновление завершилось с ошибкой.",
                _clean_text(result.get("chat_response")) or "Проверьте статус в кабинете.",
                f"Оплата: {billing_label}.",
            ]
        )
    else:
        lines.extend(
            [
                "Статус обновления изменился.",
                _clean_text(result.get("chat_response")) or "Проверьте результат в кабинете.",
                f"Оплата: {billing_label}.",
            ]
        )

    lines.extend(
        [
            "",
            "Следующий шаг:",
            "• если есть отзывы без ответа — напишите «подготовь ответы на отзывы»;",
            "• публикация в карты остаётся ручной: LocalOS готовит черновики, вы копируете и вставляете сами.",
            "Кабинет: https://localos.pro/dashboard/operator",
        ]
    )
    return "\n".join(lines)


def dispatch_operator_refresh_telegram_followup(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    queue_id: str,
    send_func: Callable[[str, str], bool],
    commit_func: Callable[[], None] | None = None,
) -> dict[str, Any]:
    clean_business_id = _clean_text(business_id)
    clean_user_id = _clean_text(user_id)
    clean_queue_id = _clean_text(queue_id)
    if not clean_business_id or not clean_user_id or not clean_queue_id:
        return {"status": "skipped", "reason": "queue_identity_missing", "sent": False}

    reservation = _load_refresh_reservation(
        cursor,
        business_id=clean_business_id,
        user_id=clean_user_id,
        queue_id=clean_queue_id,
    )
    if not reservation:
        return {"status": "skipped", "reason": "operator_reservation_not_found", "sent": False}

    metadata = _json_dict(reservation.get("metadata"))
    if metadata.get(FOLLOWUP_ATTEMPTED_AT_KEY) or metadata.get(FOLLOWUP_DELIVERED_AT_KEY):
        return {
            "status": "skipped",
            "reason": "telegram_refresh_followup_already_attempted",
            "reservation_id": reservation.get("id"),
            "sent": False,
        }

    contact = _load_owner_contact(cursor, business_id=clean_business_id, user_id=clean_user_id)
    telegram_id = _clean_text(contact.get("telegram_id"))
    if not telegram_id:
        return {
            "status": "skipped",
            "reason": "owner_telegram_id_missing",
            "reservation_id": reservation.get("id"),
            "sent": False,
        }

    result = build_refresh_result_status(
        cursor,
        business_id=clean_business_id,
        user_id=clean_user_id,
        queue_id=clean_queue_id,
    )
    result_status = _clean_text(result.get("status"))
    if result_status == "processing":
        return {
            "status": "skipped",
            "reason": "refresh_still_processing",
            "reservation_id": reservation.get("id"),
            "sent": False,
        }

    attempted_at = _utc_now_iso()
    reservation_id = _clean_text(reservation.get("id"))
    _store_followup_metadata(
        cursor,
        reservation_id=reservation_id,
        patch={
            FOLLOWUP_ATTEMPTED_AT_KEY: attempted_at,
            FOLLOWUP_STATUS_KEY: "attempted",
        },
    )
    if commit_func:
        commit_func()

    text = format_refresh_followup_text(result, business_name=_clean_text(contact.get("business_name")))
    delivered = bool(send_func(telegram_id, text))
    delivered_at = _utc_now_iso() if delivered else ""
    _store_followup_metadata(
        cursor,
        reservation_id=reservation_id,
        patch={
            FOLLOWUP_STATUS_KEY: "delivered" if delivered else "failed",
            FOLLOWUP_DELIVERED_AT_KEY: delivered_at,
        },
    )
    if commit_func:
        commit_func()
    return {
        "status": "sent" if delivered else "failed",
        "reason": "" if delivered else "telegram_send_failed",
        "reservation_id": reservation_id,
        "telegram_id": telegram_id,
        "sent": delivered,
        "result_status": result_status,
    }
