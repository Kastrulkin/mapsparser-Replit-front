from __future__ import annotations

import re
import json
import hashlib
import os
import uuid
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any, Callable
from zoneinfo import ZoneInfo

from core.action_orchestrator import ActionOrchestrator
from services.agent_capability_handlers import CANONICAL_CAPABILITIES, build_capability_handlers, capability_runtime_contract
from services.operator_capabilities import (
    build_operator_help_response,
    classify_operator_help_intent,
    classify_unanswered_reviews_status_intent,
    get_unanswered_reviews_status,
)
from services.operator_fresh_reviews import classify_fresh_reviews_intent, refresh_reviews_from_operator
from services.operator_finance_ingest import (
    build_finance_sales_preview,
    finance_result_ref,
    finance_sales_ingest_tool_contract,
)
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
from services.operator_conversations import finish_operator_action, get_operator_action, reject_operator_action
from services.operator_content_history import list_operator_content_history
from services.operator_mobile_today import build_mobile_progress
from services.operator_mobile_modules import list_operator_mobile_module
from services.operator_query import execute_operator_query, operator_query_tool_contract
from services.operator_scope_summary import build_operator_scope_summary
from services.operator_tool_loop import run_operator_tool_loop
from services.operator_tool_billing import run_paid_operator_tool_loop


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
    OperatorCapability("operator.query", "Поиск по данным LocalOS", "available", "read_only", "none", "/dashboard/operator", ("Покажи услуги нужной категории", "Покажи последний отзыв", "Найди посты за период")),
    OperatorCapability("maps.status", "Состояние карточки", "available", "read_only", "none", "/dashboard/card", ("В каком состоянии карточка?",)),
    OperatorCapability("maps.refresh", "Обновление карточки и отзывов", "available", "paid_external", "credit_policy", "/dashboard/card", ("Обнови карточку", "Проверь новые отзывы")),
    OperatorCapability("reviews.read", "Отзывы без ответа", "available", "read_only", "none", "/dashboard/card?tab=reviews&review_filter=needs_reply", ("Есть отзывы без ответа?",)),
    OperatorCapability("reviews.reply.draft", "Черновики ответов", "draft_only", "paid_compute", "credit_policy", "/dashboard/card?tab=reviews&review_filter=needs_reply", ("Подготовь ответы на отзывы",)),
    OperatorCapability("reviews.manual.add", "Добавление отзыва и черновика ответа", "available", "write_internal", "explicit_command", "/dashboard/card?tab=reviews&review_filter=needs_reply", ("Добавь отзыв и подготовь ответ",)),
    OperatorCapability("news.generate", "Черновик новости", "draft_only", "paid_compute", "credit_policy", "/dashboard/content", ("Создай новость про акцию",)),
    OperatorCapability("social_post.generate", "Черновик поста", "draft_only", "paid_compute", "credit_policy", "/dashboard/content", ("Подготовь пост для соцсетей",)),
    OperatorCapability("content_plan.generate", "Контент-план", "available", "write_internal", "explicit_command", "/dashboard/content", ("Сделай контент-план на 30 дней",), "content_plan.item.create_draft"),
    OperatorCapability("content.create_plan", "Черновик контент-плана", "draft_only", "write_internal", "explicit_command", "/dashboard/content", ("Подготовь контент-план",), "content_plan.item.create_draft"),
    OperatorCapability("content.history", "История контента и черновиков", "available", "read_only", "none", "/dashboard/content", ("Покажи последние черновики",)),
    OperatorCapability("services.read", "Список услуг", "available", "read_only", "none", "/dashboard/card?tab=services", ("Выдай 3 верхние услуги", "Покажи первые 5 услуг")),
    OperatorCapability("services.prepare_updates", "Подготовка изменений услуг", "draft_only", "paid_compute", "credit_policy", "/dashboard/card?tab=services", ("Найди услуги без цен и подготовь исправления",)),
    OperatorCapability("services.optimize", "Оптимизация услуг", "draft_only", "paid_compute", "credit_policy", "/dashboard/card?tab=services", ("Оптимизируй услуги",)),
    OperatorCapability("services.apply_updates", "Применение изменений услуг", "approval_required", "bulk_write", "separate_confirmation", "/dashboard/card?tab=services", ("Примени подготовленные изменения услуг",)),
    OperatorCapability("services.apply", "Применение предложений по услугам", "approval_required", "bulk_write", "separate_confirmation", "/dashboard/card?tab=services", ("Примени предложения по услугам",)),
    OperatorCapability("services.price.update", "Изменение цены одной услуги", "available", "write_internal", "explicit_command", "/dashboard/card?tab=services", ("Измени цену услуги Маникюр на 1500",)),
    OperatorCapability("finance.manage", "Финансы и импорты", "request_only", "financial", "separate_confirmation", "/dashboard/finance", ("Добавь расход", "Покажи финансовый итог"), "finance.transaction.create"),
    OperatorCapability("finance.read", "Финансовая сводка", "available", "read_only", "none", "/dashboard/finance", ("Покажи выручку и расходы за 30 дней",)),
    OperatorCapability("finance.prepare_transaction", "Подготовка финансовой операции", "approval_required", "financial_write_request", "separate_confirmation", "/dashboard/finance", ("Добавь расход 5000 на рекламу",), "finance.transaction.apply_operator"),
    OperatorCapability("finance.sales_import", "Импорт списка продаж", "approval_required", "financial_write_request", "separate_confirmation", "/dashboard/finance", ("Добавь сегодняшние продажи из этого списка",), "finance.sales_import.apply_operator"),
    OperatorCapability("average_ticket.manage", "Средний чек и допродажи", "manual", "read_or_draft", "manual_handoff", "/dashboard/average-ticket", ("Как увеличить средний чек?",)),
    OperatorCapability("average_ticket.read", "Средний чек и допродажи", "available", "read_only", "none", "/dashboard/average-ticket", ("Что со средним чеком?",)),
    OperatorCapability("crm.stats", "Статистика CRM", "available", "read_only", "none", "/dashboard/progress", ("Покажи статистику записей и загрузки",)),
    OperatorCapability("appointments.read", "Записи клиентов", "available", "read_only", "none", "/dashboard/progress", ("Покажи записи на завтра",), "appointments.read"),
    OperatorCapability("communications.manage", "Чаты и сообщения", "request_only", "communication", "separate_confirmation", "/dashboard/chats", ("Подготовь сообщение клиентам",), "communications.draft"),
    OperatorCapability("communications.draft", "Черновик сообщения", "draft_only", "draft", "none", "/dashboard/chats", ("Подготовь текст напоминания",), "communications.draft"),
    OperatorCapability("communications.prepare_send", "Подготовка отправки", "approval_required", "external_send_request", "separate_confirmation", "/dashboard/chats", ("Подготовь отправку напоминания клиенту",), "communications.send_reminder"),
    OperatorCapability("partnerships.manage", "Партнёрства и outreach", "request_only", "external_send", "separate_confirmation", "/dashboard/partnerships", ("Найди партнёров рядом",), "partnership.draft_offer"),
    OperatorCapability("partnerships.read", "Партнёрские лиды", "available", "read_only", "none", "/dashboard/partnerships", ("Покажи партнёров в работе",)),
    OperatorCapability("partnerships.search", "Поиск партнёров в LocalOS", "available", "read_only", "none", "/dashboard/partnerships", ("Найди партнёров в нашем списке",)),
    OperatorCapability("partnerships.prepare_message", "Черновик партнёрского сообщения", "draft_only", "draft", "none", "/dashboard/partnerships", ("Подготовь сообщение партнёру",), "partnership.draft_offer"),
    OperatorCapability("network.manage", "Сеть и локации", "manual", "write_internal", "manual_handoff", "/dashboard/network", ("Покажи проблемные локации",)),
    OperatorCapability("network.read", "Состояние сети и локаций", "available", "read_only", "none", "/dashboard/network", ("Покажи проблемные локации",)),
    OperatorCapability("agents.manage", "ИИ-сотрудники", "manual", "privileged", "manual_handoff", "/dashboard/agents", ("Покажи моих ИИ-сотрудников",)),
    OperatorCapability("agents.read", "Состояние ИИ-сотрудников", "available", "read_only", "none", "/dashboard/agents", ("Какие ИИ-сотрудники активны?",)),
    OperatorCapability("settings.manage", "Настройки и подключения", "manual", "identity_access", "manual_handoff", "/dashboard/settings", ("Проверь подключения",)),
    OperatorCapability("settings.read", "Состояние подключений", "available", "read_only", "none", "/dashboard/settings", ("Какие подключения работают?",)),
    OperatorCapability("support.manage", "Поддержка и диагностика", "manual", "support_read", "manual_handoff", "/dashboard/settings/integrations", ("Почему не работает подключение?",)),
    OperatorCapability("support.read", "Диагностика LocalOS", "available", "support_read", "none", "/dashboard/settings/integrations", ("Что сейчас требует внимания?",)),
    OperatorCapability("reviews.publish_external", "Публикация ответов в карты", "gap", "write_external", "separate_confirmation", "/dashboard/card?tab=reviews", ("Опубликуй ответы в Яндекс",)),
    OperatorCapability("content.publish_external", "Автопубликация во внешние каналы", "gap", "write_external", "separate_confirmation", "/dashboard/content", ("Опубликуй новость во всех каналах",)),
)


CAPABILITY_BY_NAME = {item.name: item for item in CAPABILITIES}
OPERATOR_ACTION_ORCHESTRATOR = ActionOrchestrator(build_capability_handlers())


MANUAL_MATCHERS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("finance.manage", ("финанс", "расход", "доход", "выруч", "транзакц")),
    ("average_ticket.manage", ("средн", "допрод", "чек")),
    ("crm.stats", ("бронир", "запис", "визит", "неявк", "загрузк")),
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
    "выдай",
    "назови",
    "перечисл",
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


def _registered_capability_envelope(
    *,
    capability: str,
    business_id: str,
    user_id: str,
    channel: str,
    message: str,
    payload: dict[str, Any],
    backend_capability: str | None = None,
) -> dict[str, Any]:
    backend_name = str(backend_capability or CAPABILITY_BY_NAME[capability].backend_capability or capability)
    idempotency_source = f"{business_id}:{user_id}:{channel}:{backend_name}:{message.strip().lower()}"
    return {
        "tenant_id": business_id,
        "actor": {"id": user_id, "type": "user", "channel": channel},
        "trace_id": str(uuid.uuid4()),
        "idempotency_key": "operator:" + hashlib.sha256(idempotency_source.encode("utf-8")).hexdigest(),
        "capability": backend_name,
        "payload": payload,
        "approval": {"mode": "auto", "ttl_sec": 1800},
        "billing": {"tariff_id": "operator", "reserve_tokens": 1},
    }


def _execute_registered_capability(
    *,
    capability: str,
    business_id: str,
    user_id: str,
    channel: str,
    message: str,
    payload: dict[str, Any],
    backend_capability: str | None = None,
    orchestrator: ActionOrchestrator | None = None,
) -> dict[str, Any]:
    envelope = _registered_capability_envelope(
        capability=capability,
        business_id=business_id,
        user_id=user_id,
        channel=channel,
        message=message,
        payload=payload,
        backend_capability=backend_capability,
    )
    execution = (orchestrator or OPERATOR_ACTION_ORCHESTRATOR).execute(
        envelope,
        {"user_id": user_id, "is_superadmin": False},
    )
    if execution.get("success") and execution.get("status") == "pending_human":
        return standardize_operator_result(
            {
                "status": "approval_required",
                "chat_response": "Действие подготовлено в защищённом контуре LocalOS и ожидает подтверждения.",
                "action_id": execution.get("action_id"),
                "approval": execution.get("approval") or {},
                "external_writes_performed": False,
            },
            capability,
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


def _prepare_registered_capability_approval(
    *,
    capability: str,
    tool_name: str,
    business_id: str,
    user_id: str,
    channel: str,
    message: str,
    payload: dict[str, Any],
    backend_capability: str | None = None,
    orchestrator: ActionOrchestrator | None = None,
) -> dict[str, Any]:
    prepared = _execute_registered_capability(
        capability=capability,
        business_id=business_id,
        user_id=user_id,
        channel=channel,
        message=message,
        payload=payload,
        backend_capability=backend_capability,
        orchestrator=orchestrator,
    )
    if prepared.get("status") != "approval_required" or not prepared.get("action_id"):
        return prepared
    backend_name = str(backend_capability or CAPABILITY_BY_NAME[capability].backend_capability or capability)
    return {
        **prepared,
        "approval": {
            "status": "pending",
            "capability": tool_name,
            "summary": str(message or "").strip(),
            "envelope": {
                "tool": tool_name,
                "orchestrator_action_id": str(prepared.get("action_id") or ""),
                "backend_capability": backend_name,
            },
        },
    }


def _prepare_finance_sales_approval(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    channel: str,
    message: str,
    arguments: Any,
    orchestrator: ActionOrchestrator | None,
) -> dict[str, Any]:
    preview = build_finance_sales_preview(
        cursor,
        business_id=business_id,
        message=message,
        arguments=arguments,
    )
    if preview.get("status") != "ready":
        return preview
    prepared = _prepare_registered_capability_approval(
        capability="finance.sales_import",
        tool_name="finance.ingest_sales",
        business_id=business_id,
        user_id=user_id,
        channel=channel,
        message=message,
        payload={
            "rows": list(preview.get("rows") or []),
            "source": "operator_chat",
            "source_hash": preview.get("source_hash"),
            "import_batch_id": preview.get("import_batch_id"),
        },
        backend_capability="finance.sales_import.apply_operator",
        orchestrator=orchestrator,
    )
    finance_preview = {
        "rows": list(preview.get("rows") or []),
        "duplicate_count": int(preview.get("duplicate_count") or 0),
        "recognized_count": int(preview.get("recognized_count") or 0),
        "import_count": int(preview.get("import_count") or 0),
        "total_amount": preview.get("total_amount"),
    }
    if prepared.get("status") != "approval_required":
        return {
            **prepared,
            "finance_preview": finance_preview,
            "result_ref": finance_result_ref(),
            "external_writes_performed": False,
        }
    return {
        **prepared,
        "chat_response": preview.get("chat_response"),
        "finance_preview": finance_preview,
        "result_ref": finance_result_ref(),
        "external_writes_performed": False,
    }


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


def _is_services_read_intent(message: str) -> bool:
    lowered = str(message or "").lower()
    return "услуг" in lowered and any(
        marker in lowered for marker in ("выдай", "покаж", "назови", "перечисл", "какие", "каких")
    )


def _is_services_inventory_intent(message: str) -> bool:
    lowered = str(message or "").lower()
    return "услуг" in lowered and "сколько" in lowered


def _service_source_title(source: Any) -> str:
    normalized = str(source or "localos").strip().lower().replace("-", "_")
    titles = {
        "yandex": "Яндекс Карты",
        "yandex_maps": "Яндекс Карты",
        "yandex_business": "Яндекс Бизнес",
        "2gis": "2ГИС",
        "two_gis": "2ГИС",
        "google": "Google Maps",
        "google_maps": "Google Maps",
        "apple": "Apple Maps",
        "apple_maps": "Apple Maps",
        "localos": "LocalOS",
    }
    return titles.get(normalized, str(source or "LocalOS").strip())


def _read_services_inventory(cursor: Any, *, business_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT COALESCE(NULLIF(LOWER(TRIM(source)), ''), 'localos') AS source,
               COUNT(*) AS cnt
        FROM userservices
        WHERE business_id = %s AND COALESCE(is_active, TRUE) = TRUE
        GROUP BY COALESCE(NULLIF(LOWER(TRIM(source)), ''), 'localos')
        ORDER BY COUNT(*) DESC, source ASC
        """,
        (business_id,),
    )
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    source_counts = []
    for raw in cursor.fetchall() or []:
        row = dict(raw) if isinstance(raw, dict) else {
            columns[index]: raw[index] for index in range(min(len(columns), len(raw)))
        }
        count = int(row.get("cnt") or 0)
        if count <= 0:
            continue
        source = str(row.get("source") or "localos")
        source_counts.append({"source": source, "title": _service_source_title(source), "count": count})
    total_count = sum(item["count"] for item in source_counts)
    if source_counts:
        breakdown = ", ".join(f"{item['title']} — {item['count']}" for item in source_counts)
        chat_response = f"Активных записей услуг: {total_count}. По источникам: {breakdown}."
    else:
        chat_response = "В выбранном бизнесе пока нет активных услуг из LocalOS или подключённых карт."
    return standardize_operator_result(
        {
            "status": "completed",
            "intent": "services.inventory",
            "chat_response": chat_response,
            "count": total_count,
            "source_counts": source_counts,
            "external_writes_performed": False,
        },
        "services.read",
    )


def _read_business_profile(cursor: Any, *, business_id: str) -> dict[str, Any]:
    cursor.execute("SELECT * FROM businesses WHERE id = %s LIMIT 1", (business_id,))
    raw = cursor.fetchone()
    if isinstance(raw, dict):
        row = dict(raw)
    elif hasattr(raw, "keys"):
        row = {key: raw[key] for key in raw.keys()}
    else:
        columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
        row = {
            columns[index]: raw[index]
            for index in range(min(len(columns), len(raw or ())))
        }
    allowed = ("id", "name", "description", "address", "phone", "site", "industry", "categories")
    profile = {key: row.get(key) for key in allowed if row.get(key) not in (None, "")}
    return {
        "status": "completed" if profile else "not_found",
        "business": profile,
        "external_writes_performed": False,
    }


def _rows_from_cursor(cursor: Any) -> list[dict[str, Any]]:
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    rows = []
    for raw in cursor.fetchall() or []:
        if isinstance(raw, dict):
            rows.append(dict(raw))
        elif hasattr(raw, "keys"):
            rows.append({key: raw[key] for key in raw.keys()})
        else:
            rows.append({columns[index]: raw[index] for index in range(min(len(columns), len(raw)))})
    return rows


def _read_finance_summary(cursor: Any, *, business_id: str, days: Any) -> dict[str, Any]:
    clean_days = max(1, min(int(days or 30), 366))
    period_end = datetime.now(ZoneInfo("Europe/Moscow")).date()
    period_start = period_end - timedelta(days=clean_days - 1)
    cursor.execute(
        """
        SELECT COUNT(*) AS transactions_count,
               COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'income'), 0) AS income,
               COALESCE(SUM(amount) FILTER (WHERE transaction_type = 'expense'), 0) AS expense,
               COALESCE(AVG(amount) FILTER (WHERE transaction_type = 'income'), 0) AS average_ticket
        FROM financialtransactions
        WHERE business_id = %s
          AND transaction_date BETWEEN %s AND %s
        """,
        (business_id, period_start, period_end),
    )
    raw = cursor.fetchone()
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    row = dict(raw) if isinstance(raw, dict) else {
        columns[index]: raw[index] for index in range(min(len(columns), len(raw or ())))
    }
    income = Decimal(str(row.get("income") or 0))
    expense = Decimal(str(row.get("expense") or 0))
    average_ticket = Decimal(str(row.get("average_ticket") or 0))
    return {
        "status": "completed",
        "period_days": clean_days,
        "transactions_count": int(row.get("transactions_count") or 0),
        "income": income,
        "expense": expense,
        "balance": income - expense,
        "average_ticket": average_ticket,
        "period_start": period_start.isoformat(),
        "period_end": period_end.isoformat(),
        "external_writes_performed": False,
    }


def _read_partnership_leads(cursor: Any, *, business_id: str, limit: Any, query: Any = "") -> dict[str, Any]:
    clean_limit = max(1, min(int(limit or 10), 50))
    clean_query = str(query or "").strip()[:200]
    search_clause = ""
    params: list[Any] = [business_id]
    if clean_query:
        search_clause = "AND (name ILIKE %s OR city ILIKE %s OR category ILIKE %s)"
        pattern = f"%{clean_query}%"
        params.extend([pattern, pattern, pattern])
    params.append(clean_limit)
    cursor.execute(
        f"""
        SELECT id, name, city, category, status, selected_channel, rating, reviews_count, updated_at
        FROM prospectingleads
        WHERE business_id = %s
          AND COALESCE(intent, 'client_outreach') = 'partnership_outreach'
          {search_clause}
        ORDER BY updated_at DESC NULLS LAST
        LIMIT %s
        """,
        tuple(params),
    )
    leads = _rows_from_cursor(cursor)
    return {
        "status": "completed",
        "query": clean_query,
        "leads": leads,
        "count": len(leads),
        "external_writes_performed": False,
    }


def _read_agents(cursor: Any, *, business_id: str, limit: Any) -> dict[str, Any]:
    clean_limit = max(1, min(int(limit or 20), 50))
    cursor.execute(
        """
        SELECT id, name, description, category, status, updated_at
        FROM agent_blueprints
        WHERE business_id = %s AND status <> 'archived'
        ORDER BY updated_at DESC NULLS LAST
        LIMIT %s
        """,
        (business_id, clean_limit),
    )
    agents = _rows_from_cursor(cursor)
    return {"status": "completed", "agents": agents, "count": len(agents), "external_writes_performed": False}


def _read_scope_status(cursor: Any, *, business_id: str, user_id: str) -> dict[str, Any]:
    summary = build_operator_scope_summary(
        cursor,
        scope={"kind": "business", "id": business_id, "business_ids": [business_id]},
        user_id=user_id,
    )
    return {
        "status": "completed",
        "as_of": summary.get("as_of"),
        "freshness": summary.get("freshness"),
        "metrics": list(summary.get("metrics") or [])[:20],
        "attention_items": list(summary.get("attention_items") or [])[:10],
        "data_warnings": list(summary.get("data_warnings") or [])[:10],
        "external_writes_performed": False,
    }


def _read_progress_status(cursor: Any, *, business_id: str, user_id: str) -> dict[str, Any]:
    progress = build_mobile_progress(
        cursor,
        scope={"kind": "business", "id": business_id, "business_ids": [business_id]},
        user_id=user_id,
    )
    return {
        "status": str(progress.get("status") or "available"),
        "as_of": progress.get("as_of"),
        "summary": progress.get("summary"),
        "growth_loop": progress.get("growth_loop"),
        "data_health": progress.get("data_health"),
        "areas": list(progress.get("areas") or [])[:20],
        "network_summary": progress.get("network_summary"),
        "problem_locations": list(progress.get("problem_locations") or [])[:20],
        "location_breakdown": list(progress.get("location_breakdown") or [])[:20],
        "data_warnings": list(progress.get("data_warnings") or [])[:10],
        "external_writes_performed": False,
    }


def _read_connections(cursor: Any, *, business_id: str) -> dict[str, Any]:
    cursor.execute(
        """
        SELECT id, source, external_id, display_name, is_active,
               last_sync_at, last_error, updated_at
        FROM externalbusinessaccounts
        WHERE business_id = %s
        ORDER BY source, updated_at DESC NULLS LAST
        """,
        (business_id,),
    )
    accounts = _rows_from_cursor(cursor)
    normalized = []
    for account in accounts:
        normalized.append({
            "id": account.get("id"),
            "source": account.get("source"),
            "external_id": account.get("external_id"),
            "display_name": account.get("display_name"),
            "is_active": bool(account.get("is_active")),
            "last_sync_at": account.get("last_sync_at"),
            "last_error": str(account.get("last_error") or "")[:500],
            "updated_at": account.get("updated_at"),
        })
    active_count = sum(1 for account in normalized if account.get("is_active"))
    error_count = sum(1 for account in normalized if account.get("last_error"))
    return {
        "status": "completed",
        "accounts": normalized,
        "count": len(normalized),
        "active_count": active_count,
        "error_count": error_count,
        "external_writes_performed": False,
    }


def _read_mobile_module(cursor: Any, *, business_id: str, module: str) -> dict[str, Any]:
    result = list_operator_mobile_module(
        cursor,
        module=module,
        scope={"kind": "business", "id": business_id, "business_ids": [business_id]},
    )
    return {
        "status": str(result.get("status") or "read_only"),
        "module": module,
        "items": list(result.get("items") or [])[:100],
        "counts": result.get("counts") or {},
        "as_of": result.get("as_of"),
        "freshness": result.get("freshness") or {},
        "data_warnings": list(result.get("data_warnings") or [])[:20],
        "external_writes_performed": False,
    }


def _normalize_tool_contract(tool: dict[str, Any], *, business_id: str) -> dict[str, Any]:
    risk_class = str(tool.get("risk_class") or "read_only")
    default_timeout = 60 if risk_class in {"paid_compute", "paid_external_read"} else 30
    return {
        **tool,
        "input_schema": tool.get("input_schema") if isinstance(tool.get("input_schema"), dict) else {"type": "object", "properties": {}},
        "output_schema": tool.get("output_schema") if isinstance(tool.get("output_schema"), dict) else {
            "type": "object",
            "required": ["status"],
            "properties": {
                "status": {"type": "string"},
                "error_code": {"type": "string"},
                "blocked_reasons": {"type": "array", "items": {"type": "string"}},
            },
        },
        "scope": {"type": "business", "business_id": business_id},
        "required_permission": str(tool.get("required_permission") or "business.access"),
        "risk_class": risk_class,
        "timeout_seconds": int(tool.get("timeout_seconds") or default_timeout),
        "approval_required": bool(tool.get("approval_required")),
    }


def _operator_tool_catalog(
    cursor: Any,
    *,
    business_id: str,
    user_id: str,
    message: str,
    channel: str,
    limit: Any,
    refresh_handler: Callable[..., dict[str, Any]],
    action_orchestrator: ActionOrchestrator | None = None,
) -> list[dict[str, Any]]:
    query_tool = operator_query_tool_contract()
    query_tool["execute"] = lambda arguments: execute_operator_query(
        cursor,
        business_id=business_id,
        arguments=arguments,
    )
    tools = [
        query_tool,
        {
            "name": "business.get_profile",
            "capability": "operator.help",
            "title": "Профиль выбранного бизнеса",
            "description": "Читает основные сведения только о выбранном бизнесе LocalOS.",
            "input_schema": {"type": "object", "properties": {}},
            "risk_class": "read_only",
            "approval_required": False,
            "execute": lambda _arguments: _read_business_profile(cursor, business_id=business_id),
        },
        {
            "name": "services.inventory",
            "capability": "services.read",
            "title": "Количество услуг по источникам",
            "description": "Считает активные услуги выбранного бизнеса и группирует их по источникам карт.",
            "input_schema": {"type": "object", "properties": {}},
            "risk_class": "read_only",
            "approval_required": False,
            "execute": lambda _arguments: _read_services_inventory(cursor, business_id=business_id),
        },
        {
            "name": "services.list",
            "capability": "services.read",
            "title": "Список услуг",
            "description": "Возвращает активные услуги выбранного бизнеса.",
            "input_schema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
            },
            "risk_class": "read_only",
            "approval_required": False,
            "planner_visible": False,
            "execute": lambda arguments: _read_services(
                cursor,
                business_id=business_id,
                message=f"Покажи {arguments.get('limit') or limit or 5} услуг",
                fallback_limit=arguments.get("limit") or limit,
            ),
        },
        {
            "name": "reviews.list_unanswered",
            "capability": "reviews.read",
            "title": "Отзывы без ответа",
            "description": "Читает сохранённые отзывы без ответа только выбранного бизнеса.",
            "input_schema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
            },
            "risk_class": "read_only",
            "approval_required": False,
            "planner_visible": False,
            "execute": lambda arguments: get_unanswered_reviews_status(
                cursor,
                business_id=business_id,
                limit=arguments.get("limit") or limit,
            ),
        },
        {
            "name": "reviews.generate_reply_drafts",
            "capability": "reviews.reply.draft",
            "title": "Черновики ответов на отзывы",
            "description": "Создаёт внутренние черновики ответов выбранного бизнеса. Ничего не публикует во внешние карты.",
            "input_schema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
            },
            "risk_class": "paid_compute",
            "approval_required": False,
            "explicit_intent_markers": ("подготов", "созд", "сгенерир", "напиш", "ответ"),
            "execute": lambda arguments: generate_review_reply_drafts_for_unanswered_reviews(
                cursor,
                business_id=business_id,
                user_id=user_id,
                limit=arguments.get("limit") or limit,
                channel=channel,
            ),
        },
        {
            "name": "reviews.prepare_replies",
            "capability": "reviews.reply.draft",
            "title": "Черновики ответов на отзывы",
            "description": "Готовит внутренние черновики ответов. Во внешние карты ничего не публикует.",
            "input_schema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
            },
            "risk_class": "paid_compute",
            "approval_required": False,
            "explicit_intent_markers": ("подготов", "созд", "сгенерир", "напиш", "ответ"),
            "execute": lambda arguments: generate_review_reply_drafts_for_unanswered_reviews(
                cursor,
                business_id=business_id,
                user_id=user_id,
                limit=arguments.get("limit") or limit,
                channel=channel,
            ),
        },
        {
            "name": "content.generate_news_draft",
            "capability": "news.generate",
            "title": "Черновик новости",
            "description": "Создаёт внутренний черновик новости выбранного бизнеса без публикации.",
            "input_schema": {
                "type": "object",
                "properties": {"brief": {"type": "string", "maxLength": 2000}},
            },
            "risk_class": "paid_compute",
            "approval_required": False,
            "explicit_intent_markers": ("подготов", "созд", "сгенерир", "напиш", "новост"),
            "execute": lambda arguments: generate_news_draft_from_operator(
                cursor,
                business_id=business_id,
                user_id=user_id,
                message=str(arguments.get("brief") or message),
                channel=channel,
            ),
        },
        {
            "name": "content.create_news_draft",
            "capability": "news.generate",
            "title": "Черновик новости",
            "description": "Создаёт внутренний черновик новости без публикации.",
            "input_schema": {
                "type": "object",
                "properties": {"brief": {"type": "string", "maxLength": 2000}},
            },
            "risk_class": "paid_compute",
            "approval_required": False,
            "explicit_intent_markers": ("подготов", "созд", "сгенерир", "напиш", "новост"),
            "execute": lambda arguments: generate_news_draft_from_operator(
                cursor,
                business_id=business_id,
                user_id=user_id,
                message=str(arguments.get("brief") or message),
                channel=channel,
            ),
        },
        {
            "name": "content.generate_social_post_draft",
            "capability": "social_post.generate",
            "title": "Черновик поста",
            "description": "Создаёт внутренний черновик поста выбранного бизнеса без внешней отправки.",
            "input_schema": {
                "type": "object",
                "properties": {"brief": {"type": "string", "maxLength": 2000}},
            },
            "risk_class": "paid_compute",
            "approval_required": False,
            "explicit_intent_markers": ("подготов", "созд", "сгенерир", "напиш", "пост"),
            "execute": lambda arguments: generate_social_post_draft_from_operator(
                cursor,
                business_id=business_id,
                user_id=user_id,
                message=str(arguments.get("brief") or message),
                channel=channel,
            ),
        },
        {
            "name": "content.create_plan",
            "capability": "content.create_plan",
            "title": "Черновик контент-плана",
            "description": "Создаёт в LocalOS внутренний черновик плана. Ничего не публикует во внешние каналы.",
            "input_schema": {
                "type": "object",
                "properties": {"brief": {"type": "string", "maxLength": 2000}},
            },
            "risk_class": "write_internal_draft",
            "approval_required": False,
            "explicit_intent_markers": ("подготов", "созд", "сдел", "состав", "план"),
            "execute": lambda arguments: _create_content_plan(
                business_id=business_id,
                user_id=user_id,
                message=str(arguments.get("brief") or message),
            ),
        },
        {
            "name": "services.prepare_updates",
            "capability": "services.prepare_updates",
            "title": "Предпросмотр изменений услуг",
            "description": "Создаёт внутренний job с предложениями и возвращает preview. Ни одна услуга не изменяется до отдельного подтверждения.",
            "input_schema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
            },
            "risk_class": "paid_compute",
            "approval_required": False,
            "explicit_intent_markers": ("подготов", "исправ", "оптимиз", "улучш", "предлож"),
            "execute": lambda arguments: optimize_services_from_operator(
                cursor,
                business_id=business_id,
                user_id=user_id,
                limit=arguments.get("limit") or limit,
                channel=channel,
            ),
        },
        {
            "name": "services.optimize",
            "capability": "services.optimize",
            "title": "Предложения по улучшению услуг",
            "description": "Создаёт внутренние предложения по услугам выбранного бизнеса; изменения ещё не применяются.",
            "input_schema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 20}},
            },
            "risk_class": "paid_compute",
            "approval_required": False,
            "explicit_intent_markers": ("оптимиз", "улучш", "предлож"),
            "execute": lambda arguments: optimize_services_from_operator(
                cursor,
                business_id=business_id,
                user_id=user_id,
                limit=arguments.get("limit") or limit,
                channel=channel,
            ),
        },
        {
            "name": "maps.refresh",
            "capability": "maps.refresh",
            "title": "Обновление данных карт",
            "description": "Запускает платный сбор свежих данных карт выбранного бизнеса; внешние данные не изменяет.",
            "input_schema": {
                "type": "object",
                "properties": {"url": {"type": "string", "maxLength": 2000}},
            },
            "risk_class": "paid_external_read",
            "approval_required": False,
            "explicit_intent_markers": ("обнов", "свеж", "проверь", "собер", "синхрон"),
            "execute": lambda arguments: refresh_handler(
                cursor,
                business_id=business_id,
                user_id=user_id,
                explicit_url=arguments.get("url"),
                channel=channel,
            ),
        },
        {
            "name": "services.apply_updates",
            "capability": "services.apply_updates",
            "title": "Применение подготовленных изменений услуг",
            "description": "Подготавливает подтверждение для ранее созданного preview. Запись в LocalOS выполняется только после нажатия кнопки подтверждения.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "item_ids": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
            },
            "risk_class": "bulk_write",
            "approval_required": True,
            "explicit_intent_markers": ("примени", "подтверд", "внес", "измени"),
        },
        {
            "name": "services.apply",
            "capability": "services.apply",
            "title": "Применение предложений по услугам",
            "description": "Подготавливает применение уже созданных предложений. Выполнение возможно только после отдельного подтверждения пользователя.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "job_id": {"type": "string"},
                    "item_ids": {"type": "array", "items": {"type": "string"}},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 20},
                },
            },
            "risk_class": "bulk_write",
            "approval_required": True,
            "explicit_intent_markers": ("примени", "подтверд", "внес", "измени"),
        },
        {
            "name": "content.list_history",
            "capability": "content.history",
            "title": "История контента и черновиков",
            "description": "Читает последние черновики, ответы и предложения только выбранного бизнеса.",
            "input_schema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
            },
            "risk_class": "read_only",
            "approval_required": False,
            "execute": lambda arguments: list_operator_content_history(
                cursor,
                business_id=business_id,
                user_id=user_id,
                limit=arguments.get("limit") or limit,
            ),
        },
        {
            "name": "finance.get_summary",
            "capability": "finance.read",
            "title": "Финансовая сводка",
            "description": "Считает доходы, расходы и баланс выбранного бизнеса за указанный период.",
            "input_schema": {
                "type": "object",
                "properties": {"days": {"type": "integer", "minimum": 1, "maximum": 366}},
            },
            "risk_class": "financial_read",
            "approval_required": False,
            "execute": lambda arguments: _read_finance_summary(
                cursor,
                business_id=business_id,
                days=arguments.get("days") or 30,
            ),
        },
        {
            **finance_sales_ingest_tool_contract(),
            "prepare_approval": lambda arguments: _prepare_finance_sales_approval(
                cursor,
                business_id=business_id,
                user_id=user_id,
                channel=channel,
                message=message,
                arguments=arguments,
                orchestrator=action_orchestrator,
            ),
        },
        {
            "name": "finance.prepare_transaction",
            "capability": "finance.prepare_transaction",
            "title": "Подготовка финансовой операции",
            "description": "Готовит ровно одну финансовую операцию. Для списка продаж всегда используйте finance.ingest_sales. Запись не выполняется до отдельного подтверждения.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "amount": {"type": "number", "minimum": 0.01},
                    "transaction_type": {"type": "string", "enum": ["income", "expense"]},
                    "transaction_date": {"type": "string", "maxLength": 10},
                    "category": {"type": "string", "maxLength": 200},
                    "description": {"type": "string", "maxLength": 1000},
                },
                "required": ["amount", "transaction_type"],
            },
            "risk_class": "financial_write_request",
            "approval_required": True,
            "timeout_seconds": 30,
            "explicit_intent_markers": ("добав", "запиш", "созд", "внес", "расход", "доход"),
            "prepare_approval": lambda arguments: _prepare_registered_capability_approval(
                capability="finance.prepare_transaction",
                tool_name="finance.prepare_transaction",
                business_id=business_id,
                user_id=user_id,
                channel=channel,
                message=message,
                payload={"rows": [dict(arguments)], "source": "operator_chat"},
                orchestrator=action_orchestrator,
            ),
        },
        {
            "name": "appointments.list",
            "capability": "appointments.read",
            "title": "Записи клиентов",
            "description": "Читает записи только выбранного бизнеса с необязательными фильтрами даты и статуса.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "from": {"type": "string", "maxLength": 10},
                    "to": {"type": "string", "maxLength": 10},
                    "status": {"type": "string", "maxLength": 50},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
            },
            "risk_class": "read_only",
            "approval_required": False,
            "execute": lambda arguments: _execute_registered_capability(
                capability="appointments.read",
                business_id=business_id,
                user_id=user_id,
                channel=channel,
                message=message,
                payload=arguments,
            ),
        },
        {
            "name": "communications.draft",
            "capability": "communications.draft",
            "title": "Черновик сообщения клиентам",
            "description": "Готовит текст сообщения внутри LocalOS. Ничего не отправляет.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "maxLength": 3000},
                    "channel": {"type": "string", "maxLength": 30},
                    "audience": {"type": "string", "maxLength": 200},
                },
                "required": ["message"],
            },
            "risk_class": "draft_only",
            "approval_required": False,
            "explicit_intent_markers": ("подготов", "созд", "напиш", "чернов"),
            "execute": lambda arguments: _execute_registered_capability(
                capability="communications.draft",
                business_id=business_id,
                user_id=user_id,
                channel=channel,
                message=message,
                payload=arguments,
            ),
        },
        {
            "name": "communications.prepare_send",
            "capability": "communications.prepare_send",
            "title": "Подготовка отправки сообщения",
            "description": "Создаёт защищённый request на отправку. Внешняя отправка без явного подтверждения невозможна.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "maxLength": 3000},
                    "channel": {"type": "string", "maxLength": 30},
                    "audience": {"type": "string", "maxLength": 200},
                },
                "required": ["message"],
            },
            "risk_class": "external_send_request",
            "approval_required": True,
            "timeout_seconds": 30,
            "explicit_intent_markers": ("отправ", "разошл", "напомни клиент"),
            "prepare_approval": lambda arguments: _prepare_registered_capability_approval(
                capability="communications.prepare_send",
                tool_name="communications.prepare_send",
                business_id=business_id,
                user_id=user_id,
                channel=channel,
                message=message,
                payload=dict(arguments),
                orchestrator=action_orchestrator,
            ),
        },
        {
            "name": "partnerships.list_leads",
            "capability": "partnerships.read",
            "title": "Партнёрские лиды",
            "description": "Читает партнёрские лиды только выбранного бизнеса.",
            "input_schema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
            },
            "risk_class": "read_only",
            "approval_required": False,
            "execute": lambda arguments: _read_partnership_leads(
                cursor,
                business_id=business_id,
                limit=arguments.get("limit") or limit,
            ),
        },
        {
            "name": "partnerships.search",
            "capability": "partnerships.search",
            "title": "Поиск партнёров в LocalOS",
            "description": "Ищет по имени, городу или категории среди партнёрских лидов только выбранного бизнеса.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "maxLength": 200},
                    "limit": {"type": "integer", "minimum": 1, "maximum": 50},
                },
            },
            "risk_class": "read_only",
            "approval_required": False,
            "execute": lambda arguments: _read_partnership_leads(
                cursor,
                business_id=business_id,
                query=arguments.get("query"),
                limit=arguments.get("limit") or limit,
            ),
        },
        {
            "name": "partnerships.prepare_message",
            "capability": "partnerships.prepare_message",
            "title": "Черновик партнёрского сообщения",
            "description": "Готовит текст для партнёра. Ничего не отправляет.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "partner_name": {"type": "string", "maxLength": 300},
                    "business_name": {"type": "string", "maxLength": 300},
                    "channel": {"type": "string", "maxLength": 30},
                    "tone": {"type": "string", "maxLength": 50},
                    "draft_text": {"type": "string", "maxLength": 3000},
                },
                "required": ["partner_name"],
            },
            "risk_class": "draft_only",
            "approval_required": False,
            "explicit_intent_markers": ("подготов", "напиш", "чернов", "сообщен"),
            "execute": lambda arguments: _execute_registered_capability(
                capability="partnerships.prepare_message",
                business_id=business_id,
                user_id=user_id,
                channel=channel,
                message=message,
                payload={**arguments, "intent": "partnership_outreach"},
                orchestrator=action_orchestrator,
            ),
        },
        {
            "name": "agents.list",
            "capability": "agents.read",
            "title": "ИИ-сотрудники",
            "description": "Читает список и статус ИИ-сотрудников только выбранного бизнеса.",
            "input_schema": {
                "type": "object",
                "properties": {"limit": {"type": "integer", "minimum": 1, "maximum": 50}},
            },
            "risk_class": "privileged_read",
            "approval_required": False,
            "execute": lambda arguments: _read_agents(
                cursor,
                business_id=business_id,
                limit=arguments.get("limit") or limit,
            ),
        },
        {
            "name": "maps.get_status",
            "capability": "maps.status",
            "title": "Состояние карточки и сохранённых данных",
            "description": "Возвращает рейтинг, количество отзывов, свежесть данных и текущие предупреждения выбранного бизнеса без внешнего обновления.",
            "input_schema": {"type": "object", "properties": {}},
            "risk_class": "read_only",
            "approval_required": False,
            "execute": lambda _arguments: _read_scope_status(cursor, business_id=business_id, user_id=user_id),
        },
        {
            "name": "maps.get_latest_snapshot",
            "capability": "maps.status",
            "title": "Последний сохранённый снимок карточки",
            "description": "Читает последние сохранённые метрики, свежесть и предупреждения без запуска нового парсинга.",
            "input_schema": {"type": "object", "properties": {}},
            "risk_class": "read_only",
            "approval_required": False,
            "execute": lambda _arguments: _read_scope_status(cursor, business_id=business_id, user_id=user_id),
        },
        {
            "name": "cards.list",
            "capability": "maps.status",
            "title": "Карточки, парсинг и график обновлений",
            "description": "Читает сохранённые карточки, статус парсинга и расписание автообновлений выбранного бизнеса.",
            "input_schema": {"type": "object", "properties": {}},
            "risk_class": "read_only",
            "approval_required": False,
            "execute": lambda _arguments: _read_mobile_module(cursor, business_id=business_id, module="cards"),
        },
        {
            "name": "content.list_items",
            "capability": "content.history",
            "title": "Элементы контент-плана",
            "description": "Читает текущие темы, сроки, статусы и черновики контент-плана.",
            "input_schema": {"type": "object", "properties": {}},
            "risk_class": "read_only",
            "approval_required": False,
            "planner_visible": False,
            "execute": lambda _arguments: _read_mobile_module(cursor, business_id=business_id, module="content"),
        },
        {
            "name": "analytics.get_overview",
            "capability": "crm.stats",
            "title": "Аналитика бизнеса",
            "description": "Читает сохранённые метрики аналитики и данные об источниках.",
            "input_schema": {"type": "object", "properties": {}},
            "risk_class": "read_only",
            "approval_required": False,
            "execute": lambda _arguments: _read_mobile_module(cursor, business_id=business_id, module="analytics"),
        },
        {
            "name": "diagnostics.list_issues",
            "capability": "support.read",
            "title": "Ошибки и зависшие задачи",
            "description": "Читает ошибки, зависшие задачи и несвежие источники без повторного запуска.",
            "input_schema": {"type": "object", "properties": {}},
            "risk_class": "support_read",
            "approval_required": False,
            "execute": lambda _arguments: _read_mobile_module(cursor, business_id=business_id, module="diagnostics"),
        },
        {
            "name": "progress.get_summary",
            "capability": "crm.stats",
            "title": "Прогресс и CRM-показатели",
            "description": "Читает сохранённые показатели прогресса, загрузки и результаты выбранного бизнеса.",
            "input_schema": {"type": "object", "properties": {}},
            "risk_class": "read_only",
            "approval_required": False,
            "execute": lambda _arguments: _read_progress_status(cursor, business_id=business_id, user_id=user_id),
        },
        {
            "name": "average_ticket.get_overview",
            "capability": "average_ticket.read",
            "title": "Средний чек и допродажи",
            "description": "Читает доступные показатели среднего чека, допродаж и рекомендации из прогресса выбранного бизнеса.",
            "input_schema": {"type": "object", "properties": {}},
            "risk_class": "read_only",
            "approval_required": False,
            "execute": lambda _arguments: _read_progress_status(cursor, business_id=business_id, user_id=user_id),
        },
        {
            "name": "network.get_status",
            "capability": "network.read",
            "title": "Состояние сети и локаций",
            "description": "Читает сетевую сводку, проблемные точки и сравнение локаций в области выбранного бизнеса.",
            "input_schema": {"type": "object", "properties": {}},
            "risk_class": "read_only",
            "approval_required": False,
            "execute": lambda _arguments: _read_progress_status(cursor, business_id=business_id, user_id=user_id),
        },
        {
            "name": "settings.check_connections",
            "capability": "settings.read",
            "title": "Состояние внешних подключений",
            "description": "Проверяет активность, последнюю синхронизацию и ошибки подключений выбранного бизнеса. Секреты и токены не возвращаются.",
            "input_schema": {"type": "object", "properties": {}},
            "risk_class": "identity_read",
            "approval_required": False,
            "execute": lambda _arguments: _read_connections(cursor, business_id=business_id),
        },
        {
            "name": "support.get_attention",
            "capability": "support.read",
            "title": "Диагностика и внимание",
            "description": "Читает предупреждения, свежесть данных и задачи, требующие внимания в выбранном бизнесе.",
            "input_schema": {"type": "object", "properties": {}},
            "risk_class": "support_read",
            "approval_required": False,
            "execute": lambda _arguments: _read_scope_status(cursor, business_id=business_id, user_id=user_id),
        },
        {
            "name": "operator.get_capabilities",
            "capability": "operator.help",
            "title": "Возможности Оператора",
            "description": "Возвращает честный каталог доступных, ручных и пока недоступных действий.",
            "input_schema": {"type": "object", "properties": {}},
            "risk_class": "read_only",
            "approval_required": False,
            "execute": lambda _arguments: build_operator_help_response(),
        },
    ]
    return [_normalize_tool_contract(tool, business_id=business_id) for tool in tools]


def _operator_tool_loop_enabled() -> bool:
    return str(os.getenv("OPERATOR_TOOL_LOOP_ENABLED") or "").strip().lower() in {"1", "true", "yes", "on"}


def _requested_services_limit(message: str, fallback: Any = 5) -> int:
    number_match = re.search(r"\b(\d{1,2})\b", str(message or ""))
    if number_match:
        return max(1, min(int(number_match.group(1)), 20))
    word_limits = {
        "одну": 1,
        "две": 2,
        "три": 3,
        "четыре": 4,
        "пять": 5,
        "десять": 10,
    }
    lowered = str(message or "").lower()
    for word, value in word_limits.items():
        if re.search(rf"\b{word}\b", lowered):
            return value
    try:
        return max(1, min(int(fallback or 5), 20))
    except (TypeError, ValueError):
        return 5


def _read_services(cursor: Any, *, business_id: str, message: str, fallback_limit: Any) -> dict[str, Any]:
    requested_limit = _requested_services_limit(message, fallback_limit)
    cursor.execute(
        """
        SELECT id, category, name, price, description
        FROM userservices
        WHERE business_id = %s AND COALESCE(is_active, TRUE) = TRUE
        ORDER BY category NULLS LAST, name NULLS LAST, updated_at DESC NULLS LAST
        LIMIT %s
        """,
        (business_id, requested_limit),
    )
    columns = [item[0] for item in (getattr(cursor, "description", None) or [])]
    services: list[dict[str, Any]] = []
    for raw in cursor.fetchall() or []:
        row = dict(raw) if isinstance(raw, dict) else {
            columns[index]: raw[index] for index in range(min(len(columns), len(raw)))
        }
        services.append(
            {
                "id": str(row.get("id") or ""),
                "category": str(row.get("category") or "").strip(),
                "name": str(row.get("name") or "").strip(),
                "price": str(row.get("price") or "").strip(),
                "description": str(row.get("description") or "").strip(),
            }
        )
    cursor.execute("SELECT name FROM businesses WHERE id = %s LIMIT 1", (business_id,))
    business_row = cursor.fetchone()
    if isinstance(business_row, dict):
        business_label = str(business_row.get("name") or "").strip()
    elif isinstance(business_row, (tuple, list)) and business_row:
        business_label = str(business_row[0] or "").strip()
    else:
        business_label = ""
    account_context = f"аккаунте «{business_label}»" if business_label else "выбранном аккаунте"
    found_count = len(services)
    chat_response = (
        f"Показываю {found_count} первых услуг в {account_context} в текущем порядке списка."
        if services
        else f"В {account_context} нет активных услуг. Если услуги находятся в другом бизнесе, переключите аккаунт сверху и повторите команду."
    )
    return standardize_operator_result(
        {
            "status": "completed",
            "intent": "services.read",
            "chat_response": chat_response,
            "services": services,
            "count": found_count,
            "requested_limit": requested_limit,
            "business_label": business_label,
            "external_writes_performed": False,
            "result_ref": _result_ref("services.read", label="Открыть услуги"),
        },
        "services.read",
    )


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
    result = _approval_preview(
        "services.price.update",
        message,
        {
            "tool": "services.price.update",
            "service_id": str(selected.get("id") or ""),
            "service_name": str(selected.get("name") or service_name),
            "previous_price": selected.get("price"),
            "new_price": price,
        },
    )
    result["chat_response"] = (
        f"Подготовил изменение цены услуги «{selected.get('name')}»: "
        f"с {selected.get('price') or 0} ₽ на {price} ₽. Изменение ещё не применено."
    )
    result["preview"] = {
        "service_id": str(selected.get("id") or ""),
        "service_name": str(selected.get("name") or service_name),
        "previous_price": selected.get("price"),
        "new_price": price,
    }
    return result, {}


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
    capability_copy = {
        "crm.stats": "LocalOS не управляет записями. Статистика загружается из CRM и отображается в «Прогрессе» и «Финансах».",
    }
    copy_by_status = {
        "request_only": "Для этого действия нужен контролируемый запрос и подтверждение. Откройте раздел, чтобы проверить параметры.",
        "manual": "Этот раздел пока управляется вручную. Откройте его — Оператор не будет имитировать выполнение.",
        "gap": "Эта возможность пока не подключена к Оператору.",
    }
    result = {
        "status": "approval_required" if spec.status == "approval_required" else "manual_handoff",
        "intent": capability,
        "chat_response": capability_copy.get(capability) or copy_by_status.get(spec.status, "Откройте раздел для продолжения."),
        "external_writes_performed": False,
        "result_ref": _result_ref(capability, label="Открыть Прогресс" if capability == "crm.stats" else None),
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
    conversation_id: str = "",
    conversation_history: Any = None,
    actor_context: dict[str, Any] | None = None,
    pending_approvals: list[dict[str, Any]] | None = None,
    refresh_handler: Callable[..., dict[str, Any]] | None = None,
    ai_router_handler: Callable[..., dict[str, Any]] | None = None,
    tool_planner: Callable[[dict[str, Any]], dict[str, Any]] | None = None,
    manual_review_handler: Callable[..., dict[str, Any]] | None = None,
    action_orchestrator: ActionOrchestrator | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    clean_message = str(message or "").strip()
    tool_loop_active = _operator_tool_loop_enabled() or tool_planner is not None
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
    if _is_services_inventory_intent(clean_message) and not tool_loop_active:
        return _read_services_inventory(cursor, business_id=business_id), {}
    if _is_services_read_intent(clean_message) and not tool_loop_active:
        return _read_services(
            cursor,
            business_id=business_id,
            message=clean_message,
            fallback_limit=limit,
        ), {}
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
            "Статистику CRM показываю в «Прогрессе» и «Финансах». Партнёрства, сеть, агентов и настройки открываю в нужном разделе, "
            "если безопасный handler ещё не подключён. Внешние публикации и отправки не выполняю без отдельного подтверждения."
        )
        result["capability_catalog"] = operator_capability_catalog()
        return standardize_operator_result(result, "operator.help"), {}
    if classify_unanswered_reviews_status_intent(clean_message) and not tool_loop_active:
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
    if manual_capability and not tool_loop_active:
        return _manual_result(manual_capability), {}

    if tool_loop_active:
        tools = _operator_tool_catalog(
            cursor,
            business_id=business_id,
            user_id=user_id,
            message=clean_message,
            channel=channel,
            limit=limit,
            refresh_handler=run_refresh,
            action_orchestrator=action_orchestrator,
        )
        if tool_planner is None:
            tool_result = run_paid_operator_tool_loop(
                cursor,
                business_id=business_id,
                user_id=user_id,
                message=clean_message,
                conversation_id=conversation_id,
                conversation_history=conversation_history,
                actor_context=actor_context,
                pending_approvals=pending_approvals,
                tools=tools,
            )
        else:
            tool_result = run_operator_tool_loop(
                business_id=business_id,
                user_id=user_id,
                message=clean_message,
                conversation_id=conversation_id,
                conversation_history=conversation_history,
                actor_context=actor_context,
                pending_approvals=pending_approvals,
                tools=tools,
                planner=tool_planner,
            )
        capability = str(tool_result.get("capability") or "operator.help")
        return standardize_operator_result(tool_result, capability), {}

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
    action_orchestrator: ActionOrchestrator | None = None,
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
    orchestrator_action_id = str(envelope.get("orchestrator_action_id") or "").strip()
    if orchestrator_action_id:
        execution = (action_orchestrator or OPERATOR_ACTION_ORCHESTRATOR).resolve_human_decision(
            orchestrator_action_id,
            "approved",
            {"user_id": user_id, "is_superadmin": False},
            decision_reason="Confirmed in LocalOS Operator chat",
        )
        if not execution.get("success"):
            is_finance_action = capability in {"finance.prepare_transaction", "finance.sales_import"}
            return {
                "status": "blocked",
                "capability": capability,
                "chat_response": (
                    "Не удалось записать операции. Откройте раздел «Финансы» и продолжите импорт там."
                    if is_finance_action
                    else "Не удалось подтвердить действие в защищённом контуре LocalOS."
                ),
                "error_code": str(execution.get("error_code") or "orchestrator_confirmation_failed"),
                "blocked_reasons": ["orchestrator_confirmation_failed"],
                "result_ref": _result_ref(capability) if is_finance_action else None,
                "external_writes_performed": False,
            }, False
        backend_result = execution.get("result") if isinstance(execution.get("result"), dict) else {}
        backend_chat_response = str(backend_result.get("chat_response") or "").strip()
        if backend_chat_response:
            confirmation_message = backend_chat_response
        elif backend_result.get("manual_apply_required") or backend_result.get("apply_state") == "not_applied":
            confirmation_message = (
                "Подтверждение принято. LocalOS подготовил проверенный запрос, но запись ещё не применена. "
                "Для этой capability пока нужен отдельный apply-handler."
            )
        elif backend_result.get("delivery_state") == "not_dispatched":
            confirmation_message = (
                "Запрос на отправку подтверждён и сохранён в LocalOS. "
                "Внешняя отправка не выполнялась."
            )
        else:
            confirmation_message = "Действие подтверждено и обработано защищённым контуром LocalOS."
        result = standardize_operator_result(
            {
                **backend_result,
                "status": "completed",
                "chat_response": confirmation_message,
                "orchestrator_action_id": orchestrator_action_id,
                "orchestrator_status": execution.get("status"),
                "external_writes_performed": bool(
                    backend_result.get("provider_write_performed")
                    or backend_result.get("external_dispatch_performed")
                ),
            },
            capability,
        )
        finish_operator_action(cursor, action_id=action_id, result=result)
        return result, False
    if capability == "services.price.update":
        service_id = str(envelope.get("service_id") or "").strip()
        service_name = str(envelope.get("service_name") or "").strip()
        try:
            new_price = Decimal(str(envelope.get("new_price")))
            previous_price = Decimal(str(envelope.get("previous_price") or 0))
        except (InvalidOperation, TypeError, ValueError):
            return {
                "status": "blocked",
                "capability": capability,
                "chat_response": "Не удалось проверить цену из preview. Подготовьте изменение заново.",
                "blocked_reasons": ["invalid_service_price_preview"],
            }, False
        if not service_id or new_price < 0:
            return {
                "status": "blocked",
                "capability": capability,
                "chat_response": "Preview изменения цены неполон. Подготовьте его заново.",
                "blocked_reasons": ["invalid_service_price_preview"],
            }, False
        cursor.execute(
            """
            UPDATE userservices
            SET price = %s, updated_at = CURRENT_TIMESTAMP
            WHERE id = %s AND business_id = %s
              AND COALESCE(is_active, TRUE) = TRUE
              AND COALESCE(price, 0) = %s
            RETURNING id, name, price
            """,
            (new_price, service_id, business_id, previous_price),
        )
        updated = cursor.fetchone()
        if not updated:
            return {
                "status": "blocked",
                "capability": capability,
                "chat_response": "Цена или состояние услуги изменились после preview. Ничего не применено; подготовьте изменение заново.",
                "blocked_reasons": ["stale_service_price_preview"],
                "external_writes_performed": False,
            }, False
        updated_row = dict(updated) if isinstance(updated, dict) else {
            "id": service_id,
            "name": service_name,
            "price": new_price,
        }
        result = standardize_operator_result(
            {
                "status": "completed",
                "intent": capability,
                "chat_response": f"Изменил цену услуги «{updated_row.get('name') or service_name}» на {new_price} ₽.",
                "service": updated_row,
                "external_writes_performed": False,
                "result_ref": _result_ref(capability, service_id),
            },
            capability,
        )
        finish_operator_action(cursor, action_id=action_id, result=result)
        return result, False
    if capability not in {"services.apply", "services.apply_updates"}:
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


def reject_pending_operator_action(
    cursor: Any,
    *,
    action_id: str,
    business_id: str,
    user_id: str,
    action_orchestrator: ActionOrchestrator | None = None,
) -> tuple[dict[str, Any], bool]:
    action = get_operator_action(cursor, action_id=action_id, business_id=business_id, user_id=user_id)
    if not action:
        return {"status": "blocked", "chat_response": "Действие не найдено.", "blocked_reasons": ["action_not_found"]}, False
    if str(action.get("status") or "") == "rejected":
        stored = action.get("result_json")
        if isinstance(stored, str):
            stored = json.loads(stored)
        return stored if isinstance(stored, dict) else {}, True
    if str(action.get("status") or "") == "completed":
        return {
            "status": "blocked",
            "chat_response": "Действие уже выполнено, его нельзя отклонить задним числом.",
            "blocked_reasons": ["action_already_completed"],
        }, False
    capability = str(action.get("capability") or "operator.help")
    envelope = action.get("envelope_json")
    if isinstance(envelope, str):
        envelope = json.loads(envelope)
    envelope = envelope if isinstance(envelope, dict) else {}
    orchestrator_action_id = str(envelope.get("orchestrator_action_id") or "").strip()
    if orchestrator_action_id:
        execution = (action_orchestrator or OPERATOR_ACTION_ORCHESTRATOR).resolve_human_decision(
            orchestrator_action_id,
            "rejected",
            {"user_id": user_id, "is_superadmin": False},
            decision_reason="Rejected in LocalOS Operator chat",
        )
        if not execution.get("success"):
            return {
                "status": "blocked",
                "capability": capability,
                "chat_response": "Не удалось отклонить действие в защищённом контуре LocalOS.",
                "blocked_reasons": ["orchestrator_rejection_failed"],
            }, False
    result = standardize_operator_result(
        {
            "status": "rejected",
            "chat_response": "Действие отклонено. Изменения и внешние отправки не выполнялись.",
            "orchestrator_action_id": orchestrator_action_id or None,
            "external_writes_performed": False,
        },
        capability,
    )
    reject_operator_action(cursor, action_id=action_id, result=result)
    return result, False
