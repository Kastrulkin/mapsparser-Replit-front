from __future__ import annotations

import hashlib
import json
from typing import Any, Callable

from services.gigachat_client import analyze_text_with_gigachat
from services.operator_credit_reservation import finalize_reserved_action_credits, reserve_paid_action_credits
from services.operator_paid_preflight import build_paid_action_preflight


MANUAL_REVIEW_SOURCE = "manual_chat"
MANUAL_REVIEW_ACTION_KEY = "review_replies_generate"
MANUAL_REVIEW_ESTIMATED_CREDITS = 1
MANUAL_REVIEW_ACTUAL_CREDITS = 1
BILLING_URL = "/dashboard/billing"


def _stable_id(*parts: Any) -> str:
    raw = "|".join(str(part or "").strip() for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


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
        return {columns[idx]: row[idx] for idx in range(min(len(columns), len(row)))}
    return None


def _extract_review_text(message: Any) -> str:
    text = _clean_text(message)
    if not text:
        return ""
    markers = (
        "добавь новый отзыв в список и сгенерируй ответ:",
        "добавь новый отзыв и сгенерируй ответ:",
        "добавь отзыв и сгенерируй ответ:",
        "сгенерируй ответ:",
        "отзыв:",
    )
    lowered = text.lower()
    for marker in markers:
        index = lowered.find(marker)
        if index >= 0:
            return text[index + len(marker):].strip()
    return text


def classify_operator_chat_intent(message: Any) -> str:
    text = _clean_text(message).lower()
    if "отзыв" in text and ("сгенер" in text or "ответ" in text or "добав" in text):
        return "manual_review_add_and_reply_generate"
    return "unsupported"


def _build_review_reply_prompt(review_text: str) -> str:
    return (
        "Ты - внимательный менеджер локального бизнеса. "
        "Сгенерируй короткий, тёплый и профессиональный ответ на отзыв. "
        "Не выдумывай факты, не обещай лишнего, не упоминай автоматизацию. "
        "До 350 символов. Верни СТРОГО JSON: {\"reply\": \"текст ответа\"}\n\n"
        f"Отзыв клиента:\n{review_text[:1500]}"
    )


def _extract_reply(value: Any) -> str:
    text = _clean_text(value)
    if not text:
        return ""
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            parsed = json.loads(text[start:end])
            if isinstance(parsed, dict):
                return _clean_text(parsed.get("reply"))
        except Exception:
            pass
    return text


def _default_reply_generator(prompt: str, *, business_id: str, user_id: str) -> str:
    return analyze_text_with_gigachat(
        prompt,
        task_type="review_reply",
        business_id=business_id,
        user_id=user_id,
    )


def _insert_manual_review(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    review_text: str,
    author_name: str | None = None,
    rating: Any = None,
) -> dict[str, Any]:
    external_review_id = _stable_id("manual_review", business_id, review_text)
    review_id = _stable_id("externalbusinessreviews", business_id, MANUAL_REVIEW_SOURCE, external_review_id)
    raw_payload = {
        "source": MANUAL_REVIEW_SOURCE,
        "entrypoint": "operator_chat",
        "created_by_user_id": user_id,
    }
    cursor.execute(
        """
        INSERT INTO externalbusinessreviews (
            id, business_id, source, external_review_id, rating, author_name,
            text, published_at, response_text, response_at, raw_payload,
            created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP, NULL, NULL, %s, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
        ON CONFLICT (business_id, source, external_review_id)
        DO UPDATE SET
            text = EXCLUDED.text,
            rating = COALESCE(EXCLUDED.rating, externalbusinessreviews.rating),
            author_name = COALESCE(EXCLUDED.author_name, externalbusinessreviews.author_name),
            raw_payload = EXCLUDED.raw_payload,
            updated_at = CURRENT_TIMESTAMP
        RETURNING id, business_id, source, external_review_id, rating, author_name, text, created_at
        """,
        (
            review_id,
            business_id,
            MANUAL_REVIEW_SOURCE,
            external_review_id,
            rating,
            _clean_text(author_name) or "Клиент",
            review_text,
            json.dumps(raw_payload, ensure_ascii=False),
        ),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    if not row:
        row = {
            "id": review_id,
            "business_id": business_id,
            "source": MANUAL_REVIEW_SOURCE,
            "external_review_id": external_review_id,
            "rating": rating,
            "author_name": _clean_text(author_name) or "Клиент",
            "text": review_text,
        }
    return row


def _upsert_reply_draft(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    review: dict[str, Any],
    reply_text: str,
) -> dict[str, Any]:
    review_id = _clean_text(review.get("id"))
    draft_id = _stable_id("reviewreplydrafts", business_id, review_id)
    cursor.execute(
        """
        INSERT INTO reviewreplydrafts (
            id, business_id, review_id, user_id, source, rating, author_name,
            review_text, generated_text, status, tone, prompt_key, prompt_version,
            created_at, updated_at
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 'draft', %s, %s, %s, NOW(), NOW())
        ON CONFLICT (review_id)
        DO UPDATE SET
            generated_text = EXCLUDED.generated_text,
            status = 'draft',
            tone = EXCLUDED.tone,
            prompt_key = EXCLUDED.prompt_key,
            prompt_version = EXCLUDED.prompt_version,
            updated_at = NOW()
        RETURNING id, business_id, review_id, generated_text, status, created_at, updated_at
        """,
        (
            draft_id,
            business_id,
            review_id,
            user_id,
            review.get("source"),
            review.get("rating"),
            review.get("author_name"),
            review.get("text"),
            reply_text,
            "professional",
            "operator_manual_review_reply",
            "v1",
        ),
    )
    row = _row_to_dict(cursor, cursor.fetchone()) or {}
    if not row:
        row = {
            "id": draft_id,
            "business_id": business_id,
            "review_id": review_id,
            "generated_text": reply_text,
            "status": "draft",
        }
    return row


def process_operator_chat_message(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    message: Any,
    channel: str = "web",
    reply_generator: Callable[..., str] | None = None,
) -> dict[str, Any]:
    intent = classify_operator_chat_intent(message)
    if intent != "manual_review_add_and_reply_generate":
        return {
            "status": "unsupported",
            "intent": intent,
            "message": _clean_text(message),
            "reply_text": "",
            "chat_response": "Пока я умею добавлять отзыв из чата и готовить черновик ответа.",
            "blocked_reasons": ["unsupported_operator_chat_intent"],
        }

    review_text = _extract_review_text(message)
    if len(review_text) < 10:
        return {
            "status": "blocked",
            "intent": intent,
            "reply_text": "",
            "chat_response": "Пришлите текст отзыва, чтобы я добавил его в список и подготовил ответ.",
            "blocked_reasons": ["review_text_required"],
        }

    preflight = build_paid_action_preflight(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=MANUAL_REVIEW_ACTION_KEY,
        estimated_credits=MANUAL_REVIEW_ESTIMATED_CREDITS,
    )
    if preflight.get("status") != "ready":
        blocked = list(preflight.get("blocked_reasons") or [])
        if "insufficient_balance" in blocked:
            return {
                "status": "blocked",
                "intent": intent,
                "reply_text": "",
                "preflight": preflight,
                "blocked_reasons": blocked,
                "chat_response": "Недостаточно кредитов для генерации ответа. Пополните счёт или выберите тариф: /dashboard/billing",
                "billing_url": BILLING_URL,
            }
        return {
            "status": "blocked",
            "intent": intent,
            "reply_text": "",
            "preflight": preflight,
            "blocked_reasons": blocked,
            "chat_response": "Не удалось запустить генерацию ответа. Причины: " + ", ".join(blocked),
        }

    idempotency_key = _stable_id("operator_manual_review_reply", business_id, user_id, review_text)
    reservation = reserve_paid_action_credits(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=MANUAL_REVIEW_ACTION_KEY,
        estimated_credits=MANUAL_REVIEW_ESTIMATED_CREDITS,
        idempotency_key=idempotency_key,
        metadata={"source": "operator_manual_review", "channel": channel},
    )
    if reservation.get("status") != "reserved":
        blocked = list(reservation.get("blocked_reasons") or [])
        return {
            "status": "blocked",
            "intent": intent,
            "reply_text": "",
            "preflight": preflight,
            "reservation_result": reservation,
            "blocked_reasons": blocked,
            "chat_response": "Не удалось зарезервировать кредиты для генерации. Причины: " + ", ".join(blocked),
        }

    review = _insert_manual_review(
        cursor,
        business_id=business_id,
        user_id=user_id,
        review_text=review_text,
    )

    generator = reply_generator or _default_reply_generator
    try:
        generated = generator(
            _build_review_reply_prompt(review_text),
            business_id=business_id,
            user_id=user_id,
        )
        reply_text = _extract_reply(generated)
    except Exception:
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
            "intent": intent,
            "review": review,
            "reply_text": "",
            "preflight": preflight,
            "reservation_result": reservation,
            "finalization_result": release,
            "blocked_reasons": ["reply_generation_failed"],
            "chat_response": "Отзыв добавлен, но ответ не удалось сгенерировать. Кредиты не списаны.",
        }

    if not reply_text:
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
            "intent": intent,
            "review": review,
            "reply_text": "",
            "preflight": preflight,
            "reservation_result": reservation,
            "finalization_result": release,
            "blocked_reasons": ["empty_generated_reply"],
            "chat_response": "Отзыв добавлен, но модель вернула пустой ответ. Кредиты не списаны.",
        }

    draft = _upsert_reply_draft(
        cursor,
        business_id=business_id,
        user_id=user_id,
        review=review,
        reply_text=reply_text,
    )
    finalization = finalize_reserved_action_credits(
        cursor,
        reservation_id=_clean_text(reservation.get("reservation_id")),
        business_id=business_id,
        user_id=user_id,
        actual_credits=MANUAL_REVIEW_ACTUAL_CREDITS,
        finalization_mode="charge",
        external_id=idempotency_key,
    )

    charged = int(finalization.get("charge_credits") or 0)
    response_lines = [
        "Добавил отзыв в список и подготовил черновик ответа.",
        "",
        "Ответ:",
        reply_text,
        "",
        f"Списано кредитов: {charged}.",
        "Публикация в карты пока вручную: скопируйте ответ и вставьте его в кабинете карты.",
    ]
    return {
        "status": "completed",
        "intent": intent,
        "review": review,
        "draft": draft,
        "reply_text": reply_text,
        "preflight": preflight,
        "reservation_result": reservation,
        "finalization_result": finalization,
        "credit_charged": finalization.get("status") == "charged",
        "charged_credits": charged,
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_publication_only": True,
        "chat_response": "\n".join(response_lines),
        "blocked_reasons": [],
    }
