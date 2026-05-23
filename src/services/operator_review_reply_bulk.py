from __future__ import annotations

from typing import Any, Callable

from services.operator_credit_reservation import finalize_reserved_action_credits, reserve_paid_action_credits
from services.operator_manual_review import (
    BILLING_URL,
    MANUAL_REVIEW_ACTION_KEY,
    REVIEWS_URL,
    _build_review_reply_prompt,
    _build_ui_action,
    _clean_text,
    _default_reply_generator,
    _extract_reply,
    _row_to_dict,
    _stable_id,
    _upsert_reply_draft,
)
from services.operator_paid_preflight import build_paid_action_preflight


BULK_REVIEW_REPLY_MAX_LIMIT = 5
BULK_REVIEW_REPLY_CREDITS_PER_DRAFT = 1


def classify_bulk_review_reply_intent(message: Any) -> bool:
    text = _clean_text(message).lower()
    if "добав" in text:
        return False
    if "отзывы" not in text and "отзывов" not in text:
        return False
    return "подготов" in text or "сгенер" in text or "ответ" in text


def _positive_limit(value: Any) -> int:
    try:
        parsed = int(value or BULK_REVIEW_REPLY_MAX_LIMIT)
    except Exception:
        return BULK_REVIEW_REPLY_MAX_LIMIT
    if parsed <= 0:
        return BULK_REVIEW_REPLY_MAX_LIMIT
    return min(parsed, BULK_REVIEW_REPLY_MAX_LIMIT)


def _table_exists(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s)", (f"public.{table_name}",))
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    return bool(row.get("to_regclass") or row.get("table_ref"))


def _load_unanswered_reviews(cursor: Any, *, business_id: str, limit: int) -> list[dict[str, Any]]:
    if not _table_exists(cursor, "externalbusinessreviews"):
        return []
    if not _table_exists(cursor, "reviewreplydrafts"):
        return []
    cursor.execute(
        """
        SELECT id, business_id, source, external_review_id, rating, author_name, text, published_at
        FROM externalbusinessreviews reviews
        WHERE reviews.business_id = %s
          AND COALESCE(reviews.text, '') <> ''
          AND COALESCE(reviews.response_text, '') = ''
          AND NOT EXISTS (
              SELECT 1
              FROM reviewreplydrafts drafts
              WHERE drafts.review_id = reviews.id
                AND drafts.status IN ('draft', 'generated', 'pending_review', 'manual_published')
          )
        ORDER BY reviews.published_at DESC NULLS LAST, reviews.created_at DESC
        LIMIT %s
        """,
        (business_id, limit),
    )
    reviews: list[dict[str, Any]] = []
    for row in cursor.fetchall() or []:
        item = _row_to_dict(cursor, row) or {}
        if _clean_text(item.get("id")) and _clean_text(item.get("text")):
            reviews.append(item)
    return reviews


def generate_review_reply_drafts_for_unanswered_reviews(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    limit: Any = BULK_REVIEW_REPLY_MAX_LIMIT,
    channel: str = "web",
    reply_generator: Callable[..., str] | None = None,
) -> dict[str, Any]:
    clean_limit = _positive_limit(limit)
    reviews = _load_unanswered_reviews(cursor, business_id=business_id, limit=clean_limit)
    if not reviews:
        return {
            "status": "completed",
            "intent": "bulk_review_replies_generate",
            "chat_response": "По сохранённым данным нет отзывов без ответа, для которых ещё нет черновика.",
            "reviews_found": 0,
            "drafts": [],
            "charged_credits": 0,
            "credit_charged": False,
            "external_calls_performed": False,
            "external_writes_performed": False,
            "manual_publication_only": True,
            "blocked_reasons": [],
        }

    estimated_credits = len(reviews) * BULK_REVIEW_REPLY_CREDITS_PER_DRAFT
    preflight = build_paid_action_preflight(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=MANUAL_REVIEW_ACTION_KEY,
        estimated_credits=estimated_credits,
    )
    if preflight.get("status") != "ready":
        blocked = list(preflight.get("blocked_reasons") or [])
        if "insufficient_balance" in blocked:
            return {
                "status": "blocked",
                "intent": "bulk_review_replies_generate",
                "chat_response": "Недостаточно кредитов для генерации ответов. Пополните счёт или выберите тариф: /dashboard/billing",
                "billing_url": BILLING_URL,
                "preflight": preflight,
                "reviews_found": len(reviews),
                "drafts": [],
                "charged_credits": 0,
                "credit_charged": False,
                "blocked_reasons": blocked,
                "ui_actions": [_build_ui_action("open_billing", "Пополнить счёт", href=BILLING_URL)],
            }
        return {
            "status": "blocked",
            "intent": "bulk_review_replies_generate",
            "chat_response": "Не удалось запустить генерацию ответов. Причины: " + ", ".join(blocked),
            "preflight": preflight,
            "reviews_found": len(reviews),
            "drafts": [],
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": blocked,
        }

    review_ids = ",".join(_clean_text(review.get("id")) for review in reviews)
    idempotency_key = _stable_id("operator_bulk_review_replies", business_id, user_id, review_ids)
    reservation = reserve_paid_action_credits(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=MANUAL_REVIEW_ACTION_KEY,
        estimated_credits=estimated_credits,
        idempotency_key=idempotency_key,
        metadata={"source": "operator_bulk_review_reply", "channel": channel, "review_count": len(reviews)},
    )
    if reservation.get("status") != "reserved":
        blocked = list(reservation.get("blocked_reasons") or [])
        return {
            "status": "blocked",
            "intent": "bulk_review_replies_generate",
            "chat_response": "Не удалось зарезервировать кредиты для генерации. Причины: " + ", ".join(blocked),
            "preflight": preflight,
            "reservation_result": reservation,
            "reviews_found": len(reviews),
            "drafts": [],
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": blocked,
        }

    generator = reply_generator or _default_reply_generator
    drafts: list[dict[str, Any]] = []
    failures: list[dict[str, Any]] = []
    for review in reviews:
        review_text = _clean_text(review.get("text"))
        try:
            generated = generator(
                _build_review_reply_prompt(review_text),
                business_id=business_id,
                user_id=user_id,
            )
            reply_text = _extract_reply(generated)
            if not reply_text:
                failures.append({"review_id": _clean_text(review.get("id")), "reason": "empty_generated_reply"})
                continue
            draft = _upsert_reply_draft(
                cursor,
                business_id=business_id,
                user_id=user_id,
                review=review,
                reply_text=reply_text,
            )
            drafts.append(draft)
        except Exception:
            failures.append({"review_id": _clean_text(review.get("id")), "reason": "reply_generation_failed"})

    if not drafts:
        release = finalize_reserved_action_credits(
            cursor,
            reservation_id=_clean_text(reservation.get("reservation_id")),
            business_id=business_id,
            user_id=user_id,
            finalization_mode="release",
            external_id=idempotency_key,
        )
        return {
            "status": "blocked",
            "intent": "bulk_review_replies_generate",
            "chat_response": "Отзывы найдены, но ответы не удалось сгенерировать. Кредиты не списаны.",
            "preflight": preflight,
            "reservation_result": reservation,
            "finalization_result": release,
            "reviews_found": len(reviews),
            "drafts": [],
            "failures": failures,
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": ["reply_generation_failed"],
        }

    actual_credits = len(drafts) * BULK_REVIEW_REPLY_CREDITS_PER_DRAFT
    finalization = finalize_reserved_action_credits(
        cursor,
        reservation_id=_clean_text(reservation.get("reservation_id")),
        business_id=business_id,
        user_id=user_id,
        actual_credits=actual_credits,
        finalization_mode="charge",
        external_id=idempotency_key,
    )
    charged = int(finalization.get("charge_credits") or 0)
    response_lines = [
        f"Подготовил черновики ответов: {len(drafts)}.",
        f"Списано кредитов: {charged}.",
        "Публикация в карты пока вручную: скопируйте ответы и вставьте их в кабинете карты.",
    ]
    if failures:
        response_lines.append(f"Не удалось обработать отзывов: {len(failures)}.")

    return {
        "status": "completed",
        "intent": "bulk_review_replies_generate",
        "chat_response": "\n".join(response_lines),
        "preflight": preflight,
        "reservation_result": reservation,
        "finalization_result": finalization,
        "reviews_found": len(reviews),
        "drafts": drafts,
        "failures": failures,
        "charged_credits": charged,
        "credit_charged": finalization.get("status") == "charged",
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_publication_only": True,
        "ui_actions": [
            _build_ui_action("open_reviews", "Открыть отзывы", href=REVIEWS_URL),
        ],
        "blocked_reasons": [],
    }


def format_bulk_review_reply_result_for_telegram(result: dict[str, Any]) -> str:
    response = _clean_text(result.get("chat_response")) or "Команда обработана."
    drafts = result.get("drafts") if isinstance(result.get("drafts"), list) else []
    if not drafts:
        return response
    lines = [response]
    for index, draft in enumerate(drafts[:5], start=1):
        if not isinstance(draft, dict):
            continue
        text = _clean_text(draft.get("generated_text"))
        if text:
            lines.extend(["", f"Ответ {index}:", text])
    lines.extend(
        [
            "",
            "Публикация в карты остаётся ручной: скопируйте ответы и вставьте их в кабинете площадки.",
            "LocalOS не публиковал ответы во внешние системы.",
        ]
    )
    return "\n".join(lines)
