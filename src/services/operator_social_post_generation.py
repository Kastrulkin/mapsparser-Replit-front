from __future__ import annotations

import json
import re
import sys
from typing import Any, Callable

from services.llm import analyze_text_with_gigachat
from services.knowledge_retrieval import semantic_context_for_cursor
from services.operator_credit_reservation import finalize_reserved_action_credits, reserve_paid_action_credits
from services.operator_manual_review import BILLING_URL, _build_ui_action
from services.operator_news_generation import (
    NEWS_DRAFTS_URL,
    _clean_text,
    _insert_news_draft,
    _load_business_context,
    _normalize_news_text,
    _stable_id,
)
from services.operator_paid_preflight import build_paid_action_preflight


SOCIAL_POST_GENERATE_ACTION_KEY = "social_post_generate"
SOCIAL_POST_GENERATE_ESTIMATED_CREDITS = 1
SOCIAL_POST_GENERATE_ACTUAL_CREDITS = 1


def classify_social_post_generate_intent(message: Any) -> bool:
    text = _clean_text(message).lower()
    if not text:
        return False
    if "новост" in text:
        return False
    has_post_target = "соцсет" in text or "соц сет" in text or "пост" in text or "telegram" in text or "телеграм" in text
    if not has_post_target:
        return False
    return "сгенер" in text or "подготов" in text or "напиш" in text or "создай" in text


def extract_social_post_source_text(message: Any) -> str:
    text = _clean_text(message)
    if not text:
        return ""
    lowered = text.lower()
    markers = (
        "сгенерируй пост:",
        "подготовь пост:",
        "напиши пост:",
        "создай пост:",
        "пост для соцсетей:",
        "пост:",
    )
    for marker in markers:
        index = lowered.find(marker)
        if index >= 0:
            return text[index + len(marker):].strip()
    return text


def _build_social_post_prompt(*, source_text: str, business: dict[str, Any]) -> str:
    business_name = _clean_text(business.get("name") or business.get("business_name") or "локального бизнеса")
    business_description = _clean_text(business.get("description"))
    return "\n".join(
        [
            "Ты - SMM-редактор LocalOS для локального бизнеса.",
            "Подготовь пост для соцсетей на русском языке.",
            "Стиль: живой, спокойный, профессиональный. Без агрессивных продаж и без выдуманных фактов.",
            "Можно использовать 1-3 коротких абзаца и мягкий call-to-action.",
            "Не добавляй хэштеги, если их нет в исходных данных.",
            "Верни СТРОГО JSON: {\"post\": \"текст поста\"}.",
            "",
            f"Бизнес: {business_name}",
            f"Описание бизнеса: {business_description or 'нет данных'}",
            "",
            f"Исходная информация:\n{source_text[:1500]}",
        ]
    )


def _normalize_social_post_text(value: Any) -> str:
    raw = _clean_text(value)
    if not raw:
        return ""
    try:
        parsed = json.loads(raw)
    except Exception:
        parsed = None
    if not isinstance(parsed, dict):
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start >= 0 and end > start:
            try:
                parsed = json.loads(raw[start:end])
            except Exception:
                parsed = None
    if isinstance(parsed, dict) and "post" in parsed:
        return _clean_text(parsed.get("post"))
    return _normalize_news_text(raw).strip()


def validate_operational_claims(post_text, source_text):
    patterns=(r'свободн.{0,50}(?:кресл|мест|окн)',r'(?:мастер|сотрудник).{0,50}(?:боле|отсутств)')
    for pattern in patterns:
        if re.search(pattern,post_text,re.I) and not re.search(pattern,source_text,re.I):
            raise ValueError('В пост добавлены рабочие условия, которых нет в текущем поручении.')


def validate_operating_window(post_text,hours):
    if hours and re.search(r'свободн.{0,50}(?:кресл|мест|окн)',post_text,re.I):
        times=re.findall(r'\b(?:[01]\d|2[0-3]):[0-5]\d\b',post_text)
        if hours.get('closed') or any(value<hours['time'] or value>hours['end'] for value in times):
            raise ValueError('Предложено окно вне графика точки.')


def _default_social_post_generator(prompt: str, *, business_id: str, user_id: str) -> str:
    return analyze_text_with_gigachat(
        prompt,
        task_type="social_post_generation",
        business_id=business_id,
        user_id=user_id,
    )


def generate_social_post_draft_from_operator(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    message: Any,
    channel: str = "web",
    post_generator: Callable[..., str] | None = None,
    business_reference: str = "",
    original_message: str = "",
) -> dict[str, Any]:
    if business_reference:
        from services.business_chat_changes import resolve_target
        from services.business_permissions import load_actor
        if business_reference.casefold() not in str(original_message or message).casefold():
            return {"status":"clarification_required","chat_response":"Укажите бизнес для этого черновика явно.","external_writes_performed":False}
        try:
            business_id=resolve_target(cursor,load_actor(cursor,user_id),business_reference,business_id)
        except (ValueError,PermissionError):
            return {"status":"clarification_required","chat_response":str(sys.exception()),"external_writes_performed":False}
    source_text = extract_social_post_source_text(message)
    if len(source_text) < 8:
        return {
            "status": "blocked",
            "intent": SOCIAL_POST_GENERATE_ACTION_KEY,
            "chat_response": "Пришлите тему или исходную информацию, чтобы я подготовил пост.",
            "social_post_text": "",
            "blocked_reasons": ["social_post_source_text_required"],
        }

    preflight = build_paid_action_preflight(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=SOCIAL_POST_GENERATE_ACTION_KEY,
        estimated_credits=SOCIAL_POST_GENERATE_ESTIMATED_CREDITS,
    )
    if preflight.get("status") != "ready":
        blocked = list(preflight.get("blocked_reasons") or [])
        if "insufficient_balance" in blocked:
            return {
                "status": "blocked",
                "intent": SOCIAL_POST_GENERATE_ACTION_KEY,
                "chat_response": "Недостаточно кредитов для генерации поста. Пополните счёт или выберите тариф: /dashboard/billing",
                "billing_url": BILLING_URL,
                "preflight": preflight,
                "social_post_text": "",
                "charged_credits": 0,
                "credit_charged": False,
                "blocked_reasons": blocked,
                "ui_actions": [_build_ui_action("open_billing", "Пополнить счёт", href=BILLING_URL)],
            }
        return {
            "status": "blocked",
            "intent": SOCIAL_POST_GENERATE_ACTION_KEY,
            "chat_response": "Не удалось запустить генерацию поста. Причины: " + ", ".join(blocked),
            "preflight": preflight,
            "social_post_text": "",
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": blocked,
        }

    idempotency_key = _stable_id("operator_social_post_generate", business_id, user_id, source_text)
    reservation = reserve_paid_action_credits(
        cursor,
        business_id=business_id,
        user_id=user_id,
        action_key=SOCIAL_POST_GENERATE_ACTION_KEY,
        estimated_credits=SOCIAL_POST_GENERATE_ESTIMATED_CREDITS,
        idempotency_key=idempotency_key,
        metadata={"source": "operator_social_post_generate", "channel": channel},
    )
    if reservation.get("status") != "reserved":
        blocked = list(reservation.get("blocked_reasons") or [])
        return {
            "status": "blocked",
            "intent": SOCIAL_POST_GENERATE_ACTION_KEY,
            "chat_response": "Не удалось зарезервировать кредиты для генерации поста. Причины: " + ", ".join(blocked),
            "preflight": preflight,
            "reservation_result": reservation,
            "social_post_text": "",
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": blocked,
        }

    business = _load_business_context(cursor, business_id)
    knowledge_context, _ = semantic_context_for_cursor(
        cursor,
        business_id=business_id,
        query=source_text,
        purpose="client_content",
        consumer="social_post_generation",
        pipeline_id=idempotency_key,
    )
    post_prompt = _build_social_post_prompt(source_text=source_text, business=business)
    post_prompt += '\nРабочие окна, доступность кресел и отсутствие мастеров можно упоминать только из текущей исходной информации. Исторические заметки не подтверждают доступность сегодня.'
    operational_hours=None
    if re.search(r'свободн.{0,50}(?:кресл|мест|окн)',source_text,re.I):
        from services.operator_owner_actions import source_dates,effective_hours
        from services.finance_daily import settings
        zone=settings(cursor,business_id).get('timezone')
        days=source_dates(source_text,zone) if zone else set()
        if len(days)==1:
            operational_hours=effective_hours(cursor,business_id,next(iter(days)))
        if operational_hours:
            post_prompt+='\nПроверенный временный график точки на указанную дату: '+json.dumps(operational_hours,ensure_ascii=False)+'. Свободные кресла НЕ разрешают запись вне графика. В посте сократи окно до пересечения с графиком. Если точка закрыта — не предлагай свободные места.'
        post_prompt+='\nНе добавляй неподтверждённые удобства, детские занятия или описание аудитории. Напиши короткое фактическое объявление о времени.'
    from services.operator_editorial import editorial_prompt
    post_prompt += '\n\n' + editorial_prompt(cursor,business_id)
    if knowledge_context:
        post_prompt += (
            "\n\nПодтверждённый контекст LocalOS. Используй только подходящие факты, "
            "избегай смысловых дублей:\n" + knowledge_context
        )
    generator = post_generator or _default_social_post_generator
    try:
        generated = generator(
            post_prompt,
            business_id=business_id,
            user_id=user_id,
        )
        post_text = _normalize_social_post_text(generated)
        validate_operational_claims(post_text,source_text)
        validate_operating_window(post_text,operational_hours)
        from services.content_rules import enforce
        post_text = enforce(cursor,business_id,user_id,post_text,generator,source_text)
        validate_operational_claims(post_text,source_text)
        validate_operating_window(post_text,operational_hours)
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
            "intent": SOCIAL_POST_GENERATE_ACTION_KEY,
            "chat_response": "Пост не удалось сгенерировать. Кредиты не списаны.",
            "preflight": preflight,
            "reservation_result": reservation,
            "finalization_result": release,
            "social_post_text": "",
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": ["social_post_generation_failed"],
        }

    if not post_text:
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
            "intent": SOCIAL_POST_GENERATE_ACTION_KEY,
            "chat_response": "Модель вернула пустой пост. Кредиты не списаны.",
            "preflight": preflight,
            "reservation_result": reservation,
            "finalization_result": release,
            "social_post_text": "",
            "charged_credits": 0,
            "credit_charged": False,
            "blocked_reasons": ["empty_generated_social_post"],
        }

    social_post_draft = _insert_news_draft(
        cursor,
        business_id=business_id,
        user_id=user_id,
        source_text=source_text,
        generated_text=post_text,
        prompt_key="operator_social_post_generate",
    )
    draft_href='/dashboard/card?tab=news&business_id='+business_id+'&news_id='+str(social_post_draft['id'])
    finalization = finalize_reserved_action_credits(
        cursor,
        reservation_id=_clean_text(reservation.get("reservation_id")),
        business_id=business_id,
        user_id=user_id,
        actual_credits=SOCIAL_POST_GENERATE_ACTUAL_CREDITS,
        finalization_mode="charge",
        external_id=idempotency_key,
    )
    charged = int(finalization.get("charge_credits") or 0)
    response_lines = [
        "Подготовил черновик поста.",
        "",
        post_text,
        "",
        f"Списано кредитов: {charged}.",
        "Публикация остаётся ручной: скопируйте текст и разместите его в нужной соцсети.",
    ]
    return {
        "status": "completed",
        "intent": SOCIAL_POST_GENERATE_ACTION_KEY,
        "social_post_draft": social_post_draft,
        "social_post_text": post_text,
        "result_ref": {"href":draft_href,"label":"Открыть черновик поста","entity_id":social_post_draft['id']},
        "preflight": preflight,
        "reservation_result": reservation,
        "finalization_result": finalization,
        "charged_credits": charged,
        "credit_charged": finalization.get("status") == "charged",
        "external_calls_performed": False,
        "external_writes_performed": False,
        "manual_publication_only": True,
        "ui_actions": [
            _build_ui_action("copy_social_post", "Скопировать пост", payload={"text": post_text}),
            _build_ui_action("open_news_drafts", "Открыть черновики", href=draft_href),
        ],
        "chat_response": "\n".join(response_lines),
        "blocked_reasons": [],
    }
