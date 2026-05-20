from __future__ import annotations

from math import floor
from typing import Any


APIFY_CREDIT_MULTIPLIER = 10

CONSENT_MODES = ("ask_each_time", "auto_with_limits", "disabled")

PAID_ACTIONS: dict[str, dict[str, Any]] = {
    "map_reviews_refresh": {
        "label": "Обновить данные карт",
        "action_class": "paid_external",
        "cost_source": "provider_actual_cost",
        "provider": "apify",
        "credit_multiplier": APIFY_CREDIT_MULTIPLIER,
        "manual_approval_required": False,
        "external_write": False,
        "description": "Свежий сбор данных с карт, включая отзывы и состояние карточки.",
    },
    "review_replies_generate": {
        "label": "Сгенерировать ответы на отзывы",
        "action_class": "paid_compute",
        "cost_source": "model_tokens",
        "provider": "configured_ai_provider",
        "credit_multiplier": 1,
        "manual_approval_required": False,
        "external_write": False,
        "description": "Подготовка черновиков ответов. Публикация в карты остаётся ручной.",
    },
    "news_generate": {
        "label": "Сгенерировать новости",
        "action_class": "paid_compute",
        "cost_source": "model_tokens",
        "provider": "configured_ai_provider",
        "credit_multiplier": 1,
        "manual_approval_required": False,
        "external_write": False,
        "description": "Подготовка черновиков новостей для ручной проверки.",
    },
    "social_post_generate": {
        "label": "Сгенерировать посты",
        "action_class": "paid_compute",
        "cost_source": "model_tokens",
        "provider": "configured_ai_provider",
        "credit_multiplier": 1,
        "manual_approval_required": False,
        "external_write": False,
        "description": "Подготовка черновиков публикаций для соцсетей без автоматической отправки.",
    },
    "services_optimize": {
        "label": "Оптимизировать услуги",
        "action_class": "paid_compute",
        "cost_source": "model_tokens",
        "provider": "configured_ai_provider",
        "credit_multiplier": 1,
        "manual_approval_required": False,
        "external_write": False,
        "description": "Подготовка предложений по услугам, описаниям и структуре карточки.",
    },
}


def _positive_int(value: Any) -> int | None:
    try:
        parsed = int(value)
    except Exception:
        return None
    if parsed <= 0:
        return None
    return parsed


def build_paid_action_offer(
    action_key: str,
    *,
    business_id: str,
    balance_credits: Any = None,
    estimated_credits: Any = None,
    reason: str = "",
) -> dict[str, Any]:
    config = dict(PAID_ACTIONS.get(action_key) or {})
    if not config:
        raise ValueError(f"unknown paid action: {action_key}")

    clean_balance = _positive_int(balance_credits)
    clean_estimate = _positive_int(estimated_credits)
    affordable_runs = None
    if clean_balance is not None and clean_estimate is not None:
        affordable_runs = floor(clean_balance / clean_estimate)

    estimate_available = clean_estimate is not None
    if action_key == "map_reviews_refresh":
        primary_copy = "Могу показать последние известные данные бесплатно. Или обновить карты сейчас — платно."
    elif config.get("action_class") == "paid_compute":
        primary_copy = "Могу подготовить черновик платно, если вы разрешите использовать кредиты."
    else:
        primary_copy = "Это платное действие. Перед выполнением нужно разрешение на списание кредитов."

    if estimate_available and clean_balance is not None and affordable_runs is not None:
        disclosure = f"Оценка: до {clean_estimate} кредитов. Вашего баланса хватит примерно на {affordable_runs} таких операций."
    elif clean_balance is not None:
        disclosure = f"Сейчас на балансе {clean_balance} кредитов. Точную стоимость покажем после оценки перед запуском."
    else:
        disclosure = "Точная стоимость появится после оценки. До согласия платные действия не выполняются."

    return {
        "action_key": action_key,
        "business_id": business_id,
        "label": config["label"],
        "description": config["description"],
        "action_class": config["action_class"],
        "status": "proposal_only",
        "consent_required": True,
        "consent_modes": list(CONSENT_MODES),
        "default_consent_mode": "ask_each_time",
        "cost_source": config["cost_source"],
        "provider": config["provider"],
        "credit_multiplier": int(config["credit_multiplier"]),
        "estimate_available": estimate_available,
        "estimated_credits": clean_estimate,
        "balance_credits": clean_balance,
        "affordable_runs_estimate": affordable_runs,
        "manual_approval_required": bool(config["manual_approval_required"]),
        "external_write": bool(config["external_write"]),
        "paid_actions_performed": False,
        "reason": reason,
        "copy": {
            "primary": primary_copy,
            "disclosure": disclosure,
            "auto_consent_question": "Разрешить дальше выполнять такие обновления без спроса в пределах лимитов?",
            "manual_publication_note": "Публикация ответов в карты сейчас ручная: LocalOS готовит текст, пользователь копирует и вставляет его сам.",
        },
    }


def build_map_reviews_refresh_offer(
    *,
    business_id: str,
    balance_credits: Any = None,
    estimated_credits: Any = None,
    reason: str = "",
) -> dict[str, Any]:
    return build_paid_action_offer(
        "map_reviews_refresh",
        business_id=business_id,
        balance_credits=balance_credits,
        estimated_credits=estimated_credits,
        reason=reason,
    )
