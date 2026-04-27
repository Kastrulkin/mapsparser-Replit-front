from __future__ import annotations

import re


def _normalize_text(text: str) -> str:
    normalized = str(text or "").strip().lower()
    normalized = normalized.replace("ё", "е")
    normalized = re.sub(r"\s+", " ", normalized)
    return normalized


def classify_guest_intent(text: str) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return ""

    if any(token in normalized for token in ("тариф", "цена", "стоимость", "оплат", "подписк")):
        return "tariffs"
    if any(token in normalized for token in ("что уме", "возможност", "localos", "локалос")):
        return "about"
    if any(token in normalized for token in ("подключ", "привяз", "аккаунт", "кабинет")):
        return "connect"
    if any(token in normalized for token in ("сравни", "конкурент")):
        return "compare"
    if any(token in normalized for token in ("аудит", "карточк", "провер", "карты")):
        return "audit"
    return ""


def classify_client_intent(text: str) -> str:
    normalized = _normalize_text(text)
    if not normalized:
        return ""

    intent_rules = [
        ("today", ("что делать сегодня", "сегодня", "что важно", "что сейчас", "план на день")),
        ("card", ("карточк", "аудит", "карты", "рейтинг", "обновить карточку")),
        ("reviews", ("отзыв", "ответ на отзыв", "репутац")),
        ("growth", ("рост", "новост", "партнер", "партнерств", "конкурент")),
        ("automation", ("автоматиз", "расписан", "дайджест", "по расписанию")),
        ("subscription", ("подписк", "тариф", "оплат", "цена", "кредиты")),
        ("help", ("что уме", "как работает", "что ты умеешь", "помощ", "возможност")),
        ("approvals", ("подтвержд", "апрув", "approve", "pending approvals")),
        ("businesses", ("сменить бизнес", "какой бизнес", "мои бизнесы", "бизнесы")),
        ("cabin", ("кабинет", "личный кабинет", "профиль", "настройки")),
    ]
    for intent, patterns in intent_rules:
        if any(pattern in normalized for pattern in patterns):
            return intent
    return ""
