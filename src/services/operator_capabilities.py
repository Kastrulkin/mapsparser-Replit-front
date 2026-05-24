from __future__ import annotations

from typing import Any

from services.operator_manual_review import _build_ui_action, _clean_text, _row_to_dict


REVIEWS_URL = "/dashboard/card?tab=reviews&review_filter=needs_reply"
BILLING_URL = "/dashboard/billing"


def classify_operator_help_intent(message: Any) -> bool:
    text = _clean_text(message).lower()
    if not text:
        return False
    return (
        "что уме" in text
        or "что ты уме" in text
        or "что может" in text
        or "какие команды" in text
        or "помощ" in text
        or text in {"help", "/help"}
    )


def classify_unanswered_reviews_status_intent(message: Any) -> bool:
    text = _clean_text(message).lower()
    if not text:
        return False
    has_reviews = "отзыв" in text
    asks_status = (
        "есть" in text
        or "сколько" in text
        or "покажи" in text
        or "провер" in text
        or "посмотри" in text
        or "статус" in text
    )
    mentions_unanswered = "без ответа" in text or "неотвеч" in text or "не отвеч" in text
    asks_generation = "подготов" in text or "сгенер" in text or "напиши ответ" in text
    asks_fresh_refresh = "новые" in text or "свеж" in text or "обнов" in text
    return has_reviews and asks_status and mentions_unanswered and not asks_generation and not asks_fresh_refresh


def build_operator_help_response() -> dict[str, Any]:
    commands = [
        "Проверить, есть ли отзывы без ответа в сохранённой базе.",
        "Проверить новые отзывы через платное read-only обновление карт.",
        "Обновить или спарсить данные карточки через тот же read-only refresh.",
        "Подготовить ответы на отзывы без ответа.",
        "Добавить присланный отзыв в список и сразу подготовить ответ.",
        "Подготовить новость для карточки или сайта.",
        "Подготовить пост для соцсетей.",
        "Оптимизировать названия и описания услуг.",
        "Применить подтверждённые предложения по услугам внутри LocalOS.",
    ]
    return {
        "status": "completed",
        "intent": "operator_help",
        "chat_response": "Я могу управлять основными сценариями LocalOS через чат:\n- " + "\n- ".join(commands),
        "capabilities": commands,
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_publication_only": True,
        "paid_actions_performed": False,
        "credit_charged": False,
        "blocked_reasons": [],
        "ui_actions": [
            _build_ui_action("open_reviews", "Открыть отзывы", href=REVIEWS_URL),
            _build_ui_action("open_billing", "Пополнить счёт", href=BILLING_URL),
        ],
    }


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) AS table_ref", (f"public.{table_name}",))
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return bool(row.get("table_ref") or row.get("to_regclass"))


def get_unanswered_reviews_status(cursor: Any, *, business_id: str, limit: Any = 5) -> dict[str, Any]:
    try:
        clean_limit = int(limit or 5)
    except Exception:
        clean_limit = 5
    clean_limit = max(1, min(clean_limit, 10))

    if not _table_exists(cursor, "externalbusinessreviews"):
        return {
            "status": "completed",
            "intent": "unanswered_reviews_status",
            "chat_response": "В сохранённой базе пока нет таблицы отзывов. Можно запустить проверку новых отзывов через карты.",
            "reviews_found": 0,
            "unanswered_reviews_count": 0,
            "reviews": [],
            "external_calls_performed": False,
            "external_writes_performed": False,
            "manual_publication_only": True,
            "paid_actions_performed": False,
            "credit_charged": False,
            "blocked_reasons": [],
            "ui_actions": [_build_ui_action("open_reviews", "Открыть отзывы", href=REVIEWS_URL)],
        }

    cursor.execute(
        """
        SELECT COUNT(*) AS cnt
        FROM externalbusinessreviews
        WHERE business_id = %s
          AND COALESCE(TRIM(text), '') <> ''
          AND COALESCE(TRIM(response_text), '') = ''
        """,
        (business_id,),
    )
    count_row = _row_to_dict(cursor, cursor.fetchone()) or {}
    try:
        unanswered_count = int(count_row.get("cnt") or 0)
    except Exception:
        unanswered_count = 0

    cursor.execute(
        """
        SELECT id, source, external_review_id, rating, author_name, text, published_at, created_at
        FROM externalbusinessreviews
        WHERE business_id = %s
          AND COALESCE(TRIM(text), '') <> ''
          AND COALESCE(TRIM(response_text), '') = ''
        ORDER BY published_at DESC NULLS LAST, created_at DESC
        LIMIT %s
        """,
        (business_id, clean_limit),
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
                "published_at": item.get("published_at"),
                "created_at": item.get("created_at"),
                "has_response": False,
            }
        )

    if unanswered_count > 0:
        chat_response = (
            f"Да, в сохранённой базе есть отзывы без ответа: {unanswered_count}. "
            "Могу подготовить черновики ответов командой «подготовь ответы на отзывы»."
        )
    else:
        chat_response = (
            "По сохранённой базе сейчас нет отзывов без ответа. "
            "Если нужно проверить карты заново, напишите «проверь новые отзывы»."
        )

    return {
        "status": "completed",
        "intent": "unanswered_reviews_status",
        "chat_response": chat_response,
        "reviews_found": unanswered_count,
        "unanswered_reviews_count": unanswered_count,
        "new_unanswered_reviews_count": unanswered_count,
        "new_reviews_count": len(reviews),
        "new_reviews": reviews,
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_publication_only": True,
        "paid_actions_performed": False,
        "credit_charged": False,
        "blocked_reasons": [],
        "ui_actions": [
            _build_ui_action("open_reviews", "Открыть отзывы", href=REVIEWS_URL),
            _build_ui_action("generate_review_replies", "Подготовить ответы", payload={"action_key": "review_replies_generate"}),
        ],
    }
