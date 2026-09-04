"""Canonical lead journey state shared by web and Telegram Mini App."""
from __future__ import annotations

import hashlib
import json
import os
import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from psycopg2.extras import Json


ACTIVE_ACTION_STATUSES = {"ready", "in_progress", "waiting", "blocked"}
FINAL_ACTION_STATUSES = {"completed", "superseded", "cancelled"}
FLOW_TYPES = {"influencer", "partnership", "maps", "content", "automation", "average_ticket"}
FLOW_FLAGS = {
    "influencer": "INFLUENCER_JOURNEY_ENABLED",
    "partnership": "PARTNERSHIP_JOURNEY_ENABLED",
    "maps": "MAPS_JOURNEY_ENABLED",
    "content": "CONTENT_JOURNEY_ENABLED",
    "automation": "AUTOMATION_JOURNEY_ENABLED",
    "average_ticket": "AUTOMATION_JOURNEY_ENABLED",
}
PUBLIC_EVENT_NAMES = {
    "lead_link_opened", "opportunity_preview_clicked", "opportunity_list_opened",
    "action_prepare_clicked", "partial_result_viewed", "registration_started",
}

PUBLIC_OPPORTUNITY_METRIC_KEYS = {
    "rating", "reviews_count", "scheduled_for",
    "followers", "follower_count", "subscribers", "subscriber_count",
    "members", "audience_count", "views", "avg_views", "engagement_rate",
    "offer_service", "offer_value", "offer_threshold", "offer_reward",
    "offer_constraints", "offer_valid_until", "offer_version", "offer_status",
    "example_links",
}

ACTION_COMMANDS = {
    "prepare_offer": ("prepare",),
    "register": ("claim",),
    "browse_creators": ("complete",),
    "send_message": ("copy", "mark_sent"),
    "check_reply": ("record_reply", "prepare_followup"),
    "send_followup": ("copy", "mark_sent"),
    "define_terms": ("save_terms",),
    "mark_published": ("mark_published",),
    "mark_launched": ("mark_launched",),
    "add_result": ("add_result",),
    "select_next_influencer": ("start_next_cycle",),
    "select_next_partner": ("start_next_cycle",),
    "complete_map_task": ("complete",),
    "refresh_data": ("complete",),
    "compare_snapshot": ("complete", "retry_refresh"),
    "start_next_map_plan": ("start_next_cycle",),
    "prepare_content": ("prepare",),
    "review_content": ("save_draft",),
    "save_to_calendar": ("schedule",),
    "waiting_for_publication": ("mark_published",),
    "add_content_result": ("add_result",),
    "start_next_content_cycle": ("start_next_cycle",),
    "configure_automation": ("save_configuration",),
    "review_automation_preflight": ("approve",),
    "run_automation": ("link_run",),
    "review_automation_result": ("add_result",),
    "start_next_automation_cycle": ("start_next_cycle",),
    "open_average_ticket": ("prepare", "complete"),
    "upgrade": ("open_upgrade",),
}


class JourneyError(Exception):
    def __init__(self, message: str, status_code: int = 400, code: str = "journey_error"):
        super().__init__(message)
        self.status_code = status_code
        self.code = code


def journey_enabled(flag: str = "LEAD_JOURNEY_ENABLED") -> bool:
    return str(os.getenv(flag) or "false").strip().lower() in {"1", "true", "yes", "on"}


def journey_flow_enabled(flow_type: str) -> bool:
    flag = FLOW_FLAGS.get(flow_type)
    return bool(flag and journey_enabled() and journey_enabled(flag))


def _row(cursor: Any, value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "keys"):
        return dict(value)
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    return {columns[index]: value[index] for index in range(min(len(columns), len(value)))}


def _json_object(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, dict) else {}
        except (TypeError, ValueError):
            return {}
    return {}


def _json_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            return parsed if isinstance(parsed, list) else []
        except (TypeError, ValueError):
            return []
    return []


def token_hash(token: str) -> str:
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _iso(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        normalized = value if value.tzinfo else value.replace(tzinfo=timezone.utc)
        return normalized.astimezone(timezone.utc).isoformat()
    return str(value)


def _clean_public_opportunity(item: dict[str, Any]) -> dict[str, Any]:
    flow = str(item.get("flow_type") or item.get("flow") or "").strip()
    if flow not in FLOW_TYPES:
        return {}
    metrics = item.get("metrics") if isinstance(item.get("metrics"), dict) else {}
    safe_metrics = {
        str(key)[:80]: value
        for key, value in metrics.items()
        if str(key) in PUBLIC_OPPORTUNITY_METRIC_KEYS
        and isinstance(value, (str, int, float, bool))
        and len(str(value)) <= 160
    }
    tasks = item.get("tasks") if isinstance(item.get("tasks"), list) else []
    safe_tasks = [
        {"title": str(task.get("title") or "")[:200], "reason": str(task.get("reason") or "")[:500]}
        for task in tasks[:12]
        if isinstance(task, dict) and str(task.get("title") or "").strip()
    ]
    public_url = str(item.get("public_url") or "").strip()
    if not public_url.startswith(("https://", "http://")):
        public_url = ""
    return {
        "flow_type": flow,
        "entity_type": str(item.get("entity_type") or flow)[:100],
        "entity_id": str(item.get("entity_id") or "")[:160],
        "title": str(item.get("title") or "")[:200],
        "summary": str(item.get("summary") or item.get("description") or "")[:800],
        "reason": str(item.get("reason") or "")[:800],
        "mechanic": str(item.get("mechanic") or "")[:500],
        "message_excerpt": str(item.get("message_excerpt") or "")[:180],
        "public_url": public_url[:500],
        "count": max(0, int(item.get("count") or 0)),
        "metrics": safe_metrics,
        "tasks": safe_tasks,
    }


def _default_opportunities(lead: dict[str, Any]) -> list[dict[str, Any]]:
    business_name = str(lead.get("company_name") or lead.get("name") or "вашего бизнеса")
    return [
        {"flow_type": "influencer", "entity_type": "creator_search", "entity_id": "", "title": "Локальный автор", "summary": f"Подберём автора рядом с {business_name} по географии и тематике.", "reason": "Аудитория автора может совпадать с вашими клиентами.", "mechanic": "Начать с бартера или персонального промокода.", "message_excerpt": "Здравствуйте! Увидели ваш материал о…", "count": 0, "metrics": {}},
        {"flow_type": "partnership", "entity_type": "partner_search", "entity_id": "", "title": "Соседский партнёр", "summary": "Найдём бизнес рядом с дополняющей аудиторией.", "reason": "Клиенты могут пользоваться обеими услугами в одном сценарии.", "mechanic": "Взаимная рекомендация клиентов.", "message_excerpt": "Здравствуйте! Мы работаем рядом и хотим предложить…", "count": 0, "metrics": {}},
        {"flow_type": "maps", "entity_type": "card_audit", "entity_id": "", "title": "Возможность на картах", "summary": "Покажем приоритетное отличие от ближайших конкурентов.", "reason": "Конкретная задача помогает улучшить полноту карточки.", "mechanic": "Выполнить первый пункт недельного плана.", "message_excerpt": "", "count": 0, "metrics": {}},
        {"flow_type": "content", "entity_type": "content_topic", "entity_id": "", "title": "Тема для следующей публикации", "summary": f"Покажем тему и короткий черновик для {business_name} на основе реальных данных бизнеса.", "reason": "Регулярный полезный контент помогает напоминать о бизнесе без постоянного поиска идей.", "mechanic": "Подготовить один материал, проверить его и сохранить в календарь.", "message_excerpt": "Полезный материал для клиентов вашего бизнеса…", "count": 0, "metrics": {}},
        {"flow_type": "automation", "entity_type": "automation_use_case", "entity_id": "routine_control", "title": "Автоматизировать повторяющуюся работу", "summary": "Выберите регулярную задачу, проверьте план ИИ-сотрудника и контролируйте каждый запуск.", "reason": "Повторяющиеся проверки можно выполнять по расписанию, сохраняя ручное подтверждение важных действий.", "mechanic": "Сначала настроить задачу и проверить preflight. Запуск и внешние действия подтверждаются отдельно.", "message_excerpt": "Например: каждое утро собрать отзывы без ответа и подготовить черновики.", "count": 0, "metrics": {}},
        {"flow_type": "average_ticket", "entity_type": "growth_opportunity", "entity_id": "average_ticket", "title": "Увеличить средний чек", "summary": "Покажем, какие услуги можно объединить и где предложить уместную допродажу.", "reason": "Понятные пакеты и следующий подходящий шаг помогают расти без давления на клиента.", "mechanic": "Сначала проверить текущие услуги и цены, затем выбрать один безопасный сценарий роста.", "message_excerpt": "Например: базовая услуга + подходящее дополнение с прозрачной выгодой.", "count": 0, "metrics": {}},
    ]


def build_lead_preview(lead: dict[str, Any]) -> dict[str, Any]:
    """Build a safe six-path preview from fields already stored on the lead."""
    business_name = str(lead.get("name") or "").strip()
    city = str(lead.get("city") or "").strip()
    address = str(lead.get("address") or "").strip()
    category = str(lead.get("category") or "").strip()
    rating = lead.get("rating")
    reviews_count = lead.get("reviews_count")
    opportunities = _default_opportunities({"name": business_name})
    context = ", ".join(value for value in (category, city) if value)
    if context:
        opportunities[0]["reason"] = f"Поиск будет учитывать: {context}."
        opportunities[1]["reason"] = f"Партнёры будут подобраны рядом с бизнесом в категории «{category or 'локальный бизнес'}»."
    map_metrics: dict[str, Any] = {}
    if isinstance(rating, (int, float)):
        map_metrics["rating"] = rating
    if isinstance(reviews_count, int):
        map_metrics["reviews_count"] = reviews_count
    opportunities[2]["metrics"] = map_metrics
    if context:
        opportunities[3]["reason"] = f"Первая тема будет учитывать: {context}."
    return {
        "business_name": business_name,
        "business_city": city,
        "business_address": address,
        "opportunities": opportunities,
    }


def build_lead_preview_from_sources(cursor: Any, lead: dict[str, Any]) -> dict[str, Any]:
    """Enrich the safe fallback with one real public example from each existing domain."""
    preview = build_lead_preview(lead)
    opportunities = preview["opportunities"]
    city = str(lead.get("city") or "").strip()
    lead_id = str(lead.get("id") or "").strip()
    cursor.execute(
        """
        SELECT profile.id::text, profile.display_name, profile.description, profile.primary_city,
               channel.canonical_url, channel.public_metrics_json
        FROM creator_profiles profile
        LEFT JOIN LATERAL (
            SELECT canonical_url, public_metrics_json
            FROM creator_channels item WHERE item.creator_profile_id = profile.id
            ORDER BY item.last_observed_at DESC NULLS LAST, item.created_at DESC LIMIT 1
        ) channel ON TRUE
        WHERE profile.verification_status <> 'rejected' AND profile.brand_safety_status <> 'blocked'
        ORDER BY CASE WHEN LOWER(COALESCE(profile.primary_city, '')) = LOWER(%s) THEN 0 ELSE 1 END,
                 profile.updated_at DESC
        LIMIT 1
        """,
        (city,),
    )
    creator = _row(cursor, cursor.fetchone())
    if creator:
        opportunities[0].update({
            "entity_type": "creator_profile", "entity_id": str(creator.get("id") or ""),
            "title": str(creator.get("display_name") or "Локальный автор"),
            "summary": str(creator.get("description") or "Публичный профиль локального автора."),
            "reason": f"Автор найден в городе {creator.get('primary_city') or city or 'клиента'}; соответствие нужно подтвердить перед контактом.",
            "public_url": str(creator.get("canonical_url") or ""),
            "metrics": _json_object(creator.get("public_metrics_json")),
        })
    cursor.execute(
        """
        SELECT id, name, category, city, rating, source_url
        FROM prospectingleads
        WHERE id <> %s AND COALESCE(name, '') <> ''
        ORDER BY CASE WHEN LOWER(COALESCE(city, '')) = LOWER(%s) THEN 0 ELSE 1 END,
                 rating DESC NULLS LAST, updated_at DESC
        LIMIT 1
        """,
        (lead_id, city),
    )
    partner = _row(cursor, cursor.fetchone())
    if partner:
        opportunities[1].update({
            "entity_type": "prospecting_lead", "entity_id": str(partner.get("id") or ""),
            "title": str(partner.get("name") or "Соседский партнёр"),
            "summary": f"{partner.get('category') or 'Локальный бизнес'} · {partner.get('city') or city}",
            "reason": "Это публичный пример соседнего бизнеса; общую аудиторию нужно подтвердить перед предложением.",
            "public_url": str(partner.get("source_url") or ""),
            "metrics": {"rating": partner.get("rating")} if isinstance(partner.get("rating"), (int, float)) else {},
        })
    cursor.execute(
        """
        SELECT item.id, item.theme, item.goal, item.draft_text, item.scheduled_for
        FROM contentplanitems item
        WHERE item.business_id IN (
            SELECT client_business_id FROM lead_workstreams
            WHERE lead_id = %s AND client_business_id IS NOT NULL
        )
          AND item.status IN ('planned', 'draft_generated', 'edited', 'approved')
        ORDER BY item.scheduled_for, item.updated_at DESC LIMIT 1
        """,
        (lead_id,),
    )
    content = _row(cursor, cursor.fetchone())
    if content:
        opportunities[3].update({
            "entity_type": "contentplanitem", "entity_id": str(content.get("id") or ""),
            "title": str(content.get("theme") or "Тема для публикации"),
            "summary": str(content.get("goal") or "Материал из существующего контент-плана."),
            "message_excerpt": str(content.get("draft_text") or "")[:180],
            "metrics": {"scheduled_for": str(content.get("scheduled_for") or "")},
        })
    preview["opportunities"] = [_clean_public_opportunity(item) for item in opportunities]
    return preview


def create_lead_journey(
    cursor: Any,
    *,
    prospect_lead_id: str | None,
    preview: dict[str, Any],
    source: str,
    selected_flow: str,
    expires_in_days: int = 30,
    source_offer_type: str = "lead_offer",
    source_offer_id: str | None = None,
    selected_entity_type: str | None = None,
    selected_entity_id: str | None = None,
) -> tuple[dict[str, Any], str]:
    normalized_flow = str(selected_flow or "").strip()
    if normalized_flow not in FLOW_TYPES:
        raise JourneyError("Выберите поддерживаемое направление", 400, "flow_not_supported")
    normalized_preview = dict(preview or {})
    raw_opportunities = normalized_preview.get("opportunities")
    if not isinstance(raw_opportunities, list) or not raw_opportunities:
        raw_opportunities = _default_opportunities(normalized_preview)
        normalized_preview["opportunities"] = raw_opportunities
    opportunities = [
        clean for clean in (_clean_public_opportunity(item) for item in raw_opportunities) if clean
    ]
    requested_entity_id = str(selected_entity_id or "").strip()
    selected = next((
        item for item in opportunities
        if item["flow_type"] == normalized_flow
        and (not requested_entity_id or item["entity_id"] == requested_entity_id)
    ), None)
    if not selected:
        raise JourneyError("Для выбранного направления нет безопасного примера", 400, "selected_opportunity_missing")
    requested_entity_type = str(selected_entity_type or "").strip()
    if requested_entity_type and requested_entity_type != str(selected.get("entity_type") or ""):
        raise JourneyError("Тип выбранного примера не совпадает с безопасным preview", 400, "selected_entity_mismatch")
    normalized_preview["opportunities"] = opportunities
    raw_token = secrets.token_urlsafe(32)
    journey_id = str(uuid.uuid4())
    expires_at = datetime.now(timezone.utc) + timedelta(days=max(1, min(expires_in_days, 90)))
    cursor.execute(
        """
        INSERT INTO lead_journeys (
            id, prospect_lead_id, source_offer_type, source_offer_id, public_token_hash,
            source, preview_json, selected_flow, selected_entity_type, selected_entity_id, expires_at
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING *
        """,
        (journey_id, prospect_lead_id or None, source_offer_type, source_offer_id or None,
         token_hash(raw_token), str(source or "outreach")[:100], Json(normalized_preview), normalized_flow,
         str(selected.get("entity_type") or normalized_flow)[:100],
         requested_entity_id or str(selected.get("entity_id") or "") or None, expires_at),
    )
    return serialize_journey(cursor, _row(cursor, cursor.fetchone()), public=True), raw_token


def load_public_journey(cursor: Any, token: str, *, lock: bool = False) -> dict[str, Any]:
    if not token:
        raise JourneyError("Ссылка не найдена", 404, "journey_not_found")
    cursor.execute(
        f"""
        SELECT journey.*, lead.name AS lead_name
        FROM lead_journeys journey
        LEFT JOIN prospectingleads lead ON lead.id = journey.prospect_lead_id
        WHERE journey.public_token_hash = %s
        LIMIT 1
        {"FOR UPDATE OF journey" if lock else ""}
        """,
        (token_hash(token),),
    )
    journey = _row(cursor, cursor.fetchone())
    if not journey:
        raise JourneyError("Ссылка не найдена", 404, "journey_not_found")
    now = datetime.now(timezone.utc)
    expires_at = journey.get("expires_at")
    normalized_expiry = expires_at if not isinstance(expires_at, datetime) or expires_at.tzinfo else expires_at.replace(tzinfo=timezone.utc)
    if journey.get("revoked_at") or journey.get("status") == "revoked":
        raise JourneyError("Ссылка отозвана", 410, "journey_revoked")
    if isinstance(normalized_expiry, datetime) and normalized_expiry <= now:
        raise JourneyError("Срок действия ссылки истёк", 410, "journey_expired")
    return journey


def serialize_journey(cursor: Any, journey: dict[str, Any], *, public: bool = False) -> dict[str, Any]:
    preview = _json_object(journey.get("preview_json"))
    opportunities = [
        clean for clean in (_clean_public_opportunity(item) for item in _json_list(preview.get("opportunities"))) if clean
    ]
    if not opportunities:
        opportunities = _default_opportunities(journey)
    payload = {
        "id": str(journey.get("id") or ""),
        "status": str(journey.get("status") or "preview"),
        "source": str(journey.get("source") or "outreach"),
        "business": {
            "name": str(preview.get("business_name") or journey.get("company_name") or journey.get("lead_name") or ""),
            "city": str(preview.get("business_city") or ""),
            "address": str(preview.get("business_address") or ""),
        },
        "opportunities": opportunities,
        "selected_flow": journey.get("selected_flow"),
        "expires_at": _iso(journey.get("expires_at")),
    }
    if not public:
        payload.update({
            "prospect_lead_id": journey.get("prospect_lead_id"),
            "claimed_user_id": journey.get("claimed_user_id"),
            "claimed_business_id": journey.get("claimed_business_id"),
        })
    return payload


def select_public_opportunity(cursor: Any, *, token: str, flow_type: str, entity_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    if flow_type not in FLOW_TYPES:
        raise JourneyError("Направление не поддерживается", 400, "flow_not_supported")
    journey = load_public_journey(cursor, token, lock=True)
    locked_flow = str(journey.get("selected_flow") or "").strip()
    if locked_flow and locked_flow != flow_type:
        raise JourneyError("Ссылка создана для другого направления", 409, "journey_flow_locked")
    public = serialize_journey(cursor, journey, public=True)
    opportunity = next(
        (item for item in public["opportunities"] if item["flow_type"] == flow_type and (not entity_id or item["entity_id"] == entity_id)),
        None,
    )
    if not opportunity:
        raise JourneyError("Возможность не найдена", 404, "opportunity_not_found")
    cursor.execute(
        """
        UPDATE lead_journeys
        SET selected_flow = %s, selected_entity_type = %s, selected_entity_id = %s,
            status = CASE WHEN status = 'preview' THEN 'registration_pending' ELSE status END,
            updated_at = NOW()
        WHERE id = %s
        """,
        (flow_type, opportunity["entity_type"], opportunity["entity_id"] or None, journey["id"]),
    )
    return journey, {
        **opportunity,
        "partial_result": {
            "mechanic": opportunity.get("mechanic"),
            "message_excerpt": opportunity.get("message_excerpt"),
            "locked": True,
        },
    }


def _action_copy(flow_type: str, action_type: str, payload: dict[str, Any]) -> tuple[str, str, str, int]:
    name = str(payload.get("entity_name") or payload.get("title") or "возможность")
    copies = {
        "browse_creators": ("Выберите 2–5 подходящих авторов", "Посмотрите причины соответствия, добавьте авторов в shortlist и подтвердите выбор.", "Подтвердить выбор", 115),
        "send_message": (f"Написать: {name}", "Сообщение подготовлено. Проверьте его перед ручной отправкой.", "Открыть сообщение", 110),
        "check_reply": (f"Проверить ответ: {name}", "Если ответа нет, LocalOS подготовит follow-up.", "Указать результат", 125),
        "send_followup": (f"Отправить follow-up: {name}", "Короткое продолжение подготовлено без автоматической отправки.", "Открыть follow-up", 120),
        "define_terms": (f"Согласовать условия: {name}", "Зафиксируйте реальные условия договорённости.", "Заполнить условия", 130),
        "mark_published": (f"Зафиксировать размещение: {name}", "Добавьте ссылку и дату опубликованного материала.", "Размещение вышло", 130),
        "mark_launched": (f"Запустить партнёрство: {name}", "Зафиксируйте механику и дату запуска.", "Партнёрство запущено", 130),
        "add_result": (f"Добавить результат: {name}", "Укажите только известные обращения, записи или продажи.", "Добавить результат", 135),
        "select_next_influencer": ("Выбрать следующего автора", "LocalOS найдёт похожую аудиторию для нового цикла.", "Выбрать следующего", 70),
        "select_next_partner": ("Найти похожего партнёра", "Используйте результат цикла для следующего подбора.", "Найти похожих", 70),
        "complete_map_task": (str(payload.get("task_title") or "Выполнить задачу по картам"), str(payload.get("task_reason") or "Это следующий пункт недельного плана."), "Сделать", 100),
        "refresh_data": ("Проверить изменения карточки", "Все задачи недели отмечены. Обновите данные карты.", "Обновить данные", 120),
        "compare_snapshot": ("Посмотреть результат недели", "Сравните показатели до и после выполненных задач.", "Посмотреть сравнение", 110),
        "start_next_map_plan": ("Начать следующую неделю", "Следующий план готов после проверки изменений.", "Начать следующую неделю", 70),
        "prepare_content": (f"Подготовить материал: {name}", "Откройте полный черновик и проверьте его перед сохранением.", "Подготовить черновик", 105),
        "review_content": (f"Проверить материал: {name}", "Отредактируйте текст и подтвердите итоговую версию.", "Проверить черновик", 120),
        "save_to_calendar": (f"Запланировать: {name}", "Выберите дату и сохраните материал в существующий контент-календарь.", "Добавить в календарь", 115),
        "waiting_for_publication": (f"Зафиксировать публикацию: {name}", "Публикация выполняется вручную или через отдельное подтверждение.", "Указать публикацию", 110),
        "add_content_result": (f"Добавить результат: {name}", "Зафиксируйте только известный результат опубликованного материала.", "Добавить результат", 100),
        "start_next_content_cycle": ("Подготовить следующий материал", "Используйте результат публикации для выбора следующей темы.", "Выбрать следующую тему", 70),
        "configure_automation": ("Настроить первую задачу", "Выберите повторяющуюся работу и ожидаемый результат. Внешние действия пока не запускаются.", "Настроить задачу", 105),
        "review_automation_preflight": ("Проверить план запуска", "Проверьте источники данных, ограничения и действия, которые потребуют подтверждения.", "Проверить и подтвердить", 120),
        "run_automation": ("Запустить проверенную задачу", "Откройте ИИ-сотрудника, выполните preflight и запустите задачу вручную.", "Открыть ИИ-сотрудника", 125),
        "review_automation_result": ("Проверить результат ИИ-сотрудника", "Результат реального запуска готов. Проверьте его перед следующим циклом.", "Зафиксировать результат", 115),
        "start_next_automation_cycle": ("Запустить следующий цикл", "Сохраните удачную настройку или скорректируйте задачу перед повтором.", "Настроить следующий цикл", 70),
        "open_average_ticket": ("Найти первый сценарий роста чека", "Проверьте услуги, цены и уместные дополнения перед применением.", "Открыть средний чек", 105),
        "upgrade": ("Автоматизировать повторяющуюся работу", "Вы завершили полезный цикл; LocalOS может поддерживать его постоянно.", "Посмотреть автоматизацию", 40),
    }
    return copies.get(action_type, ("Продолжить работу", "LocalOS подготовил следующий конкретный шаг.", "Продолжить", 50))


def ensure_action(
    cursor: Any,
    *,
    journey_id: str | None,
    business_id: str | None,
    user_id: str | None,
    lead_id: str | None,
    flow_type: str,
    entity_type: str,
    entity_id: str | None,
    action_type: str,
    payload: dict[str, Any],
    source_action_id: str | None = None,
    status: str = "ready",
    due_at: datetime | None = None,
) -> dict[str, Any]:
    dedupe_seed = "|".join((journey_id or business_id or "none", flow_type, entity_type, entity_id or "none", action_type, str(payload.get("cycle_key") or "default")))
    dedupe_key = hashlib.sha256(dedupe_seed.encode("utf-8")).hexdigest()
    title, description, cta_label, priority = _action_copy(flow_type, action_type, payload)
    cursor.execute(
        """
        INSERT INTO journey_actions (
            id, journey_id, business_id, user_id, lead_id, flow_type, entity_type, entity_id,
            action_type, status, priority, due_at, title, description, cta_label,
            cta_target_json, payload_json, source_action_id, dedupe_key
        ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        ON CONFLICT (dedupe_key) WHERE status IN ('ready', 'in_progress', 'waiting', 'blocked')
        DO UPDATE SET due_at = COALESCE(EXCLUDED.due_at, journey_actions.due_at),
                      payload_json = journey_actions.payload_json || EXCLUDED.payload_json,
                      updated_at = NOW()
        RETURNING *
        """,
        (str(uuid.uuid4()), journey_id, business_id, user_id, lead_id, flow_type, entity_type,
         entity_id or None, action_type, status, priority, due_at, title, description, cta_label,
         Json({"screen": _screen_for_flow(flow_type), "action_id": None}), Json(payload), source_action_id, dedupe_key),
    )
    return serialize_action(_row(cursor, cursor.fetchone()))


def _screen_for_flow(flow_type: str) -> str:
    return {"influencer": "influencers", "partnership": "partnerships", "maps": "progress", "content": "content", "automation": "agents", "average_ticket": "average_ticket", "upgrade": "settings"}.get(flow_type, "today")


def reserve_journey(cursor: Any, *, token: str, user_id: str, business_id: str) -> dict[str, Any]:
    """Bind registration context without exposing an action before email verification."""
    journey = load_public_journey(cursor, token, lock=True)
    claimed_user = str(journey.get("claimed_user_id") or "")
    claimed_business = str(journey.get("claimed_business_id") or "")
    if claimed_user and (claimed_user != user_id or claimed_business != business_id):
        raise JourneyError("Ссылка уже привязана к другому аккаунту", 409, "journey_already_claimed")
    if str(journey.get("selected_flow") or "") not in FLOW_TYPES:
        raise JourneyError("Сначала выберите возможность", 409, "opportunity_not_selected")
    cursor.execute(
        """
        UPDATE lead_journeys
        SET claimed_user_id = %s, claimed_business_id = %s,
            status = 'registration_pending', updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (user_id, business_id, journey["id"]),
    )
    return _row(cursor, cursor.fetchone())


def _claim_loaded_journey(cursor: Any, *, journey: dict[str, Any], user_id: str, business_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    claimed_user = str(journey.get("claimed_user_id") or "")
    claimed_business = str(journey.get("claimed_business_id") or "")
    if claimed_user and (claimed_user != user_id or claimed_business != business_id):
        raise JourneyError("Ссылка уже привязана к другому аккаунту", 409, "journey_already_claimed")
    flow_type = str(journey.get("selected_flow") or "")
    if flow_type not in FLOW_TYPES:
        raise JourneyError("Сначала выберите возможность", 409, "opportunity_not_selected")
    cursor.execute(
        """
        UPDATE lead_journeys
        SET claimed_user_id = %s, claimed_business_id = %s, status = 'claimed',
            claimed_at = COALESCE(claimed_at, NOW()), updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (user_id, business_id, journey["id"]),
    )
    claimed = _row(cursor, cursor.fetchone())
    preview = serialize_journey(cursor, {**journey, **claimed}, public=True)
    opportunity = next((item for item in preview["opportunities"] if item["flow_type"] == flow_type), {})
    resolved_entity_type = str(journey.get("selected_entity_type") or flow_type)
    resolved_entity_id = str(journey.get("selected_entity_id") or "") or None
    payload = {
        "entity_name": opportunity.get("title") or "возможность",
        "mechanic": opportunity.get("mechanic"),
        "message_excerpt": opportunity.get("message_excerpt"),
        "cycle_key": "first",
    }
    opportunity_metrics = opportunity.get("metrics") if isinstance(opportunity.get("metrics"), dict) else {}
    if flow_type == "influencer":
        payload["domain_summary"] = opportunity.get("summary")
        payload["offer"] = {
            "service": opportunity_metrics.get("offer_service"),
            "value": opportunity_metrics.get("offer_value"),
            "threshold": opportunity_metrics.get("offer_threshold") or 3,
            "reward": opportunity_metrics.get("offer_reward"),
            "constraints": opportunity_metrics.get("offer_constraints"),
            "valid_until": opportunity_metrics.get("offer_valid_until"),
            "version": opportunity_metrics.get("offer_version") or 1,
            "status": opportunity_metrics.get("offer_status") or "approved",
            "mechanic": opportunity.get("mechanic"),
        }
        cursor.execute(
            """
            SELECT job.id
            FROM creator_search_jobs job
            WHERE job.business_id = %s
              AND EXISTS (SELECT 1 FROM creator_search_results result WHERE result.search_job_id = job.id)
            ORDER BY job.updated_at DESC LIMIT 1
            """,
            (business_id,),
        )
        creator_search = _row(cursor, cursor.fetchone())
        if not creator_search:
            from services.creator_promotion_service import run_creator_search
            creator_search = run_creator_search(
                cursor,
                business_id=business_id,
                user_id=user_id,
                brief={
                    "city": preview.get("business", {}).get("city") or "",
                    "service": opportunity_metrics.get("offer_service") or "",
                    "barter": True,
                    "result_limit": 30,
                },
            )
        resolved_entity_type = "creator_search"
        resolved_entity_id = str(creator_search.get("id") or "") or None
        cursor.execute(
            "UPDATE lead_journeys SET selected_entity_type = %s, selected_entity_id = %s, updated_at = NOW() WHERE id = %s",
            (resolved_entity_type, resolved_entity_id, journey["id"]),
        )
    if flow_type == "maps":
        tasks = opportunity.get("tasks") if isinstance(opportunity.get("tasks"), list) else []
        if not tasks:
            tasks = [{"title": opportunity.get("title") or "Выполнить первый пункт плана", "reason": opportunity.get("reason")}]
        payload.update({
            "task_title": tasks[0].get("title"), "task_reason": tasks[0].get("reason"),
            "task_index": 0, "tasks_total": len(tasks), "tasks": tasks,
            "baseline": opportunity.get("metrics") or {},
        })
        action_type = "complete_map_task"
    elif flow_type == "content":
        if resolved_entity_id:
            cursor.execute(
                "SELECT id FROM contentplanitems WHERE id = %s AND business_id = %s",
                (resolved_entity_id, business_id),
            )
            if not cursor.fetchone():
                resolved_entity_id = None
        if not resolved_entity_id:
            cursor.execute(
                """
                SELECT id FROM contentplanitems
                WHERE business_id = %s AND status IN ('planned', 'draft_generated', 'edited')
                ORDER BY scheduled_for, created_at LIMIT 1
                """,
                (business_id,),
            )
            existing_item = _row(cursor, cursor.fetchone())
            resolved_entity_id = str(existing_item.get("id") or "") or None
        if not resolved_entity_id:
            plan_id = str(uuid.uuid4())
            resolved_entity_id = str(uuid.uuid4())
            today = datetime.now(timezone.utc).date()
            cursor.execute(
                """
                INSERT INTO contentplans (
                    id, business_id, scope_type, title, period_days, period_start, period_end,
                    plan_status, generation_mode, input_snapshot_json, created_by
                ) VALUES (%s, %s, 'single_business', %s, 30, %s, %s, 'draft', 'journey', %s, %s)
                """,
                (plan_id, business_id, f"Первый материал: {opportunity.get('title') or 'Тема публикации'}", today, today + timedelta(days=29), Json({"source": "lead_journey", "journey_id": journey.get("id")}), user_id),
            )
            cursor.execute(
                """
                INSERT INTO contentplanitems (
                    id, plan_id, business_id, scheduled_for, content_type, theme, goal,
                    source_kind, source_ref, draft_text, status, metadata_json
                ) VALUES (%s, %s, %s, %s, 'news', %s, %s, 'lead_journey', %s, %s, 'planned', %s)
                """,
                (resolved_entity_id, plan_id, business_id, today + timedelta(days=7), opportunity.get("title") or "Тема публикации", opportunity.get("summary") or "", journey.get("id"), opportunity.get("message_excerpt") or "", Json({"journey_id": journey.get("id")})),
            )
        resolved_entity_type = "contentplanitem"
        cursor.execute(
            "UPDATE lead_journeys SET selected_entity_type = %s, selected_entity_id = %s, updated_at = NOW() WHERE id = %s",
            (resolved_entity_type, resolved_entity_id, journey["id"]),
        )
        payload.update({
            "content_topic": opportunity.get("title"),
            "content_excerpt": opportunity.get("message_excerpt"),
            "domain_summary": opportunity.get("summary"),
        })
        action_type = "prepare_content"
    elif flow_type == "influencer":
        action_type = "browse_creators"
    elif flow_type == "automation":
        resolved_entity_type = "automation_use_case"
        resolved_entity_id = resolved_entity_id or "routine_control"
        payload.update({
            "use_case": resolved_entity_id,
            "domain_summary": opportunity.get("summary"),
            "approval_required": True,
        })
        action_type = "configure_automation"
    elif flow_type == "average_ticket":
        resolved_entity_type = "growth_opportunity"
        resolved_entity_id = "average_ticket"
        payload.update({"domain_summary": opportunity.get("summary"), "approval_required": True})
        action_type = "open_average_ticket"
    else:
        action_type = "send_message"
    action = ensure_action(
        cursor, journey_id=str(journey["id"]), business_id=business_id, user_id=user_id,
        lead_id=str(journey.get("prospect_lead_id") or "") or None, flow_type=flow_type,
        entity_type=resolved_entity_type,
        entity_id=resolved_entity_id,
        action_type=action_type, payload=payload,
    )
    return serialize_journey(cursor, {**journey, **claimed}, public=False), action


def claim_journey(cursor: Any, *, token: str, user_id: str, business_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    journey = load_public_journey(cursor, token, lock=True)
    return _claim_loaded_journey(cursor, journey=journey, user_id=user_id, business_id=business_id)


def claim_reserved_journey(cursor: Any, *, user_id: str) -> tuple[dict[str, Any], dict[str, Any]] | None:
    """Resume a registration-bound journey without putting its public token in email."""
    cursor.execute(
        """
        SELECT * FROM lead_journeys
        WHERE claimed_user_id = %s AND status = 'registration_pending'
          AND revoked_at IS NULL AND expires_at > NOW()
        ORDER BY updated_at DESC
        LIMIT 1
        FOR UPDATE
        """,
        (user_id,),
    )
    journey = _row(cursor, cursor.fetchone())
    if not journey:
        return None
    business_id = str(journey.get("claimed_business_id") or "")
    if not business_id:
        raise JourneyError("У персонального сценария потерян бизнес", 409, "journey_business_missing")
    return _claim_loaded_journey(cursor, journey=journey, user_id=user_id, business_id=business_id)


def serialize_action(action: dict[str, Any]) -> dict[str, Any]:
    payload = _json_object(action.get("payload_json"))
    target = _json_object(action.get("cta_target_json"))
    action_id = str(action.get("id") or "")
    action_type = str(action.get("action_type") or "")
    action_status = str(action.get("status") or "ready")
    target["action_id"] = action_id
    result_requirements = {
        "check_reply": ["outcome"],
        "define_terms": ["details"],
        "mark_published": ["publication_url"],
        "mark_launched": ["mechanic"],
        "add_result": ["inquiries", "sales", "note"],
        "review_content": ["draft_text"],
        "save_to_calendar": ["scheduled_for"],
        "waiting_for_publication": ["publication_url"],
        "add_content_result": ["views", "inquiries", "note"],
    }.get(action_type, [])
    return {
        "id": action_id,
        "journey_id": str(action.get("journey_id") or "") or None,
        "business_id": str(action.get("business_id") or "") or None,
        "lead_id": str(action.get("lead_id") or "") or None,
        "flow_type": str(action.get("flow_type") or ""),
        "entity_type": str(action.get("entity_type") or ""),
        "entity_id": str(action.get("entity_id") or "") or None,
        "action_type": action_type,
        "status": action_status,
        "priority": int(action.get("priority") or 0),
        "due_at": _iso(action.get("due_at")),
        "title": str(action.get("title") or ""),
        "description": str(action.get("description") or ""),
        "reason": str(action.get("description") or ""),
        "domain_summary": payload.get("domain_summary") or payload.get("mechanic") or "",
        "cta_label": str(action.get("cta_label") or "Продолжить"),
        "cta_target": target,
        "payload": payload,
        "allowed_commands": (
            [] if action_type == "compare_snapshot" and action_status == "waiting"
            else ["retry_refresh"] if action_type == "compare_snapshot" and action_status == "blocked"
            else list(ACTION_COMMANDS.get(action_type, ()))
        ),
        "result_requirements": result_requirements,
        "version": int(action.get("version") or 1),
        "completed_at": _iso(action.get("completed_at")),
        "created_at": _iso(action.get("created_at")),
        "updated_at": _iso(action.get("updated_at")),
    }


def reconcile_map_actions(cursor: Any, *, business_ids: list[str]) -> None:
    if not business_ids:
        return
    cursor.execute(
        """
        UPDATE journey_actions action
        SET status = 'ready',
            payload_json = action.payload_json || jsonb_build_object(
                'verification_status', 'refresh_verified',
                'refresh_verified_at', NOW()
            ),
            version = version + 1,
            updated_at = NOW()
        WHERE action.business_id = ANY(%s)
          AND action.flow_type = 'maps'
          AND action.action_type = 'compare_snapshot'
          AND action.status = 'waiting'
          AND EXISTS (
              SELECT 1 FROM parsequeue queue
              WHERE queue.id = action.payload_json->>'refresh_queue_id'
                AND queue.status IN ('completed', 'success')
          )
        """,
        (business_ids,),
    )
    cursor.execute(
        """
        UPDATE journey_actions action
        SET status = 'blocked',
            payload_json = action.payload_json || jsonb_build_object(
                'verification_status', 'refresh_failed',
                'refresh_error', COALESCE(queue.error_message, 'map_refresh_failed')
            ),
            version = version + 1,
            updated_at = NOW()
        FROM parsequeue queue
        WHERE action.business_id = ANY(%s)
          AND action.flow_type = 'maps'
          AND action.action_type = 'compare_snapshot'
          AND action.status = 'waiting'
          AND queue.id = action.payload_json->>'refresh_queue_id'
          AND queue.status IN ('error', 'failed', 'cancelled')
        """,
        (business_ids,),
    )


def list_actions(cursor: Any, *, business_id: str, history: bool = False) -> list[dict[str, Any]]:
    if not history:
        reconcile_map_actions(cursor, business_ids=[business_id])
    statuses = tuple(sorted(FINAL_ACTION_STATUSES if history else ACTIVE_ACTION_STATUSES))
    cursor.execute(
        """
        SELECT * FROM journey_actions
        WHERE business_id = %s AND status = ANY(%s)
        ORDER BY
          CASE WHEN due_at IS NOT NULL AND due_at <= NOW() THEN 0 ELSE 1 END,
          priority DESC, due_at NULLS LAST, created_at
        LIMIT %s
        """,
        (business_id, list(statuses), 100 if history else 30),
    )
    return [serialize_action(_row(cursor, value)) for value in (cursor.fetchall() or [])]


def build_growth_paths(*, actions: list[dict[str, Any]], capabilities: set[str]) -> list[dict[str, Any]]:
    """Project journey actions into the user-facing growth paths."""
    copy = {
        "maps": {
            "title": "Карты",
            "opportunity": "Исправьте самый заметный барьер в карточке и сравните результат после обновления.",
            "cta_label": "Открыть план по картам",
            "screen": "progress",
        },
        "content": {
            "title": "Контент для соцсетей",
            "opportunity": "Подготовьте полезную публикацию и проведите её до измеримого результата.",
            "cta_label": "Открыть контент",
            "screen": "content",
        },
        "maps_content": {
            "title": "Контент для карточек",
            "opportunity": "Готовьте новости для карт и поддерживайте профиль бизнеса актуальным.",
            "cta_label": "Открыть новости для карт",
            "screen": "card_news",
        },
        "influencer": {
            "title": "Инфлюенсеры",
            "opportunity": "Получите клиентов от местных авторов через взаимовыгодный обмен.",
            "cta_label": "Найти автора",
            "screen": "influencers",
        },
        "partnership": {
            "title": "Партнёрства",
            "opportunity": "Получите новых клиентов через совместные предложения с бизнесами, у которых похожая аудитория.",
            "cta_label": "Найти партнёра",
            "screen": "partnerships",
        },
        "automation": {
            "title": "Автоматизация",
            "opportunity": "Поручите ИИ-агентам регулярные задачи и контролируйте результат.",
            "cta_label": "Настроить автоматизацию",
            "screen": "agents",
        },
        "average_ticket": {
            "title": "Средний чек",
            "opportunity": "Соберите понятные пакеты услуг и выберите уместный сценарий допродажи.",
            "cta_label": "Открыть средний чек",
            "screen": "average_ticket",
        },
    }
    required_capabilities = {
        "maps": "maps",
        "content": "social_content",
        "maps_content": "maps.news",
        "influencer": "influencers",
        "partnership": "partnerships",
        "automation": "automation",
        "average_ticket": "average_ticket",
    }
    required_tiers = {
        "maps": ("starter", "Карты"),
        "content": ("concierge", "Управление"),
        "maps_content": ("starter", "Карты"),
        "influencer": ("professional", "Привлечение"),
        "partnership": ("professional", "Привлечение"),
        "automation": ("concierge", "Управление"),
        "average_ticket": ("concierge", "Управление"),
    }
    active_by_flow: dict[str, dict[str, Any]] = {}
    for action in actions:
        flow_type = str(action.get("flow_type") or "")
        if flow_type in copy and flow_type not in active_by_flow:
            active_by_flow[flow_type] = action
    result: list[dict[str, Any]] = []
    for flow_type in ("maps", "maps_content", "content", "influencer", "partnership", "automation", "average_ticket"):
        base = copy[flow_type]
        action = active_by_flow.get(flow_type)
        requires_payment = required_capabilities[flow_type] not in capabilities
        access_status = "payment_required" if requires_payment else "available"
        required_tier, required_tier_name = required_tiers[flow_type]
        result.append({
            "flow_type": flow_type,
            "title": base["title"],
            "status": str(action.get("status") or "ready") if action else "not_started",
            "opportunity": str(action.get("reason") or base["opportunity"]) if action else base["opportunity"],
            "obstacle": str((action.get("payload") or {}).get("refresh_error") or "") if action and action.get("status") == "blocked" else "",
            "access": {
                "status": access_status,
                "reason": f"Направление входит в тариф «{required_tier_name}»." if requires_payment else "Доступно для текущего бизнеса.",
                "cta_label": f"Выбрать тариф «{required_tier_name}»" if requires_payment else str(action.get("cta_label") or base["cta_label"]) if action else base["cta_label"],
                "cta_target": {"screen": "settings" if requires_payment else base["screen"], "action_id": None if requires_payment else action.get("id") if action else None},
                "entitlement_source": "subscription" if requires_payment else "account",
                "required_tier": required_tier,
            },
            "action": action,
        })
    return result


def load_action(cursor: Any, *, action_id: str, business_id: str, lock: bool = False) -> dict[str, Any]:
    lock_clause = "FOR UPDATE" if lock else ""
    cursor.execute(
        f"SELECT * FROM journey_actions WHERE id = %s AND business_id = %s {lock_clause}",
        (action_id, business_id),
    )
    action = _row(cursor, cursor.fetchone())
    if not action:
        raise JourneyError("Действие не найдено", 404, "action_not_found")
    return action


def _next_action_spec(action: dict[str, Any], command: str, payload: dict[str, Any]) -> tuple[str | None, str, datetime | None, dict[str, Any]]:
    action_type = str(action.get("action_type") or "")
    flow = str(action.get("flow_type") or "")
    current_payload = {**_json_object(action.get("payload_json")), **payload}
    if command == "copy":
        return None, "in_progress", None, current_payload
    if action_type == "browse_creators" and command == "complete":
        return "send_message", "completed", None, current_payload
    if action_type in {"send_message", "send_followup"} and command == "mark_sent":
        return "check_reply", "completed", datetime.now(timezone.utc) + timedelta(days=4), current_payload
    if action_type == "check_reply" and command == "prepare_followup":
        return "send_followup", "completed", None, current_payload
    if action_type == "check_reply" and command == "record_reply":
        outcome = str(payload.get("outcome") or "other")
        if outcome not in {"interested", "paid", "barter", "details", "refused", "not_interested", "other"}:
            raise JourneyError("Результат ответа не поддерживается", 400, "invalid_reply_outcome")
        current_payload["reply_outcome"] = outcome
        if outcome in {"refused", "not_interested"}:
            return ("select_next_influencer" if flow == "influencer" else "select_next_partner"), "completed", None, current_payload
        return "define_terms", "completed", None, current_payload
    if action_type == "define_terms" and command == "save_terms":
        if not str(payload.get("details") or "").strip():
            raise JourneyError("Зафиксируйте условия договорённости", 400, "terms_required")
        return ("mark_published" if flow == "influencer" else "mark_launched"), "completed", None, current_payload
    if action_type == "mark_published":
        if not str(payload.get("publication_url") or "").strip():
            raise JourneyError("Добавьте ссылку на размещение", 400, "publication_url_required")
        return "add_result", "completed", None, current_payload
    if action_type == "mark_launched":
        if not str(payload.get("mechanic") or "").strip():
            raise JourneyError("Укажите механику партнёрства", 400, "partnership_mechanic_required")
        return "add_result", "completed", None, current_payload
    if action_type == "add_result":
        current_payload["cycle_completed"] = True
        return ("select_next_influencer" if flow == "influencer" else "select_next_partner"), "completed", None, current_payload
    if action_type in {"select_next_influencer", "select_next_partner"}:
        current_payload["cycle_key"] = str(uuid.uuid4())
        return "send_message", "completed", None, current_payload
    if action_type == "complete_map_task":
        current_payload["verification_status"] = "user_reported"
        current_payload["user_reported_at"] = datetime.now(timezone.utc).isoformat()
        index = int(current_payload.get("task_index") or 0)
        total = max(1, int(current_payload.get("tasks_total") or 1))
        if index + 1 < total:
            current_payload["task_index"] = index + 1
            tasks = current_payload.get("tasks") if isinstance(current_payload.get("tasks"), list) else []
            if index + 1 < len(tasks) and isinstance(tasks[index + 1], dict):
                current_payload["task_title"] = str(tasks[index + 1].get("title") or "Следующая задача по картам")
                current_payload["task_reason"] = str(tasks[index + 1].get("reason") or "Следующий пункт недельного плана.")
            return "complete_map_task", "completed", None, current_payload
        return "refresh_data", "completed", None, current_payload
    if action_type == "refresh_data":
        current_payload["refresh_requested"] = True
        return "compare_snapshot", "completed", None, current_payload
    if action_type == "compare_snapshot" and command == "retry_refresh":
        refresh_error = str(current_payload.get("refresh_error") or "").lower()
        if any(marker in refresh_error for marker in ("hard limit", "usage limit", "monthly limit", "quota")):
            current_payload["refresh_source_override"] = "yandex_maps"
        current_payload["verification_status"] = "refresh_retry_requested"
        current_payload.pop("refresh_error", None)
        return "refresh_data", "completed", None, current_payload
    if action_type == "compare_snapshot" and command == "complete":
        current_payload["cycle_completed"] = True
        return "start_next_map_plan", "completed", None, current_payload
    if action_type == "start_next_map_plan":
        current_payload["cycle_key"] = str(uuid.uuid4())
        current_payload["task_index"] = 0
        return "complete_map_task", "completed", None, current_payload
    if action_type == "prepare_content" and command == "prepare":
        return "review_content", "completed", None, current_payload
    if action_type == "review_content" and command == "save_draft":
        if not str(payload.get("draft_text") or "").strip():
            raise JourneyError("Добавьте текст черновика", 400, "content_draft_required")
        return "save_to_calendar", "completed", None, current_payload
    if action_type == "save_to_calendar" and command == "schedule":
        if not str(payload.get("scheduled_for") or "").strip():
            raise JourneyError("Выберите дату публикации", 400, "content_schedule_required")
        return "waiting_for_publication", "completed", None, current_payload
    if action_type == "waiting_for_publication" and command == "mark_published":
        if not str(payload.get("publication_url") or "").strip():
            raise JourneyError("Добавьте ссылку на публикацию", 400, "publication_url_required")
        return "add_content_result", "completed", None, current_payload
    if action_type == "add_content_result" and command == "add_result":
        current_payload["cycle_completed"] = True
        return "start_next_content_cycle", "completed", None, current_payload
    if action_type == "start_next_content_cycle" and command == "start_next_cycle":
        current_payload["cycle_key"] = str(uuid.uuid4())
        current_payload.pop("draft_text", None)
        current_payload.pop("scheduled_for", None)
        current_payload.pop("publication_url", None)
        return "prepare_content", "completed", None, current_payload
    if action_type == "configure_automation" and command == "save_configuration":
        if not str(payload.get("use_case") or "").strip():
            raise JourneyError("Выберите задачу для ИИ-сотрудника", 400, "automation_use_case_required")
        if not str(payload.get("expected_result") or "").strip():
            raise JourneyError("Укажите ожидаемый результат", 400, "automation_result_required")
        current_payload["approval_required"] = True
        return "review_automation_preflight", "completed", None, current_payload
    if action_type == "review_automation_preflight" and command == "approve":
        if payload.get("confirmed") is not True:
            raise JourneyError("Подтвердите план запуска", 400, "automation_preflight_confirmation_required")
        current_payload["preflight_reviewed_at"] = datetime.now(timezone.utc).isoformat()
        return "run_automation", "completed", None, current_payload
    if action_type == "run_automation" and command == "link_run":
        return "review_automation_result", "completed", None, current_payload
    if action_type == "review_automation_result" and command == "add_result":
        if not str(payload.get("result_summary") or "").strip():
            raise JourneyError("Кратко укажите подтверждённый результат", 400, "automation_result_summary_required")
        current_payload["cycle_completed"] = True
        return "start_next_automation_cycle", "completed", None, current_payload
    if action_type == "start_next_automation_cycle" and command == "start_next_cycle":
        current_payload["cycle_key"] = str(uuid.uuid4())
        current_payload.pop("run_id", None)
        current_payload.pop("result_summary", None)
        current_payload.pop("preflight_reviewed_at", None)
        return "configure_automation", "completed", None, current_payload
    if action_type == "upgrade" and command == "open_upgrade":
        return None, "in_progress", None, current_payload
    raise JourneyError("Переход не поддерживается", 409, "transition_not_allowed")


def _update_domain(cursor: Any, action: dict[str, Any], command: str, payload: dict[str, Any]) -> dict[str, Any]:
    domain_updates: dict[str, Any] = {}
    entity_type = str(action.get("entity_type") or "")
    entity_id = str(action.get("entity_id") or "")
    flow = str(action.get("flow_type") or "")
    if flow == "influencer" and str(action.get("action_type") or "") == "browse_creators" and command == "complete":
        cursor.execute(
            """
            SELECT COUNT(*)::INT AS shortlisted_count
            FROM creator_search_results result
            JOIN creator_search_jobs job ON job.id = result.search_job_id
            WHERE job.business_id = %s AND result.shortlist_status = 'shortlisted'
            """,
            (action.get("business_id"),),
        )
        shortlist = _row(cursor, cursor.fetchone())
        shortlist_count = int(shortlist.get("shortlisted_count") or 0)
        if shortlist_count < 1:
            raise JourneyError("Сначала добавьте в shortlist хотя бы одного автора", 409, "creator_shortlist_required")
        domain_updates["shortlist_count"] = shortlist_count
    if flow == "maps" and str(action.get("action_type") or "") == "refresh_data" and command == "complete":
        from services.operator_map_refresh import enqueue_operator_map_refresh
        refresh = enqueue_operator_map_refresh(
            cursor,
            business_id=str(action.get("business_id") or ""),
            user_id=str(action.get("user_id") or ""),
            source_override=_json_object(action.get("payload_json")).get("refresh_source_override"),
            require_runtime_flag=True,
        )
        if refresh.get("status") != "queued":
            reasons = ", ".join(str(value) for value in refresh.get("blocked_reasons") or [])
            raise JourneyError(
                f"Обновление карты требует проверки: {reasons or 'недоступно'}",
                409,
                "map_refresh_blocked",
            )
        domain_updates.update({
            "refresh_queue_id": refresh.get("queue_id"),
            "refresh_queue_status": refresh.get("queue_status"),
            "verification_status": "refresh_queued",
        })
    if flow == "partnership" and command == "record_reply" and entity_type == "lead_workstream" and entity_id:
        cursor.execute(
            """
            SELECT touch.id AS touch_id, campaign.id AS campaign_id
            FROM outreach_campaigns campaign
            JOIN outreach_campaign_touches touch ON touch.campaign_id = campaign.id
            WHERE campaign.workstream_id = %s
              AND touch.status IN ('awaiting_manual_send', 'needs_attention', 'manual_expired', 'manual_sent', 'sent', 'delivered')
            ORDER BY touch.sequence_index DESC LIMIT 1
            """,
            (entity_id,),
        )
        touch = _row(cursor, cursor.fetchone())
        if touch:
            from services.outreach_campaign_service import record_manual_touch
            record_manual_touch(
                cursor, str(touch["campaign_id"]), str(touch["touch_id"]), "reply",
                user_id=str(action.get("user_id") or ""),
                note=str(payload.get("note") or payload.get("outcome") or "reply"),
            )
    if flow == "partnership" and entity_type == "lead_workstream" and entity_id:
        if command == "mark_launched":
            cursor.execute(
                "UPDATE lead_workstreams SET partnership_launched_at = COALESCE(partnership_launched_at, NOW()), partnership_outcome_json = partnership_outcome_json || %s, updated_at = NOW() WHERE id = %s",
                (Json({"mechanic": payload.get("mechanic"), "promo_code": payload.get("promo_code")}), entity_id),
            )
        elif command == "add_result":
            cursor.execute(
                "UPDATE lead_workstreams SET partnership_outcome_json = partnership_outcome_json || %s, updated_at = NOW() WHERE id = %s",
                (Json({"result": payload}), entity_id),
            )
    if flow == "influencer" and entity_type == "creator_collaboration" and entity_id:
        status_by_command = {"save_terms": "agreed", "mark_published": "published", "add_result": "measuring"}
        status = status_by_command.get(command)
        if status:
            cursor.execute(
                "UPDATE creator_collaborations SET status = %s, updated_at = NOW() WHERE id = %s AND business_id = %s",
                (status, entity_id, action.get("business_id")),
            )
    if flow == "content":
        content_item_id = entity_id or str(payload.get("content_plan_item_id") or "").strip()
        if command in {"save_draft", "schedule", "mark_published", "add_result"} and not content_item_id:
            raise JourneyError("Сначала выберите материал в разделе «Контент»", 409, "content_item_required")
        if content_item_id:
            if command == "save_draft":
                cursor.execute(
                    """
                    UPDATE contentplanitems
                    SET draft_text = %s, status = 'edited', updated_at = NOW()
                    WHERE id = %s AND business_id = %s
                    RETURNING id
                    """,
                    (str(payload.get("draft_text") or ""), content_item_id, action.get("business_id")),
                )
            elif command == "schedule":
                cursor.execute(
                    """
                    UPDATE contentplanitems
                    SET scheduled_for = %s, status = 'approved', updated_at = NOW()
                    WHERE id = %s AND business_id = %s
                    RETURNING id
                    """,
                    (payload.get("scheduled_for"), content_item_id, action.get("business_id")),
                )
            elif command == "mark_published":
                cursor.execute(
                    """
                    UPDATE contentplanitems
                    SET status = 'published',
                        metadata_json = COALESCE(metadata_json, '{}'::jsonb) || %s,
                        updated_at = NOW()
                    WHERE id = %s AND business_id = %s
                    RETURNING id
                    """,
                    (Json({"journey_publication": {"url": payload.get("publication_url"), "reported_at": datetime.now(timezone.utc).isoformat()}}), content_item_id, action.get("business_id")),
                )
            elif command == "add_result":
                cursor.execute(
                    """
                    UPDATE contentplanitems
                    SET metadata_json = COALESCE(metadata_json, '{}'::jsonb) || %s,
                        updated_at = NOW()
                    WHERE id = %s AND business_id = %s
                    RETURNING id
                    """,
                    (Json({"journey_result": payload}), content_item_id, action.get("business_id")),
                )
            if command in {"save_draft", "schedule", "mark_published", "add_result"}:
                updated = _row(cursor, cursor.fetchone())
                if not updated:
                    raise JourneyError("Материал не найден или недоступен", 404, "content_item_not_found")
            domain_updates["content_plan_item_id"] = content_item_id
            domain_updates["entity_id"] = content_item_id
    if flow == "automation" and command == "link_run":
        run_id = str(payload.get("run_id") or "").strip()
        if run_id:
            cursor.execute(
                """
                SELECT id, blueprint_id, status, completed_at
                FROM agent_runs
                WHERE id = %s AND business_id = %s
                LIMIT 1
                """,
                (run_id, action.get("business_id")),
            )
        else:
            reviewed_at = _json_object(action.get("payload_json")).get("preflight_reviewed_at")
            cursor.execute(
                """
                SELECT id, blueprint_id, status, completed_at
                FROM agent_runs
                WHERE business_id = %s
                  AND status = 'completed'
                  AND (%s IS NULL OR completed_at >= %s::timestamptz)
                ORDER BY completed_at DESC NULLS LAST, updated_at DESC
                LIMIT 1
                """,
                (action.get("business_id"), reviewed_at, reviewed_at),
            )
        run = _row(cursor, cursor.fetchone())
        if not run:
            raise JourneyError("Сначала завершите запуск ИИ-сотрудника", 409, "automation_run_not_found")
        if str(run.get("status") or "") != "completed":
            raise JourneyError("Дождитесь успешного завершения запуска", 409, "automation_run_not_completed")
        domain_updates.update({
            "run_id": str(run.get("id") or ""),
            "blueprint_id": str(run.get("blueprint_id") or ""),
            "run_status": "completed",
            "run_completed_at": _iso(run.get("completed_at")),
        })
    return domain_updates


def _record_business_action(cursor: Any, action: dict[str, Any], command: str, payload: dict[str, Any]) -> None:
    if command not in {"mark_sent", "mark_launched", "mark_published", "add_result", "complete"}:
        return
    cursor.execute("SELECT to_regclass('public.business_action_events')")
    exists = cursor.fetchone()
    if not exists or not (exists[0] if isinstance(exists, (tuple, list)) else _row(cursor, exists).get("to_regclass")):
        return
    source_id = f"journey-action:{action.get('id')}:{command}"
    cursor.execute(
        """
        INSERT INTO business_action_events (
            id, business_id, action_type, source_type, source_id, status, after_json, metadata_json
        ) VALUES (%s, %s, %s, 'lead_journey', %s, 'confirmed', %s, %s)
        ON CONFLICT (business_id, action_type, source_type, source_id) DO NOTHING
        """,
        (str(uuid.uuid4()), action.get("business_id"), f"journey_{command}", source_id, Json(payload), Json({"flow_type": action.get("flow_type"), "entity_type": action.get("entity_type"), "entity_id": action.get("entity_id")})),
    )


def _maybe_create_upgrade(cursor: Any, *, action: dict[str, Any]) -> None:
    if not journey_enabled("JOURNEY_UPSELL_ENABLED") or not action.get("business_id"):
        return
    cursor.execute(
        """
        SELECT COUNT(*) FILTER (WHERE status = 'completed') AS completed,
               COUNT(*) FILTER (WHERE status = 'completed' AND COALESCE((payload_json->>'cycle_completed')::boolean, FALSE)) AS cycles
        FROM journey_actions WHERE business_id = %s
        """,
        (action["business_id"],),
    )
    stats = _row(cursor, cursor.fetchone())
    if int(stats.get("completed") or 0) < 3 or int(stats.get("cycles") or 0) < 1:
        return
    ensure_action(
        cursor, journey_id=str(action.get("journey_id") or "") or None,
        business_id=str(action["business_id"]), user_id=str(action.get("user_id") or "") or None,
        lead_id=str(action.get("lead_id") or "") or None, flow_type="upgrade",
        entity_type="subscription", entity_id=str(action["business_id"]), action_type="upgrade",
        payload={"cycle_key": "first-eligible", "completed_actions": int(stats.get("completed") or 0)},
        source_action_id=str(action.get("id") or "") or None,
    )


def execute_command(
    cursor: Any,
    *,
    action_id: str,
    business_id: str,
    user_id: str,
    command: str,
    expected_version: int,
    idempotency_key: str,
    surface: str,
    payload: dict[str, Any],
) -> dict[str, Any]:
    action = load_action(cursor, action_id=action_id, business_id=business_id, lock=True)
    cursor.execute("SELECT * FROM journey_action_events WHERE action_id = %s AND idempotency_key = %s", (action_id, idempotency_key))
    existing_event = _row(cursor, cursor.fetchone())
    if existing_event:
        current = load_action(cursor, action_id=action_id, business_id=business_id)
        cursor.execute(
            """
            SELECT * FROM journey_actions
            WHERE source_action_id = %s AND business_id = %s AND flow_type = %s
            ORDER BY created_at DESC LIMIT 1
            """,
            (action_id, business_id, action.get("flow_type")),
        )
        replayed_next = _row(cursor, cursor.fetchone())
        return {
            "action": serialize_action(current),
            "next_action": serialize_action(replayed_next) if replayed_next else None,
            "idempotent_replay": True,
        }
    if int(action.get("version") or 1) != int(expected_version):
        raise JourneyError("Действие уже изменилось на другом устройстве", 409, "stale_action")
    if str(action.get("status") or "") in FINAL_ACTION_STATUSES:
        raise JourneyError("Действие уже завершено", 409, "action_final")
    allowed = ACTION_COMMANDS.get(str(action.get("action_type") or ""), ())
    if command not in allowed:
        raise JourneyError("Команда недоступна для этого действия", 409, "command_not_allowed")
    next_type, result_status, next_due_at, merged_payload = _next_action_spec(action, command, payload)
    domain_updates = _update_domain(cursor, action, command, payload)
    merged_payload.update(domain_updates)
    completed_at = datetime.now(timezone.utc) if result_status == "completed" else None
    cursor.execute(
        """
        UPDATE journey_actions
        SET status = %s, payload_json = %s, completed_at = %s,
            version = version + 1, updated_at = NOW()
        WHERE id = %s
        RETURNING *
        """,
        (result_status, Json(merged_payload), completed_at, action_id),
    )
    updated = _row(cursor, cursor.fetchone())
    cursor.execute(
        """
        INSERT INTO journey_action_events (
            id, action_id, event_type, command, from_status, to_status,
            actor_type, actor_id, surface, idempotency_key, payload_json
        ) VALUES (%s, %s, 'command', %s, %s, %s, 'user', %s, %s, %s, %s)
        """,
        (str(uuid.uuid4()), action_id, command, action.get("status"), result_status,
         user_id, surface, idempotency_key, Json(payload)),
    )
    _record_business_action(cursor, action, command, payload)
    next_action = None
    if next_type:
        next_action = ensure_action(
            cursor, journey_id=str(action.get("journey_id") or "") or None,
            business_id=business_id, user_id=user_id,
            lead_id=str(action.get("lead_id") or "") or None,
            flow_type=str(action.get("flow_type") or ""), entity_type=str(action.get("entity_type") or ""),
            entity_id=str(merged_payload.get("entity_id") or action.get("entity_id") or "") or None, action_type=next_type,
            payload=merged_payload, source_action_id=action_id,
            status="waiting" if next_type in {"check_reply", "compare_snapshot"} else "ready", due_at=next_due_at,
        )
    _maybe_create_upgrade(cursor, action=updated)
    return {"action": serialize_action(updated), "next_action": next_action, "idempotent_replay": False}
