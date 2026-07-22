from __future__ import annotations

import json
from typing import Any, Callable

from services.llm import analyze_text_with_gigachat
from services.operator_credit_reservation import finalize_reserved_action_credits, reserve_paid_action_credits
from services.operator_manual_review import BILLING_URL, _build_ui_action, _clean_text, _stable_id
from services.operator_paid_preflight import build_paid_action_preflight


OPERATOR_INTENT_CLASSIFY_ACTION_KEY = "operator_intent_classify"
OPERATOR_INTENT_CLASSIFY_ESTIMATED_CREDITS = 1
OPERATOR_INTENT_CLASSIFY_ACTUAL_CREDITS = 1

SUPPORTED_AI_INTENTS = {
    "card_refresh",
    "review_replies_generate",
    "manual_review_add_and_reply",
    "news_generate",
    "social_post_generate",
    "services_optimize",
    "services_apply",
    "operator_help",
    "unknown",
}


AI_ROUTER_ACTION_MARKERS = (
    "посмотри",
    "проверь",
    "обнов",
    "спарс",
    "парс",
    "собер",
    "подтян",
    "загруз",
    "получи",
    "актуализ",
    "синхрониз",
    "подготов",
    "сгенер",
    "напиши",
    "создай",
    "сделай",
    "ответ",
    "оптимиз",
    "улучш",
    "примени",
    "надо",
    "нужно",
)

AI_ROUTER_SCOPE_MARKERS = (
    "карточ",
    "аккаунт",
    "профил",
    "данные",
    "карт",
    "яндекс",
    "2гис",
    "2gis",
    "google",
    "отзыв",
    "ответ",
    "клиент",
    "люд",
    "услуг",
    "новост",
    "пост",
    "соцсет",
    "салон",
    "бизнес",
)


def should_use_ai_intent_router(message: Any) -> bool:
    text = _clean_text(message).lower()
    if not text:
        return False
    if len(text) < 5:
        return False
    has_action = any(marker in text for marker in AI_ROUTER_ACTION_MARKERS)
    has_scope = any(marker in text for marker in AI_ROUTER_SCOPE_MARKERS)
    return has_action and has_scope


def _build_intent_prompt(message: str) -> str:
    return "\n".join(
        [
            "Ты классификатор команд LocalOS Operator.",
            "Верни СТРОГО JSON: {\"intent\":\"...\"}.",
            "Не выполняй команду, не пиши объяснений, не добавляй других ключей.",
            "",
            "Доступные intent:",
            "- card_refresh: обновить/спарсить карточку, профиль, аккаунт, карты, свежие данные, новые отзывы.",
            "- review_replies_generate: подготовить ответы на уже сохранённые отзывы без ответа.",
            "- manual_review_add_and_reply: пользователь прислал текст нового отзыва и просит добавить его и подготовить ответ.",
            "- news_generate: подготовить новость.",
            "- social_post_generate: подготовить пост для соцсетей.",
            "- services_optimize: улучшить названия или описания услуг.",
            "- services_apply: применить уже подготовленные предложения по услугам.",
            "- operator_help: пользователь спрашивает, что ты умеешь или какие команды доступны.",
            "- unknown: всё остальное.",
            "",
            f"Команда пользователя:\n{message[:1500]}",
        ]
    )


def _default_intent_generator(prompt: str, *, business_id: str, user_id: str) -> str:
    return analyze_text_with_gigachat(
        prompt,
        task_type="operator_intent_classify",
        business_id=business_id,
        user_id=user_id,
    )


def normalize_ai_intent(value: Any) -> str:
    raw = _clean_text(value).lower()
    if not raw:
        return "unknown"
    parsed: Any = None
    try:
        parsed = json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw[start:end])
            except Exception:
                parsed = None
    if isinstance(parsed, dict):
        raw = _clean_text(parsed.get("intent")).lower()
    cleaned = raw.strip().replace("-", "_").replace(" ", "_")
    aliases = {
        "map_reviews_refresh": "card_refresh",
        "fresh_reviews_refresh": "card_refresh",
        "map_card_refresh": "card_refresh",
        "review_reply_generate": "review_replies_generate",
        "bulk_review_replies_generate": "review_replies_generate",
        "manual_review_add_and_reply_generate": "manual_review_add_and_reply",
        "help": "operator_help",
    }
    normalized = aliases.get(cleaned, cleaned)
    return normalized if normalized in SUPPORTED_AI_INTENTS else "unknown"


def classify_operator_intent_with_ai(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    message: Any,
    channel: str = "web",
    intent_generator: Callable[..., str] | None = None,
) -> dict[str, Any]:
    clean_message = _clean_text(message)
    preflight = build_paid_action_preflight(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=OPERATOR_INTENT_CLASSIFY_ACTION_KEY,
        estimated_credits=OPERATOR_INTENT_CLASSIFY_ESTIMATED_CREDITS,
    )
    if preflight.get("status") != "ready":
        blocked = list(preflight.get("blocked_reasons") or [])
        if "insufficient_balance" in blocked or "insufficient_unreserved_balance" in blocked:
            chat_response = (
                "Не смог разобрать команду через AI-роутер: не хватает кредитов. "
                "Пополните счёт или используйте одну из команд: «обнови карточку», "
                "«подготовь ответы на отзывы», «подготовь новость», «оптимизируй услуги»."
            )
        else:
            chat_response = "Не удалось разобрать команду через AI-роутер. Причины: " + ", ".join(blocked)
        return {
            "status": "blocked",
            "intent": "operator_intent_ai_router",
            "normalized_intent": "unknown",
            "chat_response": chat_response,
            "preflight": preflight,
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": blocked,
            "billing_url": BILLING_URL if "insufficient_balance" in blocked or "insufficient_unreserved_balance" in blocked else "",
            "ui_actions": [_build_ui_action("open_billing", "Пополнить счёт", href=BILLING_URL)]
            if "insufficient_balance" in blocked or "insufficient_unreserved_balance" in blocked
            else [],
        }

    idempotency_key = _stable_id("operator_intent_classify", business_id, user_id, clean_message)
    reservation = reserve_paid_action_credits(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=OPERATOR_INTENT_CLASSIFY_ACTION_KEY,
        estimated_credits=OPERATOR_INTENT_CLASSIFY_ESTIMATED_CREDITS,
        idempotency_key=idempotency_key,
        metadata={"source": "operator_intent_ai_router", "channel": channel},
    )
    if reservation.get("status") != "reserved":
        blocked = list(reservation.get("blocked_reasons") or [])
        return {
            "status": "blocked",
            "intent": "operator_intent_ai_router",
            "normalized_intent": "unknown",
            "chat_response": "Не удалось зарезервировать кредиты для AI-роутера. Причины: " + ", ".join(blocked),
            "preflight": preflight,
            "reservation_result": reservation,
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": blocked,
        }

    generator = intent_generator or _default_intent_generator
    try:
        raw_response = generator(
            _build_intent_prompt(clean_message),
            business_id=business_id,
            user_id=user_id,
        )
        normalized_intent = normalize_ai_intent(raw_response)
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
            "intent": "operator_intent_ai_router",
            "normalized_intent": "unknown",
            "chat_response": "AI-роутер не смог разобрать команду. Кредиты не списаны.",
            "preflight": preflight,
            "reservation_result": reservation,
            "finalization_result": release,
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": ["operator_intent_ai_router_failed"],
        }

    finalization = finalize_reserved_action_credits(
        cursor,
        reservation_id=_clean_text(reservation.get("reservation_id")),
        business_id=business_id,
        user_id=user_id,
        actual_credits=OPERATOR_INTENT_CLASSIFY_ACTUAL_CREDITS,
        finalization_mode="charge",
        external_id=idempotency_key,
    )
    charged = int(finalization.get("charge_credits") or 0)
    return {
        "status": "completed",
        "intent": "operator_intent_ai_router",
        "normalized_intent": normalized_intent,
        "preflight": preflight,
        "reservation_result": reservation,
        "finalization_result": finalization,
        "charged_credits": charged,
        "credit_charged": finalization.get("status") == "charged",
        "blocked_reasons": [],
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_publication_only": True,
        "chat_response": "AI-роутер распознал команду как: " + normalized_intent,
    }
