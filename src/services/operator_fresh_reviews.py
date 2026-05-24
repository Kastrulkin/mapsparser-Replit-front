from __future__ import annotations

from typing import Any

from services.operator_map_refresh import enqueue_paid_operator_map_refresh
from services.operator_manual_review import _build_ui_action
from services.operator_news_generation import _clean_text, _row_to_dict


FRESH_REVIEWS_INTENT = "fresh_reviews_refresh"
REVIEWS_URL = "/dashboard/card?tab=reviews&review_filter=needs_reply"


def classify_fresh_reviews_intent(message: Any) -> bool:
    text = _clean_text(message).lower()
    if not text:
        return False
    has_reviews = "отзыв" in text
    has_refresh = "проверь" in text or "проверить" in text or "обнов" in text or "свеж" in text or "новые" in text
    return has_reviews and has_refresh


def _load_review_snapshot(cursor: Any, *, business_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT
            COUNT(*) AS total,
            SUM(CASE WHEN COALESCE(TRIM(response_text), '') = '' THEN 1 ELSE 0 END) AS without_response,
            MAX(COALESCE(published_at, updated_at, created_at)) AS latest_seen_at
        FROM externalbusinessreviews
        WHERE business_id = %s
        """,
        (business_id,),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    try:
        total = int(row.get("total") or 0)
    except Exception:
        total = 0
    try:
        without_response = int(row.get("without_response") or 0)
    except Exception:
        without_response = 0
    return {
        "total": total,
        "without_response": without_response,
        "latest_seen_at": row.get("latest_seen_at"),
    }


def refresh_reviews_from_operator(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    explicit_url: Any = None,
    channel: str = "web",
    estimated_credits: Any = None,
) -> dict[str, Any]:
    before = _load_review_snapshot(cursor, business_id=business_id)
    refresh = enqueue_paid_operator_map_refresh(
        cursor,
        business_id=business_id,
        user_id=user_id,
        explicit_url=explicit_url,
        estimated_credits=estimated_credits,
    )
    status = "queued" if refresh.get("status") == "queued" else "blocked"
    if status == "queued":
        chat_response = "\n".join(
            [
                "Запустил платное read-only обновление карты для проверки новых отзывов.",
                f"Сейчас в сохранённых данных отзывов без ответа: {before.get('without_response')}.",
                f"Зарезервировано до {refresh.get('estimated_credits') or 'N'} кредитов; фактическое списание будет после результата Apify.",
                "Когда обновление завершится, нажмите «Проверить результат обновления» или напишите: «подготовь ответы на отзывы».",
            ]
        )
    else:
        blocked = list(refresh.get("blocked_reasons") or [])
        if "insufficient_balance" in blocked or "insufficient_unreserved_balance" in blocked:
            chat_response = "\n".join(
                [
                    "Для обновления карт не хватает кредитов.",
                    "Пополните счёт или выберите тариф, после этого можно снова запустить проверку новых отзывов.",
                ]
            )
        elif "operator_apify_refresh_disabled" in blocked:
            chat_response = "\n".join(
                [
                    "Проверка новых отзывов требует read-only обновления карт.",
                    "Сейчас runtime обновления выключен, поэтому я показываю последние сохранённые данные.",
                    f"Отзывы без ответа в сохранённых данных: {before.get('without_response')}.",
                ]
            )
        else:
            chat_response = "Не удалось запустить проверку новых отзывов. Причины: " + ", ".join(blocked)

    return {
        "status": status,
        "intent": FRESH_REVIEWS_INTENT,
        "chat_response": chat_response,
        "review_snapshot_before": before,
        "refresh_result": refresh,
        "queue_id": refresh.get("queue_id"),
        "reservation_id": refresh.get("reservation_id"),
        "estimated_credits": refresh.get("estimated_credits"),
        "balance_credits": refresh.get("balance_credits"),
        "billing_url": refresh.get("billing_url"),
        "blocked_reasons": list(refresh.get("blocked_reasons") or []),
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_publication_only": True,
        "paid_actions_performed": bool(refresh.get("paid_actions_performed")),
        "credit_reserved": bool((refresh.get("side_effects") or {}).get("credit_reserved")),
        "credit_charged": False,
        "channel": channel,
        "ui_actions": [
            _build_ui_action("open_reviews", "Открыть отзывы", href=REVIEWS_URL),
            _build_ui_action("generate_review_replies", "Подготовить ответы", payload={"action_key": "review_replies_generate"}),
        ],
    }
