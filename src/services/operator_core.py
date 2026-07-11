from __future__ import annotations

import re
import json
import hashlib
import uuid
from dataclasses import asdict, dataclass
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Callable

from core.action_orchestrator import ActionOrchestrator
from services.agent_capability_handlers import CANONICAL_CAPABILITIES, build_capability_handlers, capability_runtime_contract
from services.operator_capabilities import (
    build_operator_help_response,
    classify_operator_help_intent,
    classify_unanswered_reviews_status_intent,
    get_unanswered_reviews_status,
)
from services.operator_fresh_reviews import classify_fresh_reviews_intent, refresh_reviews_from_operator
from services.operator_intent_ai_router import classify_operator_intent_with_ai, should_use_ai_intent_router
from services.operator_manual_review import classify_operator_chat_intent, process_operator_chat_message
from services.operator_news_generation import classify_news_generate_intent, generate_news_draft_from_operator
from services.operator_review_reply_bulk import (
    classify_bulk_review_reply_intent,
    generate_review_reply_drafts_for_unanswered_reviews,
)
from services.operator_services_optimization import (
    apply_service_optimization_suggestions,
    classify_services_apply_intent,
    classify_services_optimize_intent,
    optimize_services_from_operator,
)
from services.operator_social_post_generation import classify_social_post_generate_intent, generate_social_post_draft_from_operator
from services.operator_conversations import finish_operator_action, get_operator_action


@dataclass(frozen=True)
class OperatorCapability:
    name: str
    title: str
    status: str
    risk_class: str
    approval_policy: str
    result_href: str
    examples: tuple[str, ...]
    backend_capability: str | None = None


CAPABILITIES: tuple[OperatorCapability, ...] = (
    OperatorCapability("operator.help", "Возможности Оператора", "available", "read_only", "none", "/dashboard/operator", ("Что ты умеешь?",)),
    OperatorCapability("maps.refresh", "Обновление карточки и отзывов", "available", "paid_external", "credit_policy", "/dashboard/card", ("Обнови карточку", "Проверь новые отзывы")),
    OperatorCapability("reviews.read", "Отзывы без ответа", "available", "read_only", "none", "/dashboard/card?tab=reviews&review_filter=needs_reply", ("Есть отзывы без ответа?",)),
    OperatorCapability("reviews.reply.draft", "Черновики ответов", "draft_only", "paid_compute", "credit_policy", "/dashboard/card?tab=reviews&review_filter=needs_reply", ("Подготовь ответы на отзывы",)),
    OperatorCapability("reviews.manual.add", "Добавление отзыва и черновика ответа", "available", "write_internal", "explicit_command", "/dashboard/card?tab=reviews&review_filter=needs_reply", ("Добавь отзыв и подготовь ответ",)),
    OperatorCapability("news.generate", "Черновик новости", "draft_only", "paid_compute", "credit_policy", "/dashboard/content", ("Создай новость про акцию",)),
    OperatorCapability("social_post.generate", "Черновик поста", "draft_only", "paid_compute", "credit_policy", "/dashboard/content", ("Подготовь пост для соцсетей",)),
    OperatorCapability("content_plan.generate", "Контент-план", "available", "write_internal", "explicit_command", "/dashboard/content", ("Сделай контент-план на 30 дней",), "content_plan.item.create_draft"),
    OperatorCapability("services.optimize", "Оптимизация услуг", "draft_only", "paid_compute", "credit_policy", "/dashboard/card?tab=services", ("Оптимизируй услуги",)),
    OperatorCapability("services.apply", "Применение предложений по услугам", "approval_required", "bulk_write", "separate_confirmation", "/dashboard/card?tab=services", ("Примени предложения по услугам",)),
    OperatorCapability("services.price.update", "Изменение цены одной услуги", "available", "write_internal", "explicit_command", "/dashboard/card?tab=services", ("Измени цену услуги Маникюр на 1500",)),
    OperatorCapability("finance.manage", "Финансы и импорты", "request_only", "financial", "separate_confirmation", "/dashboard/finance", ("Добавь расход", "Покажи финансовый итог"), "finance.transaction.create"),
    OperatorCapability("average_ticket.manage", "Средний чек и допродажи", "manual", "read_or_draft", "manual_handoff", "/dashboard/average-ticket", ("Как увеличить средний чек?",)),
    OperatorCapability("appointments.manage", "Бронирования", "available", "read_only", "none", "/dashboard/bookings", ("Покажи записи на завтра",), "appointments.read"),
    OperatorCapability("communications.manage", "Чаты и сообщения", "request_only", "communication", "separate_confirmation", "/dashboard/chats", ("Подготовь сообщение клиентам",), "communications.draft"),
    OperatorCapability("partnerships.manage", "Партнёрства и outreach", "request_only", "external_send", "separate_confirmation", "/dashboard/partnerships", ("Найди партнёров рядом",), "partnership.draft_offer"),
    OperatorCapability("network.manage", "Сеть и локации", "manual", "write_internal", "manual_handoff", "/dashboard/network", ("Покажи проблемные локации",)),
    OperatorCapability("agents.manage", "ИИ-сотрудники", "manual", "privileged", "manual_handoff", "/dashboard/agents", ("Покажи моих ИИ-сотрудников",)),
    OperatorCapability("settings.manage", "Настройки и подключения", "manual", "identity_access", "manual_handoff", "/dashboard/settings", ("Проверь подключения",)),
    OperatorCapability("support.manage", "Поддержка и диагностика", "manual", "support_read", "manual_handoff", "/dashboard/settings/integrations", ("Почему не работает подключение?",)),
    OperatorCapability("reviews.publish_external", "Публикация ответов в карты", "gap", "write_external", "separate_confirmation", "/dashboard/card?tab=reviews", ("Опубликуй ответы в Яндекс",)),
    OperatorCapability("content.publish_external", "Автопубликация во внешние каналы", "gap", "write_external", "separate_confirmation", "/dashboard/content", ("Опубликуй новость во всех каналах",)),
)


CAPABILITY_BY_NAME = {item.name: item for item in CAPABILITIES}
OPERATOR_ACTION_ORCHESTRATOR = ActionOrchestrator(build_capability_handlers())


MANUAL_MATCHERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("finance.manage", ("финанс", "расход", "доход", "выруч", "транзакц")),
    ("average_ticket.manage", ("средн", "допрод", "чек")),
    ("appointments.manage", ("бронир", "запис", "визит")),
    ("communications.manage", ("чат", "сообщен", "напоминан", "клиентам")),
    ("partnerships.manage", ("партнер", "партнёр", "outreach", "предложен")),
    ("network.manage", ("локац", "филиал", "сеть")),
    ("agents.manage", ("агент", "ии-сотруд", "ии сотруд")),
    ("settings.manage", ("настрой", "подключен", "интеграц")),
    ("support.manage", ("диагност", "не работает", "ошибк")),
)


OPERATOR_ACTION_MARKERS = (
    "добав",
    "измени",
    "поменя",
    "установ",
    "созд",
    "сдел",
    "состав",
    "подготов",
    "проверь",
    "обнов",
    "покажи",
    "найди",
    "отправ",
    "оптимиз",
    "примени",
    "удали",
)


def should_route_operator_message(message: Any) -> bool:
    lowered = str(message or "").strip().lower()
    conversational_queries = ("что ты умее", "есть отзыв", "сколько отзыв")
    return len(lowered) >= 5 and (
        any(marker in lowered for marker in OPERATOR_ACTION_MARKERS)
        or any(query in lowered for query in conversational_queries)
    )


def operator_capability_catalog() -> list[dict[str, Any]]:
    catalog = []
    for item in CAPABILITIES:
        serialized = asdict(item)
        backend_name = item.backend_capability or item.name
        backend_meta = CANONICAL_CAPABILITIES.get(backend_name)
        if backend_meta:
            serialized["runtime"] = capability_runtime_contract(backend_name)
            serialized["backend_contract"] = dict(backend_meta)
        else:
            serialized["runtime"] = {"capability": backend_name, "runtime_status": "operator_native", "beta_enabled": True}
        catalog.append(serialized)
    return catalog


def _result_ref(capability: str, entity_id: Any = None, href: Any = None, label: Any = None) -> dict[str, Any]:
    spec = CAPABILITY_BY_NAME.get(capability)
    target_href = str(href or (spec.result_href if spec else "/dashboard/operator")).strip()
    return {
        "entity_type": capability,
        "entity_id": str(entity_id or "").strip() or None,
        "label": str(label or (f"Открыть {spec.title.lower()}" if spec else "Открыть результат")),
        "href": target_href,
    }


def _action(action: str, label: str, *, href: str = "", payload: dict[str, Any] | None = None) -> dict[str, Any]:
    return {"action": action, "label": label, "href": href, "payload": payload or {}}


def standardize_operator_result(result: dict[str, Any], capability: str) -> dict[str, Any]:
    value = dict(result)
    spec = CAPABILITY_BY_NAME.get(capability)
    value["capability"] = capability
    value["capability_status"] = spec.status if spec else "gap"
    value["summary"] = str(value.get("chat_response") or value.get("summary") or "Команда обработана.")
    existing_ref = value.get("result_ref") if isinstance(value.get("result_ref"), dict) else {}
    entity_id = existing_ref.get("entity_id")
    if not entity_id:
        for key in ("news_draft", "social_post_draft", "draft", "optimization_job", "review"):
            item = value.get(key)
            if isinstance(item, dict) and item.get("id"):
                entity_id = item.get("id")
                break
    value["result_ref"] = _result_ref(
        capability,
        entity_id=entity_id,
        href=existing_ref.get("href"),
        label=existing_ref.get("label"),
    )
    ui_actions = list(value.get("ui_actions") or [])
    if value["result_ref"]["href"] and not any(str(item.get("href") or "") == value["result_ref"]["href"] for item in ui_actions if isinstance(item, dict)):
        ui_actions.append(
            _action(
                "open_result",
                value["result_ref"]["label"],
                href=value["result_ref"]["href"],
            )
        )
    value["ui_actions"] = ui_actions
    return value


def _execute_registered_capability(
    *,
    capability: str,
    business_id: str,
    user_id: str,
    channel: str,
    message: str,
    payload: dict[str, Any],
    orchestrator: ActionOrchestrator | None = None,
) -> dict[str, Any]:
    backend_name = str(CAPABILITY_BY_NAME[capability].backend_capability or capability)
    idempotency_source = f"{business_id}:{user_id}:{channel}:{backend_name}:{message.strip().lower()}"
    envelope = {
        "tenant_id": business_id,
        "actor": {"id": user_id, "type": "user", "channel": channel},
        "trace_id": str(uuid.uuid4()),
        "idempotency_key": "operator:" + hashlib.sha256(idempotency_source.encode("utf-8")).hexdigest(),
        "capability": backend_name,
        "payload": payload,
        "approval": {"mode": "auto", "ttl_sec": 1800},
        "billing": {"tariff_id": "operator", "reserve_tokens": 1},
    }
    execution = (orchestrator or OPERATOR_ACTION_ORCHESTRATOR).execute(
        envelope,
        {"user_id": user_id, "is_superadmin": False},
    )
    if not execution.get("success"):
        failed = {
            "status": "error",
            "chat_response": "Не удалось выполнить команду через безопасный контур LocalOS.",
            "error": execution.get("error"),
            "error_code": execution.get("error_code"),
            "action_id": execution.get("action_id"),
            "external_writes_performed": False,
        }
        return standardize_operator_result(failed, capability)
    backend_result = execution.get("result") if isinstance(execution.get("result"), dict) else {}
    count = int(backend_result.get("count") or 0)
    completed = {
        **backend_result,
        "status": "completed",
        "chat_response": f"Нашёл записей: {count}.",
        "action_id": execution.get("action_id"),
        "billing": execution.get("billing") or {},
        "external_writes_performed": False,
    }
    return standardize_operator_result(completed, capability)


def _appointments_payload(message: str, limit: Any) -> dict[str, Any]:
    lowered = message.lower()
    payload: dict[str, Any] = {"limit": max(1, min(int(limit or 5), 50))}
    if "завтр" in lowered:
        target = date.today() + timedelta(days=1)
        payload.update({"from": target.isoformat(), "to": target.isoformat()})
    elif "сегодн" in lowered:
        target = date.today()
        payload.update({"from": target.isoformat(), "to": target.isoformat()})
    return payload


def _clarification(capability: str, question: str, pending_context: dict[str, Any]) -> dict[str, Any]:
    result = {
        "status": "clarification_required",
        "intent": capability,
        "chat_response": question,
        "clarification": {"question": question, "pending_context": pending_context},
        "blocked_reasons": ["required_parameter_missing"],
        "external_writes_performed": False,
    }
    return standardize_operator_result(result, capability)


def _extract_service_price(message: str) -> tuple[str, Decimal | None]:
    clean = str(message or "").strip()
    price_match = re.search(r"(?:цен\w*[^\d]{0,20}|\sна\s)(\d+(?:[.,]\d{1,2})?)", clean, re.IGNORECASE)
    price: Decimal | None = None
    if price_match:
        try:
            price = Decimal(price_match.group(1).replace(",", "."))
        except InvalidOperation:
            price = None
    name_match = re.search(
        r"услуг(?:у|и|е)?\s+[«\"']?(.+?)[»\"']?\s+(?:на|до|=)\s*\d",
        clean,
        re.IGNORECASE,
    )
    if not name_match:
        name_match = re.search(r"услуг(?:у|и|е)?\s+[«\"']?(.+?)[»\"']?$", clean, re.IGNORECASE)
    service_name = str(name_match.group(1) if name_match else "").strip(" «»\"'")
    return service_name, price


def _is_service_price_intent(message: str) -> bool:
    lowered = str(message or "").lower()
    return "услуг" in lowered and "цен" in lowered and any(marker in lowered for marker in ("измени", "поменя", "установ", "постав"))


def _update_one_service_price(cursor: Any, *, business_id: str, message: str) -> tuple[dict[str, Any], dict[str, Any]]:
    service_name, price = _extract_service_price(message)
    pending = {"capability": "services.price.update", "original_message": message}
    if not service_name:
        return _clarification("services.price.update", "Какую именно услугу нужно изменить?", pending), pending
    if price is None or price < 0:
        pending["service_name"] = service_name
        return _clarification("services.price.update", f"Какую новую цену установить для услуги «{service_name}»?", pending), pending
    cursor.execute(
        """
        SELECT id, name, price FROM userservices
        WHERE business_id = %s AND COALESCE(is_active, TRUE) = TRUE AND name ILIKE %s
        ORDER BY CASE WHEN lower(name) = lower(%s) THEN 0 ELSE 1 END, name
        LIMIT 6
        """,
        (business_id, f"%{service_name}%", service_name),
    )
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    rows = []
    for raw in cursor.fetchall() or []:
        if isinstance(raw, dict):
            rows.append(dict(raw))
        else:
            rows.append({columns[index]: raw[index] for index in range(min(len(columns), len(raw)))})
    if not rows:
        pending["service_name"] = service_name
        return _clarification(
            "services.price.update",
            f"Не нашёл активную услугу «{service_name}». Уточните название как оно указано в LocalOS.",
            pending,
        ), pending
    exact = [item for item in rows if str(item.get("name") or "").lower() == service_name.lower()]
    if len(rows) > 1 and len(exact) != 1:
        choices = ", ".join(f"«{item.get('name')}»" for item in rows[:5])
        pending.update({"service_name": service_name, "price": str(price)})
        return _clarification("services.price.update", f"Нашёл несколько услуг: {choices}. Какую выбрать?", pending), pending
    selected = exact[0] if exact else rows[0]
    cursor.execute(
        """
        UPDATE userservices SET price = %s, updated_at = CURRENT_TIMESTAMP
        WHERE id = %s AND business_id = %s
        RETURNING id, name, price
        """,
        (price, selected.get("id"), business_id),
    )
    updated = cursor.fetchone()
    updated_row = dict(updated) if isinstance(updated, dict) else {
        "id": selected.get("id"), "name": selected.get("name"), "price": price
    }
    result = {
        "status": "completed",
        "intent": "services.price.update",
        "chat_response": f"Изменил цену услуги «{updated_row.get('name')}» на {price} ₽.",
        "service": updated_row,
        "external_writes_performed": False,
        "result_ref": _result_ref("services.price.update", updated_row.get("id")),
    }
    return standardize_operator_result(result, "services.price.update"), {}


def _is_content_plan_intent(message: str) -> bool:
    lowered = str(message or "").lower().replace("-", " ")
    return "контент план" in lowered and any(marker in lowered for marker in ("созд", "сдел", "состав", "подготов"))


def _content_plan_period(message: str) -> int:
    match = re.search(r"\b(14|30|60|90)\s*(?:дн|день|дней)", str(message or ""), re.IGNORECASE)
    return int(match.group(1)) if match else 30


def _create_content_plan(*, business_id: str, user_id: str, message: str) -> dict[str, Any]:
    from services.content_plan_service import create_generated_content_plan

    period_days = _content_plan_period(message)
    plan = create_generated_content_plan(
        user_id,
        business_id,
        scope_type="single_location",
        scope_target_id=business_id,
        period_days=period_days,
        density="standard",
        content_mix={},
    )
    plan_id = str(plan.get("id") or plan.get("plan", {}).get("id") or "")
    href = f"/dashboard/content?plan_id={plan_id}" if plan_id else "/dashboard/content"
    result = {
        "status": "completed",
        "intent": "content_plan.generate",
        "chat_response": f"Создал контент-план на {period_days} дней.",
        "content_plan": plan,
        "external_writes_performed": False,
        "result_ref": _result_ref("content_plan.generate", plan_id, href=href, label="Открыть контент-план"),
    }
    return standardize_operator_result(result, "content_plan.generate")


def _manual_result(capability: str) -> dict[str, Any]:
    spec = CAPABILITY_BY_NAME[capability]
    copy_by_status = {
        "request_only": "Для этого действия нужен контролируемый запрос и подтверждение. Откройте раздел, чтобы проверить параметры.",
        "manual": "Этот раздел пока управляется вручную. Откройте его — Оператор не будет имитировать выполнение.",
        "gap": "Эта возможность пока не подключена к Оператору.",
    }
    result = {
        "status": "approval_required" if spec.status == "approval_required" else "manual_handoff",
        "intent": capability,
        "chat_response": copy_by_status.get(spec.status, "Откройте раздел для продолжения."),
        "external_writes_performed": False,
        "result_ref": _result_ref(capability),
    }
    return standardize_operator_result(result, capability)


def _approval_preview(capability: str, message: str, envelope: dict[str, Any]) -> dict[str, Any]:
    spec = CAPABILITY_BY_NAME[capability]
    result = {
        "status": "approval_required",
        "intent": capability,
        "chat_response": f"Подготовил действие «{spec.title}». Проверьте его и подтвердите отдельно.",
        "approval": {
            "status": "pending",
            "capability": capability,
            "summary": message,
            "envelope": envelope,
        },
        "external_writes_performed": False,
        "result_ref": _result_ref(capability),
    }
    return standardize_operator_result(result, capability)


def _manual_capability(message: str) -> str | None:
    lowered = str(message or "").lower()
    for capability, markers in MANUAL_MATCHERS:
        if any(marker in lowered for marker in markers):
            return capability
    return None


def _attach_ai_router(result: dict[str, Any], ai_router: dict[str, Any]) -> dict[str, Any]:
    combined = dict(result)
    combined["ai_router"] = {
        "status": ai_router.get("status"),
        "intent": ai_router.get("normalized_intent"),
        "charged_credits": ai_router.get("charged_credits"),
        "credit_charged": ai_router.get("credit_charged"),
        "finalization_result": ai_router.get("finalization_result"),
    }
    return combined


def route_operator_message(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    message: Any,
    channel: str,
    limit: Any = 5,
    explicit_url: Any = None,
    pending_context: dict[str, Any] | None = None,
    action_payload: dict[str, Any] | None = None,
    refresh_handler: Callable[..., dict[str, Any]] | None = None,
    ai_router_handler: Callable[..., dict[str, Any]] | None = None,
    manual_review_handler: Callable[..., dict[str, Any]] | None = None,
    action_orchestrator: ActionOrchestrator | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    clean_message = str(message or "").strip()
    run_refresh = refresh_handler or refresh_reviews_from_operator
    run_ai_router = ai_router_handler or classify_operator_intent_with_ai
    run_manual_review = manual_review_handler or process_operator_chat_message
    pending = pending_context if isinstance(pending_context, dict) else {}
    if pending.get("capability") == "services.price.update":
        original = str(pending.get("original_message") or "").strip()
        service_name = str(pending.get("service_name") or "").strip()
        price = str(pending.get("price") or "").strip()
        if price and not re.search(r"\d", clean_message):
            return _update_one_service_price(
                cursor,
                business_id=business_id,
                message=f"Измени цену услуги {clean_message} на {price}",
            )
        if service_name and re.search(r"\d", clean_message):
            return _update_one_service_price(
                cursor,
                business_id=business_id,
                message=f"Измени цену услуги {service_name} на {clean_message}",
            )
        fragments = [original]
        if service_name and service_name.lower() not in clean_message.lower():
            fragments.append(f"услугу {service_name}")
        fragments.append(clean_message)
        if price and not re.search(r"\d", clean_message):
            fragments.append(f"на {price}")
        return _update_one_service_price(cursor, business_id=business_id, message=" ".join(fragments))

    if _is_service_price_intent(clean_message):
        return _update_one_service_price(cursor, business_id=business_id, message=clean_message)
    lowered_message = clean_message.lower()
    if "опублик" in lowered_message and any(marker in lowered_message for marker in ("отзыв", "яндекс", "картах", "карты")):
        return _manual_result("reviews.publish_external"), {}
    if "опублик" in lowered_message and any(marker in lowered_message for marker in ("новост", "пост", "канал", "соцсет")):
        return _manual_result("content.publish_external"), {}
    if _is_content_plan_intent(clean_message):
        return _create_content_plan(business_id=business_id, user_id=user_id, message=clean_message), {}
    if classify_operator_help_intent(clean_message):
        result = build_operator_help_response()
        result["chat_response"] = (
            "Я управляю LocalOS через единый набор безопасных возможностей. "
            "Уже выполняю работу с карточкой и отзывами, создаю новости, посты и контент-планы, "
            "оптимизирую услуги и меняю цену одной точно указанной услуги. "
            "Финансы, бронирования, партнёрства, сеть, агентов и настройки открываю в нужном разделе, "
            "если безопасный handler ещё не подключён. Внешние публикации и отправки не выполняю без отдельного подтверждения."
        )
        result["capability_catalog"] = operator_capability_catalog()
        return standardize_operator_result(result, "operator.help"), {}
    if classify_unanswered_reviews_status_intent(clean_message):
        return standardize_operator_result(
            get_unanswered_reviews_status(cursor, business_id=business_id, limit=limit),
            "reviews.read",
        ), {}
    if classify_bulk_review_reply_intent(clean_message):
        return standardize_operator_result(
            generate_review_reply_drafts_for_unanswered_reviews(cursor, business_id=business_id, user_id=user_id, limit=limit, channel=channel),
            "reviews.reply.draft",
        ), {}
    if classify_fresh_reviews_intent(clean_message):
        return standardize_operator_result(
            run_refresh(cursor, business_id=business_id, user_id=user_id, explicit_url=explicit_url, channel=channel),
            "maps.refresh",
        ), {}
    if classify_services_apply_intent(clean_message):
        payload = action_payload if isinstance(action_payload, dict) else {}
        return (
            _approval_preview(
                "services.apply",
                clean_message,
                {
                    "job_id": payload.get("job_id"),
                    "item_ids": payload.get("item_ids") or [],
                    "limit": limit,
                    "channel": channel,
                },
            ),
            {},
        )
    if classify_services_optimize_intent(clean_message):
        return standardize_operator_result(
            optimize_services_from_operator(cursor, business_id=business_id, user_id=user_id, limit=limit, channel=channel),
            "services.optimize",
        ), {}
    if classify_social_post_generate_intent(clean_message):
        return standardize_operator_result(
            generate_social_post_draft_from_operator(cursor, business_id=business_id, user_id=user_id, message=clean_message, channel=channel),
            "social_post.generate",
        ), {}
    if classify_news_generate_intent(clean_message):
        return standardize_operator_result(
            generate_news_draft_from_operator(cursor, business_id=business_id, user_id=user_id, message=clean_message, channel=channel),
            "news.generate",
        ), {}
    if any(marker in lowered_message for marker in ("запис", "бронир", "визит")) and any(
        marker in lowered_message for marker in ("покаж", "какие", "сколько", "есть")
    ):
        return _execute_registered_capability(
            capability="appointments.manage",
            business_id=business_id,
            user_id=user_id,
            channel=channel,
            message=clean_message,
            payload=_appointments_payload(clean_message, limit),
            orchestrator=action_orchestrator,
        ), {}
    manual_review_intent = classify_operator_chat_intent(clean_message)
    manual_review_result = run_manual_review(
        cursor,
        business_id=business_id,
        user_id=user_id,
        message=clean_message,
        channel=channel,
    )
    if manual_review_intent != "unsupported" or manual_review_result.get("status") != "unsupported":
        return standardize_operator_result(
            manual_review_result,
            "reviews.manual.add",
        ), {}
    manual_capability = _manual_capability(clean_message)
    if manual_capability:
        return _manual_result(manual_capability), {}

    if should_use_ai_intent_router(clean_message):
        ai_router = run_ai_router(
            cursor,
            business_id=business_id,
            user_id=user_id,
            message=clean_message,
            channel=channel,
        )
        if ai_router.get("status") != "completed":
            return standardize_operator_result(ai_router, "operator.help"), {}
        ai_intent = str(ai_router.get("normalized_intent") or "unknown")
        handlers: dict[str, tuple[str, Callable[[], dict[str, Any]]]] = {
            "card_refresh": ("maps.refresh", lambda: run_refresh(cursor, business_id=business_id, user_id=user_id, explicit_url=explicit_url, channel=channel)),
            "review_replies_generate": ("reviews.reply.draft", lambda: generate_review_reply_drafts_for_unanswered_reviews(cursor, business_id=business_id, user_id=user_id, limit=limit, channel=channel)),
            "services_optimize": ("services.optimize", lambda: optimize_services_from_operator(cursor, business_id=business_id, user_id=user_id, limit=limit, channel=channel)),
            "social_post_generate": ("social_post.generate", lambda: generate_social_post_draft_from_operator(cursor, business_id=business_id, user_id=user_id, message=clean_message, channel=channel)),
            "news_generate": ("news.generate", lambda: generate_news_draft_from_operator(cursor, business_id=business_id, user_id=user_id, message=clean_message, channel=channel)),
            "operator_help": ("operator.help", build_operator_help_response),
        }
        selected = handlers.get(ai_intent)
        if selected:
            capability, handler = selected
            return standardize_operator_result(_attach_ai_router(handler(), ai_router), capability), {}
        if ai_intent == "manual_review_add_and_reply":
            lowered = clean_message.lower()
            if "отзыв:" not in lowered and not ("добав" in lowered and "отзыв" in lowered and ":" in lowered):
                blocked = {
                    "status": "blocked",
                    "intent": "manual_review_add_and_reply",
                    "chat_response": "Пришлите явный текст отзыва после двоеточия, чтобы я не добавил неверные данные.",
                    "blocked_reasons": ["manual_review_text_not_explicit"],
                    "external_writes_performed": False,
                    "credit_charged": False,
                }
                return standardize_operator_result(_attach_ai_router(blocked, ai_router), "reviews.manual.add"), {}
            routed = run_manual_review(
                cursor,
                business_id=business_id,
                user_id=user_id,
                message="добавь отзыв и сгенерируй ответ: " + clean_message,
                channel=channel,
            )
            return standardize_operator_result(_attach_ai_router(routed, ai_router), "reviews.manual.add"), {}

    unsupported = {
        "status": "unsupported",
        "intent": "unknown",
        "chat_response": "Не понял задачу. Уточните, что нужно изменить или создать. Я не буду выполнять действие по догадке.",
        "blocked_reasons": ["unsupported_operator_chat_intent"],
        "external_writes_performed": False,
        "paid_actions_performed": False,
        "credit_charged": False,
        "manual_publication_only": True,
    }
    return standardize_operator_result(unsupported, "operator.help"), {}


def confirm_pending_operator_action(
    cursor: Any,
    *,
    action_id: str,
    business_id: str,
    user_id: str,
) -> tuple[dict[str, Any], bool]:
    action = get_operator_action(cursor, action_id=action_id, business_id=business_id, user_id=user_id)
    if not action:
        return {"status": "blocked", "chat_response": "Действие не найдено.", "blocked_reasons": ["action_not_found"]}, False
    if str(action.get("status") or "") == "completed":
        stored = action.get("result_json")
        if isinstance(stored, str):
            stored = json.loads(stored)
        return stored if isinstance(stored, dict) else {}, True
    capability = str(action.get("capability") or "")
    envelope = action.get("envelope_json")
    if isinstance(envelope, str):
        envelope = json.loads(envelope)
    envelope = envelope if isinstance(envelope, dict) else {}
    if capability != "services.apply":
        return {
            "status": "blocked",
            "capability": capability,
            "chat_response": "Для действия нет безопасного confirm handler.",
            "blocked_reasons": ["confirm_handler_unavailable"],
        }, False
    result = apply_service_optimization_suggestions(
        cursor,
        business_id=business_id,
        user_id=user_id,
        job_id=envelope.get("job_id"),
        item_ids=envelope.get("item_ids") or None,
        limit=envelope.get("limit") or 5,
        channel=str(envelope.get("channel") or "web"),
        explicit_confirmation=True,
    )
    result = standardize_operator_result(result, capability)
    finish_operator_action(cursor, action_id=action_id, result=result)
    return result, False
