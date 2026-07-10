from __future__ import annotations

import re
from datetime import date
from typing import Any, Dict, List

from services.agent_blueprint_runner import default_supervised_outreach_version_payload
from services.agent_compiled_artifact import build_compiled_artifact_candidate
from services.agent_compiler_llm import infer_agent_workflow_intent
from services.agent_openclaw_workflow_refs import annotate_steps_with_openclaw_action_refs
from services.communication_agent_templates import (
    get_communication_agent_template,
    infer_communication_agent_template_key,
    list_communication_agent_templates,
)


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _contains_any(text: str, words: List[str]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def _extract_requested_date(description: str) -> str:
    iso_match = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", description)
    if iso_match:
        try:
            return date(int(iso_match.group(1)), int(iso_match.group(2)), int(iso_match.group(3))).isoformat()
        except ValueError:
            return ""
    months = {
        "январ": 1,
        "феврал": 2,
        "март": 3,
        "апрел": 4,
        "ма": 5,
        "июн": 6,
        "июл": 7,
        "август": 8,
        "сентябр": 9,
        "октябр": 10,
        "ноябр": 11,
        "декабр": 12,
    }
    match = re.search(r"\b(\d{1,2})\s+([а-яё]+)\s+(20\d{2})", description.lower())
    if not match:
        return ""
    month_text = match.group(2)
    month = next((number for prefix, number in months.items() if month_text.startswith(prefix)), 0)
    if not month:
        return ""
    try:
        return date(int(match.group(3)), month, int(match.group(1))).isoformat()
    except ValueError:
        return ""


def infer_blueprint_category(description: str) -> str:
    text = description.lower()
    if _is_uploaded_document_request(text):
        return "documents"
    if _is_local_table_request(text):
        return "tables"
    if _infer_integration_intent(text):
        return "custom"
    if _is_browser_monitoring_request(text):
        return "custom"
    if _is_inventory_control_request(text):
        return "custom"
    if _is_staff_schedule_request(text):
        return "custom"
    if _is_cancellation_reasons_request(text):
        return "custom"
    if _is_admin_response_control_request(text):
        return "custom"
    if _is_faq_from_chats_request(text):
        return "custom"
    if _is_new_employee_check_request(text):
        return "custom"
    if _is_seasonal_services_request(text):
        return "services"
    if _is_revenue_anomaly_request(text):
        return "custom"
    if _is_map_questions_request(text):
        return "custom"
    if _is_location_description_quality_request(text):
        return "custom"
    if _is_competitor_price_request(text):
        return "custom"
    if _is_photo_quality_request(text):
        return "custom"
    if _is_new_service_control_request(text):
        return "services"
    if _is_customer_questions_request(text):
        return "custom"
    if _is_team_tasks_request(text):
        return "custom"
    if _is_no_discount_promo_request(text):
        return "custom"
    if _is_repeated_complaints_request(text):
        return "custom"
    if _is_review_location_analysis_request(text):
        return "reviews"
    if _is_manager_report_request(text):
        return "custom"
    if _is_holiday_readiness_request(text):
        return "custom"
    if _is_problem_digest_request(text):
        return "custom"
    if _is_client_reactivation_request(text):
        return "communications"
    if _is_customer_data_quality_request(text):
        return "custom"
    if _is_localos_finance_monitoring_request(text):
        return "custom"
    if _is_review_based_content_request(text):
        return "custom"
    if _contains_any(text, ["контент-план", "темы постов", "тема пост", "постов для карточ", "посты для карточ"]):
        return "custom"
    if _contains_any(text, ["партн", "коллаб"]):
        return "partnerships"
    if _contains_any(
        text,
        [
            "напом",
            "запис",
            "appointment",
            "reminder",
            "клиентам о записи",
            "пакет",
            "после визита",
            "после посещения",
            "давно не был",
            "давно не были",
            "возврат клиента",
            "вернуть клиента",
            "входящий запрос",
            "входящее сообщение",
        ],
    ):
        return "communications"
    if _contains_any(text, ["документ", "договор", "pdf", "docx", "акт"]):
        return "documents"
    if _is_email_authoring_request(text):
        return "email"
    if _contains_any(text, ["отзыв", "review"]):
        return "reviews"
    if _contains_any(text, ["услуг", "сервис", "пустые описан", "названия", "отсутствующие цены"]):
        return "services"
    if _contains_any(text, ["лид", "lead", "shortlist", "найди клиентов", "поиск клиентов", "outreach"]):
        return "outreach"
    return "custom"


def build_agent_blueprint_draft(
    description: str,
    preferred_category: str = "",
    *,
    use_ai: bool = False,
    business_id: str = "",
    user_id: str = "",
    planner_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return compile_agent_blueprint(
        description,
        preferred_category,
        use_ai=use_ai,
        business_id=business_id,
        user_id=user_id,
        planner_context=planner_context,
    )


def build_communication_agent_showcase_blueprints() -> List[Dict[str, Any]]:
    return [_communications_compilation(str(template["goal"] or ""), str(template["key"] or "")) for template in list_communication_agent_templates()]


def compile_agent_blueprint(
    description: str,
    preferred_category: str = "",
    *,
    use_ai: bool = False,
    business_id: str = "",
    user_id: str = "",
    planner_context: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    request_text = _normalized_text(description)
    category = _normalized_category(preferred_category) or infer_blueprint_category(request_text)
    if category == "communications":
        return _communications_compilation(request_text)
    ai_result = {}
    content_analytics_request = _is_telegram_content_analytics_request(request_text)
    rich_localos_workflow_request = _is_rich_localos_workflow_request(request_text)
    browser_monitoring_request = _is_browser_monitoring_request(request_text)
    if use_ai and not content_analytics_request and not rich_localos_workflow_request and not browser_monitoring_request:
        ai_result = infer_agent_workflow_intent(
            request_text,
            business_id=business_id,
            user_id=user_id,
            planner_context=planner_context,
        )
        ai_intent = _intent_from_llm_result(ai_result)
        if ai_intent and _intent_is_supported_by_text(request_text, ai_intent):
            draft = _source_destination_compilation(request_text, ai_intent)
            metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
            metadata["compiler_source"] = "gigachat_intent_extractor"
            metadata["llm_intent"] = {
                "status": ai_result.get("status"),
                "source": ai_result.get("source"),
                "intent": (ai_result.get("intent") if isinstance(ai_result.get("intent"), dict) else {}),
            }
            draft["metadata"] = metadata
            return draft
    integration_intent = {} if content_analytics_request or rich_localos_workflow_request or browser_monitoring_request else _infer_integration_intent(request_text)
    if integration_intent:
        draft = _source_destination_compilation(request_text, integration_intent)
        if ai_result:
            metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
            metadata["compiler_source"] = "deterministic_fallback"
            metadata["llm_intent"] = {
                "status": ai_result.get("status"),
                "source": ai_result.get("source"),
                "error": ai_result.get("error"),
            }
            draft["metadata"] = metadata
        return draft
    if category == "outreach":
        version_payload = default_supervised_outreach_version_payload()
        version_payload["goal"] = request_text or version_payload["goal"]
        metadata = _metadata(request_text, category, ["prospectingleads", "business_profile"])
        _attach_compiled_metadata(metadata, version_payload, "compiled_outreach_workflow_v1", "shortlist")
        return {
            "name": _draft_name(request_text, "Агент поиска клиентов"),
            "category": category,
            "description": request_text,
            "metadata": metadata,
            "version_payload": version_payload,
            "summary": _summary(category, ["prospectingleads", "business_profile"], version_payload["steps"]),
        }

    sources = _sources_for_request(category, request_text)
    required_bindings = _generic_required_integration_bindings(sources)
    version_payload = {
        "goal": request_text,
        "inputs_schema": {
            "type": "object",
            "properties": {
                "request": {"type": "string"},
                "files": {"type": "array"},
                "source_ids": {"type": "array"},
            },
        },
        "steps": _generic_steps(category, request_text, sources),
        "capability_allowlist": [],
        "approval_policy": {
            "required_for": ["final_output", "external_delivery"],
            "external_delivery": "manual_approval_required",
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "result": {"type": "object"},
                "artifacts": {"type": "array"},
                "approval_required": {"type": "boolean"},
            },
        },
    }
    if required_bindings:
        version_payload["required_integration_bindings"] = required_bindings
        version_payload["capability_allowlist"] = [
            str(binding.get("capability") or "")
            for binding in required_bindings
            if str(binding.get("capability") or "").strip()
        ]
    metadata = _metadata(request_text, category, sources)
    if required_bindings:
        metadata["required_integration_bindings"] = required_bindings
    _attach_compiled_metadata(metadata, version_payload, f"compiled_{category}_workflow_v1", "final_output")
    return {
        "name": _draft_name(request_text, _default_name_for_category(category)),
        "category": category,
        "description": request_text,
        "metadata": metadata,
        "version_payload": version_payload,
        "summary": _summary(category, sources, version_payload["steps"]),
    }


def _draft_name(description: str, fallback: str) -> str:
    cleaned = " ".join(description.split())
    if not cleaned:
        return fallback
    if len(cleaned) <= 80:
        return cleaned
    return cleaned[:77].rstrip() + "..."


def _normalized_category(value: str) -> str:
    category = _normalized_text(value).lower()
    allowed = {"communications", "documents", "email", "tables", "outreach", "reviews", "partnerships", "booking", "services", "custom"}
    aliases = {
        "communication": "communications",
        "chat": "communications",
        "reminders": "communications",
        "reminder": "communications",
        "document": "documents",
        "docs": "documents",
        "letters": "email",
        "mail": "email",
        "spreadsheet": "tables",
        "spreadsheets": "tables",
        "leads": "outreach",
        "clients": "outreach",
        "partnership": "partnerships",
        "booking_agent": "booking",
        "services_optimize": "services",
    }
    category = aliases.get(category, category)
    return category if category in allowed else ""


def _default_name_for_category(category: str) -> str:
    names = {
        "communications": "Агент коммуникаций",
        "documents": "Агент обработки документов",
        "email": "Агент подготовки писем",
        "tables": "Агент обработки таблиц",
        "reviews": "Агент ответов на отзывы",
        "partnerships": "Агент партнёрств",
        "booking": "Агент бронирования",
        "services": "Агент оптимизации услуг",
    }
    return names.get(category, "Кастомный агент")


def _sources_for_category(category: str) -> List[str]:
    if category == "communications":
        return ["appointments", "services", "packages", "business_profile"]
    if category == "documents":
        return ["uploaded_documents", "business_profile"]
    if category == "email":
        return ["business_profile", "uploaded_documents", "manual_context"]
    if category == "tables":
        return ["uploaded_tables", "manual_context"]
    if category == "reviews":
        return ["external_reviews", "business_profile", "services"]
    if category == "partnerships":
        return ["prospectingleads", "services", "business_profile"]
    if category == "booking":
        return ["business_profile", "services", "manual_context"]
    if category == "services":
        return ["services", "business_profile", "reviews"]
    return ["manual_context", "business_profile"]


def _sources_for_request(category: str, request_text: str) -> List[str]:
    sources = _sources_for_category(category)
    lowered = request_text.lower()
    if category == "documents" and _is_uploaded_document_request(lowered):
        return ["uploaded_documents", "business_profile"]
    if _is_local_table_request(lowered):
        return ["uploaded_tables", "manual_context"]
    if _is_browser_monitoring_request(lowered):
        result = ["browser_use", "competitor_websites", "business_profile"]
        if _contains_any(lowered, ["цен", "прайс", "стоимост", "меню", "товар", "услуг"]):
            result.append("services")
        if _contains_any(lowered, ["telegram", "телеграм", "присыла", "отправ", "шл", "уведом", "сообщ"]):
            result.append("telegram")
        if _contains_any(lowered, ["whatsapp", "ватсап", "вацап"]):
            result.append("whatsapp")
        return result
    if _is_inventory_control_request(lowered):
        return ["inventory", "products", "supplies", "business_profile"]
    if _is_staff_schedule_request(lowered):
        return ["staff_schedule", "team", "business_profile"]
    if _is_cancellation_reasons_request(lowered):
        return ["appointments", "clients", "business_profile"]
    if _is_admin_response_control_request(lowered):
        return ["customer_chats", "team", "business_profile"]
    if _is_faq_from_chats_request(lowered):
        return ["customer_chats", "customer_questions", "business_cards", "business_profile"]
    if _is_new_employee_check_request(lowered):
        return ["team", "staff_profiles", "services", "schedule", "locations", "business_profile"]
    if _is_seasonal_services_request(lowered):
        return ["services", "seasonality", "business_cards", "price_list", "business_profile"]
    if _is_revenue_anomaly_request(lowered):
        result = ["localos_finance", "revenue", "business_profile"]
        if _contains_any(lowered, ["telegram", "телеграм", "присыла", "отправ", "шл", "уведом"]):
            result.append("telegram")
        return result
    if _is_map_questions_request(lowered):
        return ["business_cards", "map_questions", "business_profile"]
    if _is_location_description_quality_request(lowered):
        return ["locations", "business_cards", "location_descriptions", "business_profile"]
    if _is_photo_quality_request(lowered):
        return ["business_cards", "photos", "locations", "business_profile"]
    if _is_competitor_price_request(lowered):
        return ["services", "competitors", "business_profile"]
    if _is_problem_digest_request(lowered):
        result = ["localos_digest", "business_profile"]
        if _contains_any(lowered, ["telegram", "телеграм", "присыла", "отправ", "шл", "уведом"]):
            result.append("telegram")
        return result
    if _is_cancellation_risk_request(lowered):
        return ["appointments", "clients", "business_profile"]
    if _is_new_service_control_request(lowered):
        return ["services", "business_profile"]
    if _is_customer_questions_request(lowered):
        return ["telegram", "whatsapp", "customer_questions", "business_profile"]
    if _is_team_tasks_request(lowered):
        return ["localos_tasks", "team", "business_profile"]
    if _is_no_discount_promo_request(lowered):
        return ["services", "external_reviews", "seasonality", "business_profile"]
    if _is_repeated_complaints_request(lowered):
        return ["external_reviews", "customer_messages", "services", "business_profile"]
    if _is_review_location_analysis_request(lowered):
        return ["external_reviews", "locations", "business_profile"]
    if _is_manager_report_request(lowered):
        return ["external_reviews", "appointments", "localos_finance", "locations", "business_profile"]
    if _is_holiday_readiness_request(lowered):
        return ["business_cards", "services", "posts", "schedule", "business_profile"]
    if _is_customer_data_quality_request(lowered):
        return ["clients", "business_profile"]
    if _is_localos_finance_monitoring_request(lowered):
        result = ["localos_finance", "business_profile"]
        if _contains_any(lowered, ["telegram", "телеграм", "присыла", "отправ", "шл", "уведом"]):
            result.append("telegram")
        return result
    if _is_partner_replies_request(lowered):
        return ["prospectingleads", "outreach_drafts", "business_profile"]
    if _is_review_based_content_request(lowered):
        return ["external_reviews", "services", "business_profile", "manual_context"]
    if category == "custom" and _is_telegram_content_analytics_request(request_text):
        return ["telegram", "business_profile", "services", "external_reviews", "manual_context"]
    if category == "custom" and _contains_any(lowered, ["контент-план", "темы постов", "темы публикац", "постов для карточ", "карточек на картах", "новости в карточ", "календарь публикац"]):
        return ["services", "external_reviews", "business_profile", "manual_context"]
    if category == "custom" and _contains_any(lowered, ["еженедельный отч", "отчёт владельцу", "отчет владельцу", "каждую пятниц"]):
        return ["external_reviews", "localos_finance", "appointments", "services", "business_profile"]
    return sources


def _is_telegram_content_analytics_request(text: str) -> bool:
    lowered = text.lower()
    if not _contains_any(lowered, ["telegram", "телеграм"]):
        return False
    if not _contains_any(lowered, ["реакц", "комментар", "через api"]):
        return False
    return _contains_any(lowered, ["контент-план", "собирай вывод", "что изменить", "изменения"])


def _is_uploaded_document_request(text: str) -> bool:
    if _contains_any(text, ["таблиц", "xlsx", "excel", "csv"]):
        return False
    if not _contains_any(text, ["загруж", "файл", "pdf", "docx", "документ", "договор", "акт"]):
        return False
    return _contains_any(text, ["извлек", "разбери", "найд", "проверь", "сумм", "срок", "риски", "поля", "контрагент", "счет", "счёт"])


def _is_local_table_request(text: str) -> bool:
    if _contains_any(text, ["google sheets", "google-таблиц", "google таблиц", "docs.google", "telegram", "телеграм", "whatsapp", "localos"]):
        return False
    return _contains_any(text, ["таблиц", "xlsx", "excel", "csv", "строк"])


def _is_browser_monitoring_request(text: str) -> bool:
    if not _contains_any(text, ["сайт", "страниц", "url", "лендинг", "браузер", "browser"]):
        return False
    return _contains_any(text, ["откры", "провер", "монитор", "след", "измен", "сравн", "собир"])


def _metadata(description: str, category: str, sources: List[str]) -> Dict[str, Any]:
    return {
        "builder": "description_builder_v1",
        "compiler": "agent_compiler_v1",
        "compiled_workflow_status": "draft",
        "request_text": description,
        "draft_category": category,
        "data_sources": sources,
        "outputs": [_output_format_for_category(category)],
        "approval_boundaries": ["final_output", "external_delivery"],
        "external_delivery": "approval_required",
        "side_effects": "none_in_draft_builder",
    }


def _generic_required_integration_bindings(sources: List[str]) -> List[Dict[str, Any]]:
    bindings = []
    if "browser_use" in sources:
        bindings.append(
            {
                "key": "browser_use_read",
                "provider": "browser_use",
                "direction": "external_read",
                "capability": "browser_use.read_page",
                "required": True,
                "approval_required": True,
                "required_config": ["target_urls"],
                "default_limits": {"daily_page_check_cap": 50, "frequency_cap_minutes": 60},
                "execution_boundary": "openclaw_browser_boundary",
            }
        )
    if "telegram" in sources:
        bindings.append(
            {
                "key": "telegram_delivery",
                "provider": "telegram",
                "direction": "external_write",
                "capability": "communications.draft",
                "required": True,
                "approval_required": True,
                "default_limits": {"daily_message_cap": 50, "frequency_cap_minutes": 30},
            }
        )
    if "whatsapp" in sources:
        bindings.append(
            {
                "key": "whatsapp_delivery",
                "provider": "whatsapp",
                "direction": "external_write",
                "capability": "communications.draft",
                "required": True,
                "approval_required": True,
                "required_config": ["channel_mode"],
                "default_limits": {"daily_message_cap": 50, "frequency_cap_minutes": 30},
            }
        )
    return bindings


def _attach_compiled_metadata(metadata: Dict[str, Any], version_payload: Dict[str, Any], schema: str, approval_boundary: str) -> None:
    metadata["compiled_process"] = {
        "schema": schema,
        "trigger": str(version_payload.get("trigger") or "manual.run"),
        "runtime_truth": "agent_blueprint_versions.steps_json",
        "approval_boundary": approval_boundary,
    }
    metadata["compiler_contract"] = {
        "llm_usage": "design_time_only",
        "runtime_truth": "agent_blueprint_versions.steps_json",
        "runtime_llm_required": False,
        "runtime_executes_compiled_steps": True,
    }
    metadata["compiled_artifact_candidate"] = build_compiled_artifact_candidate(version_payload, metadata)
    metadata["compiled_validation"] = metadata["compiled_artifact_candidate"]["validation"]


SOURCE_SPECS: List[Dict[str, Any]] = [
    {
        "key": "telegram",
        "keywords": ["telegram", "телеграм", "бот", "сообщени", "webhook"],
        "binding_key": "telegram_trigger",
        "provider": "telegram",
        "direction": "trigger",
        "trigger": "telegram.message.received",
        "default_capability": "",
        "default_config": {"bot_mode": "business_bot"},
        "required_config": ["bot_mode"],
    },
    {
        "key": "google_sheets",
        "keywords": ["google sheets", "google таблиц", "таблиц", "sheet", "sheets", "spreadsheet", "xlsx", "csv"],
        "binding_key": "google_sheets_read",
        "provider": "google_sheets",
        "direction": "external_read",
        "trigger": "",
        "default_capability": "google_sheets.read_rows",
        "default_config": {"sheet_name": "Sheet1"},
        "required_config": ["spreadsheet_id", "sheet_name"],
    },
]


DESTINATION_SPECS: List[Dict[str, Any]] = [
    {
        "key": "localos_finance",
        "keywords": [
            "финанс",
            "оплат",
            "платеж",
            "платёж",
            "транзакц",
            "доход",
            "расход",
            "выручк",
            "finance",
            "payment",
            "transaction",
        ],
        "binding_key": "localos_finance",
        "provider": "localos_finance",
        "direction": "localos_write_request",
        "capability": "finance.transaction.create",
        "approval_type": "finance_transaction_import",
        "default_config": {"transaction_type": "auto_detect"},
        "required_config": ["transaction_type"],
        "default_limits": {"daily_transaction_cap": 100},
    },
    {
        "key": "google_sheets",
        "keywords": ["google sheets", "google таблиц", "таблиц", "sheet", "sheets", "spreadsheet"],
        "binding_key": "google_sheets_append",
        "provider": "google_sheets",
        "direction": "external_write",
        "capability": "sheets.append_row_request",
        "approval_type": "sheet_update",
        "default_config": {"sheet_name": "Leads"},
        "required_config": ["spreadsheet_id", "sheet_name"],
        "default_limits": {"daily_append_cap": 50},
    },
    {
        "key": "telegram",
        "keywords": ["telegram", "телеграм", "пост", "канал", "публикац", "опублику", "сообщение"],
        "binding_key": "telegram_delivery",
        "provider": "telegram",
        "direction": "external_publish_request",
        "capability": "communications.draft",
        "approval_type": "telegram_post_approval",
        "default_config": {"bot_mode": "business_bot"},
        "required_config": ["bot_mode"],
        "default_limits": {"daily_post_cap": 10},
    },
]


def _matching_spec(text: str, specs: List[Dict[str, Any]]) -> Dict[str, Any]:
    lowered = text.lower()
    for spec in specs:
        if _contains_any(lowered, list(spec.get("keywords") or [])):
            return spec
    return {}


def _spec_by_key(key: str, specs: List[Dict[str, Any]]) -> Dict[str, Any]:
    clean = str(key or "").strip()
    for spec in specs:
        if spec.get("key") == clean:
            return spec
    return {}


def _intent_from_llm_result(ai_result: Dict[str, Any]) -> Dict[str, Any]:
    intent = ai_result.get("intent") if isinstance(ai_result.get("intent"), dict) else {}
    if not intent:
        return {}
    source = _spec_by_key(str(intent.get("source") or ""), SOURCE_SPECS)
    destination = _spec_by_key(str(intent.get("destination") or ""), DESTINATION_SPECS)
    if not source or not destination:
        return {}
    source = dict(source)
    destination = dict(destination)
    read_capability = str(intent.get("read_capability") or "").strip()
    write_capability = str(intent.get("write_capability") or "").strip()
    if read_capability:
        source["default_capability"] = read_capability
    if write_capability:
        destination["capability"] = write_capability
    trigger = str(intent.get("trigger") or "manual.run")
    schedule = {"time": "19:00", "timezone": "business_timezone"} if trigger == "schedule.daily" else {}
    return {
        "source": source,
        "destination": destination,
        "trigger": trigger,
        "schedule": schedule,
        "llm_intent": intent,
    }


def _intent_is_supported_by_text(description: str, intent: Dict[str, Any]) -> bool:
    lowered = description.lower()
    source = intent.get("source") if isinstance(intent.get("source"), dict) else {}
    destination = intent.get("destination") if isinstance(intent.get("destination"), dict) else {}
    source_key = str(source.get("key") or "")
    destination_key = str(destination.get("key") or "")
    if source_key == "google_sheets" and not _contains_any(lowered, ["google sheets", "google таблиц", "таблиц", "sheet", "sheets", "spreadsheet", "xlsx", "csv"]):
        return False
    if destination_key == "telegram" and not _contains_any(lowered, ["telegram", "телеграм", "бот"]):
        return False
    if destination_key == "google_sheets" and not _contains_any(lowered, ["google sheets", "google таблиц", "таблиц", "sheet", "sheets", "spreadsheet", "xlsx", "csv"]):
        return False
    if destination_key == "localos_finance" and not _is_localos_finance_monitoring_request(lowered):
        return False
    return True


def _infer_integration_intent(description: str) -> Dict[str, Any]:
    lowered = description.lower()
    localos_digest_delivery = _localos_context_to_telegram_intent(lowered)
    if localos_digest_delivery:
        return localos_digest_delivery
    review_telegram_delivery = _review_telegram_delivery_intent(lowered)
    if review_telegram_delivery:
        return review_telegram_delivery
    if (
        _contains_any(lowered, ["google sheets", "google таблиц", "таблиц", "sheet", "sheets", "spreadsheet"])
        and _contains_any(lowered, ["telegram", "телеграм"])
        and _contains_any(lowered, ["пост", "канал", "опублику", "публикац", "сообщен", "отправ", "шл", "присыла"])
    ):
        source = _spec_by_key("google_sheets", SOURCE_SPECS)
        destination = _spec_by_key("telegram", DESTINATION_SPECS)
        trigger = "manual.run"
        schedule = {}
        if _contains_any(lowered, ["каждый", "ежеднев", "вечер", "утро", "день", "предыдущ", "вчера", "schedule", "daily"]):
            trigger = "schedule.daily"
            schedule = {"time": "10:00", "timezone": "business_timezone"}
        return {
            "source": source,
            "destination": destination,
            "trigger": trigger,
            "schedule": schedule,
            "compiled_template_key": "google_sheets_to_telegram_post",
        }
    has_google_sheet_source = _contains_any(
        lowered,
        ["google sheets", "google-таблиц", "google таблиц", "spreadsheet", "docs.google"],
    ) or (
        _contains_any(lowered, ["гугл", "google"])
        and _contains_any(lowered, ["таблиц", "sheet", "sheets"])
    )
    has_source_only_result_request = _contains_any(
        lowered,
        ["пост", "контент", "сообщен", "результат", "черновик", "выбира", "найд", "строк"],
    )
    has_explicit_external_destination = (
        _contains_any(lowered, ["telegram", "телеграм", "бот"])
        or _is_localos_finance_monitoring_request(lowered)
        or (
            _contains_any(lowered, ["добав", "запиш", "append", "insert"])
            and _contains_any(lowered, ["строк", "таблиц", "sheet", "sheets", "spreadsheet"])
        )
    )
    if (
        has_google_sheet_source
        and has_source_only_result_request
        and not has_explicit_external_destination
    ):
        source = _spec_by_key("google_sheets", SOURCE_SPECS)
        trigger = "manual.run"
        schedule = {}
        if _contains_any(lowered, ["каждый", "ежеднев", "вечер", "утро", "день", "schedule", "daily"]):
            trigger = "schedule.daily"
            schedule = {"time": "10:00", "timezone": "business_timezone"}
        return {
            "source": source,
            "trigger": trigger,
            "schedule": schedule,
            "compiled_template_key": "google_sheets_to_business_result",
            "output_kind": "business_result",
        }
    direct_telegram_delivery = _direct_telegram_delivery_intent(lowered)
    if direct_telegram_delivery:
        return direct_telegram_delivery
    source = _matching_spec(lowered, SOURCE_SPECS)
    destination = _matching_spec(lowered, DESTINATION_SPECS)
    if not source or not destination:
        return {}
    if (source.get("key") == "telegram" or destination.get("key") == "telegram") and not _contains_any(lowered, ["telegram", "телеграм", "бот", "webhook"]):
        return {}
    if source.get("key") == destination.get("key") and source.get("key") != "telegram":
        return {}
    action_words = ["связ", "процесс", "workflow", "автомат", "редакт", "добав", "строк", "append", "занос", "созда", "запис", "импорт", "каждый", "ежеднев"]
    if not _contains_any(lowered, action_words):
        return {}
    trigger = str(source.get("trigger") or "")
    schedule = {}
    if _contains_any(lowered, ["каждый", "ежеднев", "вечер", "утро", "день", "schedule", "daily"]):
        trigger = "schedule.daily"
        schedule = {"time": "19:00", "timezone": "business_timezone"}
    if not trigger:
        trigger = "manual.run"
    return {
        "source": source,
        "destination": destination,
        "trigger": trigger,
        "schedule": schedule,
    }


def _source_only_compilation(description: str, intent: Dict[str, Any]) -> Dict[str, Any]:
    source = intent.get("source") if isinstance(intent.get("source"), dict) else {}
    trigger = str(intent.get("trigger") or "manual.run")
    schedule = intent.get("schedule") if isinstance(intent.get("schedule"), dict) else {}
    source_binding = _source_binding(source, trigger)
    source_step_key = f"read_{source.get('key') or 'source'}"
    save_to_content_plan = _contains_any(
        description.lower(),
        ["контент-план", "контент план", "content plan"],
    ) and _contains_any(description.lower(), ["сохран", "добав", "запиш", "созда"])
    scheduled_for = _extract_requested_date(description)
    steps = [
        _source_step(source, trigger),
        {
            "key": "prepare_output",
            "type": "artifact",
            "title": "Подготовить результат",
            "artifact_type": "agent_output_draft",
            "payload": {
                "status": "draft",
                "category": "custom",
                "format": "Готовый результат по задаче: сообщение, список действий или черновик для проверки.",
                "source_step": source_step_key,
                "rows_from_step": source_step_key,
                "external_dispatch_performed": False,
                "delivery_state": "not_dispatched",
            },
        },
    ]
    if save_to_content_plan:
        steps.append(
            {
                "key": "save_content_plan_draft",
                "type": "capability",
                "title": "Сохранить черновик в контент-план",
                "capability": "content_plan.item.create_draft",
                "requires_approval": False,
                "payload": {
                    "scheduled_for": scheduled_for,
                    "source_run_id": "{{run_id}}",
                    "input_mappings": [
                        {"from_step": "prepare_output", "path": "artifact.result.draft_text", "target": "draft_text"},
                        {"from_step": "prepare_output", "path": "artifact.result.title", "target": "theme"},
                    ],
                },
            }
        )
    steps.append(
        {
            "key": "save_result",
            "type": "artifact",
            "title": "Сохранить итог",
            "artifact_type": "agent_final_result",
            "payload": {
                "status": "saved",
                "source_step": source_step_key,
                "content_plan_step": "save_content_plan_draft" if save_to_content_plan else "",
                "external_dispatch_performed": False,
                "delivery_state": "not_dispatched",
            },
        }
    )
    steps = annotate_steps_with_openclaw_action_refs(steps)
    read_capability = str(source.get("default_capability") or "")
    capability_allowlist = [read_capability] if read_capability else []
    if save_to_content_plan:
        capability_allowlist.append("content_plan.item.create_draft")
    version_payload = {
        "goal": description,
        "trigger": trigger,
        "mode": "source_to_reviewed_result",
        "inputs_schema": {
            "type": "object",
            "properties": {
                "integration_id": {"type": "string"},
                "spreadsheet_id": {"type": "string"},
                "sheet_name": {"type": "string"},
                "request": {"type": "string"},
            },
        },
        "steps": steps,
        "capability_allowlist": capability_allowlist,
        "approval_policy": {
            "required_for": [],
            "mode": "external_actions_only",
        },
        "required_integration_bindings": [source_binding],
        "limits": {
            "max_items_per_run": 100,
            "autonomous_external_write_allowed": False,
            "autonomous_localos_write_allowed": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "source_items": {"type": "array"},
                "result": {"type": "object"},
                "content_plan_item": {"type": "object"},
            },
        },
        "side_effects_performed": save_to_content_plan,
    }
    if save_to_content_plan:
        version_payload["inputs_schema"]["properties"]["scheduled_for"] = {
            "type": "string",
            "format": "date",
            "title": "Дата в контент-плане",
            "description": "Будущая дата, на которую нужно сохранить черновик.",
            "default": scheduled_for,
        }
        version_payload["inputs_schema"]["required"] = ["scheduled_for"]
    if schedule:
        version_payload["schedule"] = schedule
    sources = [str(source.get("key") or "source"), "business_profile"]
    metadata = _metadata(description, "custom", sources)
    metadata["custom_process"] = {
        "kind": "source_to_result_workflow",
        "trigger": trigger,
        "schedule": schedule,
        "source": read_capability or str(source.get("key") or ""),
        "target": "content_plan.item.create_draft" if save_to_content_plan else "agent_output_draft",
        "runtime": "agent_blueprints",
        "archetype": f"{source.get('key')}_to_business_result",
        "binding_status": "requires_user_connection",
    }
    metadata["compiled_process"] = {
        "schema": "compiled_source_to_result_workflow_v1",
        "source_binding": str(source_binding.get("key") or ""),
        "runtime_truth": "agent_blueprint_versions.steps_json",
        "approval_boundary": "external_actions_only",
    }
    metadata["execution_mode"] = "scheduled" if trigger == "schedule.daily" else "manual"
    metadata["content_plan_destination"] = {
        "enabled": save_to_content_plan,
        "scheduled_for": scheduled_for,
    }
    metadata["compiler_contract"] = {
        "llm_usage": "design_time_only",
        "runtime_truth": "agent_blueprint_versions.steps_json",
        "runtime_llm_required": False,
        "runtime_executes_compiled_steps": True,
    }
    metadata["required_integration_bindings"] = version_payload["required_integration_bindings"]
    metadata["compiled_artifact_candidate"] = build_compiled_artifact_candidate(version_payload, metadata)
    metadata["compiled_validation"] = metadata["compiled_artifact_candidate"]["validation"]
    return {
        "name": _draft_name(description, "Кастомный рабочий агент"),
        "category": "custom",
        "description": description,
        "metadata": metadata,
        "version_payload": version_payload,
        "summary": _summary("custom", sources, steps),
    }
    if (source.get("key") == "telegram" or destination.get("key") == "telegram") and not _contains_any(lowered, ["telegram", "телеграм", "бот", "webhook"]):
        return {}
    if source.get("key") == destination.get("key") and source.get("key") != "telegram":
        return {}
    action_words = ["связ", "процесс", "workflow", "автомат", "редакт", "добав", "строк", "append", "занос", "созда", "запис", "импорт", "каждый", "ежеднев"]
    if not _contains_any(lowered, action_words):
        return {}
    trigger = str(source.get("trigger") or "")
    schedule = {}
    if _contains_any(lowered, ["каждый", "ежеднев", "вечер", "утро", "день", "schedule", "daily"]):
        trigger = "schedule.daily"
        schedule = {"time": "19:00", "timezone": "business_timezone"}
    if not trigger:
        trigger = "manual.run"
    return {
        "source": source,
        "destination": destination,
        "trigger": trigger,
        "schedule": schedule,
    }


def _review_telegram_delivery_intent(lowered: str) -> Dict[str, Any]:
    if not _contains_any(lowered, ["отзыв", "review"]):
        return {}
    if not _contains_any(lowered, ["telegram", "телеграм"]):
        return {}
    if not _contains_any(lowered, ["уведом", "присыла", "отправ", "шл", "сообщен"]):
        return {}
    source = {
        "key": "external_reviews",
        "binding_key": "business_reviews_context",
        "provider": "business_profile",
        "direction": "local_context",
        "default_capability": "",
        "default_config": {},
        "required_config": [],
    }
    destination = _spec_by_key("telegram", DESTINATION_SPECS)
    trigger = "manual.run"
    schedule = {}
    if _contains_any(lowered, ["каждый", "каждое", "каждую", "ежеднев", "день", "утро", "вечер", "schedule", "daily"]):
        trigger = "schedule.daily"
        schedule = _schedule_from_text(lowered)
    return {
        "source": source,
        "destination": destination,
        "trigger": trigger,
        "schedule": schedule,
        "compiled_template_key": "reviews_to_telegram",
    }


def _localos_context_to_telegram_intent(lowered: str) -> Dict[str, Any]:
    if not _contains_any(lowered, ["telegram", "телеграм"]):
        return {}
    if not _contains_any(lowered, ["уведом", "присыла", "отправ", "шл", "сообщен", "дайджест"]):
        return {}
    source_key = ""
    provider = "business_profile"
    if _contains_any(lowered, ["дайджест", "проблем", "просроченные задачи", "необычные расходы"]):
        source_key = "localos_digest"
    elif _is_localos_finance_monitoring_request(lowered):
        source_key = "localos_finance"
        provider = "localos_finance"
    elif _contains_any(lowered, ["запис", "предоплат", "отмен"]):
        source_key = "appointments"
    elif _is_customer_data_quality_request(lowered):
        source_key = "clients"
    elif _is_partner_replies_request(lowered):
        source_key = "partnership_replies"
    if not source_key:
        return {}
    source = {
        "key": source_key,
        "binding_key": f"{source_key}_context",
        "provider": provider,
        "direction": "local_context",
        "default_capability": "",
        "default_config": {},
        "required_config": [],
    }
    destination = _spec_by_key("telegram", DESTINATION_SPECS)
    trigger = "manual.run"
    schedule = {}
    if _contains_any(lowered, ["каждый", "каждое", "каждую", "ежеднев", "еженед", "утро", "вечер", "день", "понедельник", "вторник", "сред", "четверг", "пятниц"]):
        trigger = "schedule.daily"
        schedule = _schedule_from_text(lowered)
    return {
        "source": source,
        "destination": destination,
        "trigger": trigger,
        "schedule": schedule,
        "compiled_template_key": f"{source_key}_to_telegram",
    }


def _direct_telegram_delivery_intent(lowered: str) -> Dict[str, Any]:
    if not _contains_any(lowered, ["telegram", "телеграм"]):
        return {}
    if not _contains_any(lowered, ["шл", "отправ", "присыла", "сообщен", "напиши"]):
        return {}
    if not _contains_any(lowered, ["каждый", "каждое", "каждую", "ежеднев", "утро", "день", "вечер", "schedule", "daily"]):
        return {}
    source = {
        "key": "manual_context",
        "binding_key": "business_profile_context",
        "provider": "business_profile",
        "direction": "local_context",
        "default_capability": "",
        "default_config": {},
        "required_config": [],
    }
    destination = _spec_by_key("telegram", DESTINATION_SPECS)
    return {
        "source": source,
        "destination": destination,
        "trigger": "schedule.daily",
        "schedule": _schedule_from_text(lowered),
        "compiled_template_key": "scheduled_telegram_message",
    }


def _schedule_from_text(lowered: str) -> Dict[str, str]:
    hour = ""
    match = re.search(r"(?:в\s*)?(\d{1,2})(?::(\d{2}))?\s*(?:утра|вечера|дня)?", lowered)
    if match:
        raw_hour = int(match.group(1))
        minutes = match.group(2) or "00"
        if "вечера" in lowered and 1 <= raw_hour <= 11:
            raw_hour += 12
        hour = f"{raw_hour:02d}:{minutes}"
    return {"time": hour or "09:00", "timezone": "business_timezone"}


def _is_email_authoring_request(text: str) -> bool:
    if _contains_any(text, ["письм", "почт", "рассыл"]):
        return True
    if "email" not in text:
        return False
    return _contains_any(text, ["напис", "подготов", "отправ", "черновик", "тема письма", "body"])


def _is_customer_data_quality_request(text: str) -> bool:
    if not _contains_any(text, ["клиент"]):
        return False
    return _contains_any(text, ["без телефона", "без email", "без e-mail", "источник прихода"])


def _is_client_reactivation_request(text: str) -> bool:
    if not _contains_any(text, ["клиент"]):
        return False
    return _contains_any(text, ["не записывал", "не записывались", "старых клиентов", "больше 60", "возврат"])


def _is_localos_finance_monitoring_request(text: str) -> bool:
    if _is_manager_report_request(text) or _is_inventory_control_request(text) or _is_revenue_anomaly_request(text):
        return False
    if _contains_any(text, ["счёт", "счет", "счета", "счёта", "неоплачен", "просрочен"]):
        return True
    if "предоплат" in text and not _contains_any(text, ["запис", "клиент"]):
        return True
    if _contains_any(text, ["оплат", "платеж", "платёж", "транзакц"]) and not _contains_any(text, ["запис", "клиент"]):
        return True
    if _contains_any(text, ["расход", "траты", "трата", "трату", "финанс"]):
        return True
    return False


def _is_partner_replies_request(text: str) -> bool:
    return _contains_any(text, ["партн"]) and _contains_any(text, ["ответ", "отказ", "интерес", "ручной ответ"])


def _is_review_location_analysis_request(text: str) -> bool:
    if not _contains_any(text, ["отзыв", "review"]):
        return False
    if _contains_any(text, ["выруч", "расход", "финанс"]) and _contains_any(text, ["запис", "рекомендац", "следующую неделю"]):
        return False
    return _contains_any(text, ["филиал", "точк", "сети", "рейтинг", "паден"])


def _is_review_based_content_request(text: str) -> bool:
    if not _contains_any(text, ["отзыв", "review"]):
        return False
    return _contains_any(text, ["идеи пост", "идея пост", "3 идеи", "три идеи", "постов", "контент"])


def _is_photo_quality_request(text: str) -> bool:
    if _is_new_employee_check_request(text):
        return False
    if not _contains_any(text, ["фото", "фотограф"]):
        return False
    return _contains_any(text, ["карточ", "филиал", "точк", "устарев", "тёмн", "темн", "нерелевант", "замен"])


def _is_competitor_price_request(text: str) -> bool:
    if not _contains_any(text, ["конкурент"]):
        return False
    return _contains_any(text, ["цен", "рынок", "выше", "ниже", "поблизости"])


def _is_cancellation_risk_request(text: str) -> bool:
    if _is_cancellation_reasons_request(text):
        return False
    if not _contains_any(text, ["запис", "визит"]):
        return False
    return _contains_any(text, ["отмен", "риск", "часто отмен"])


def _is_new_service_control_request(text: str) -> bool:
    if not _contains_any(text, ["услуг"]):
        return False
    return _contains_any(text, ["новая", "новую", "появляется", "улучш"])


def _is_customer_questions_request(text: str) -> bool:
    if not _contains_any(text, ["вопрос"]):
        return False
    return _contains_any(text, ["клиент", "telegram", "телеграм", "whatsapp", "база знаний", "тем"])


def _is_team_tasks_request(text: str) -> bool:
    if not _contains_any(text, ["задач"]):
        return False
    return _contains_any(text, ["сотруд", "ответствен", "срок", "просроч"])


def _is_no_discount_promo_request(text: str) -> bool:
    if not _contains_any(text, ["без скид"]):
        return False
    return _contains_any(text, ["иде", "акц", "продвиж", "сезон", "услуг", "отзыв"])


def _is_repeated_complaints_request(text: str) -> bool:
    if not _contains_any(text, ["повтор"]):
        return False
    return _contains_any(text, ["жалоб", "проблем", "отзыв", "сообщен", "сервис"])


def _is_manager_report_request(text: str) -> bool:
    if not _contains_any(text, ["отчёт", "отчет"]):
        return False
    return _contains_any(text, ["управляющ", "филиал", "выруч", "расход", "запис", "рекомендац"])


def _is_holiday_readiness_request(text: str) -> bool:
    if not _contains_any(text, ["праздн"]):
        return False
    return _contains_any(text, ["готов", "чеклист", "карточ", "услуг", "пост", "распис"])


def _is_inventory_control_request(text: str) -> bool:
    return _contains_any(text, ["остатк", "расходник", "товар"]) and _contains_any(text, ["ниже минимума", "минимум", "заказ", "заказать"])


def _is_staff_schedule_request(text: str) -> bool:
    if _is_new_employee_check_request(text):
        return False
    if not _contains_any(text, ["расписан", "смен", "график"]):
        return False
    return _contains_any(text, ["сотруд", "пересеч", "пустые окна", "перегруз"])


def _is_cancellation_reasons_request(text: str) -> bool:
    if not _contains_any(text, ["отмен"]):
        return False
    return _contains_any(text, ["причин", "группир", "процесс записи", "что изменить"])


def _is_admin_response_control_request(text: str) -> bool:
    if not _contains_any(text, ["чат", "диалог", "переписк"]):
        return False
    return _contains_any(text, ["администратор", "долго не ответ", "ответил неполно"])


def _is_faq_from_chats_request(text: str) -> bool:
    if not _contains_any(text, ["faq", "база знаний", "пункты"]):
        return False
    return _contains_any(text, ["чат", "переписк", "вопрос", "клиент"])


def _is_new_employee_check_request(text: str) -> bool:
    if not _contains_any(text, ["сотруд"]):
        return False
    return _contains_any(text, ["добавляется", "новый", "фото", "описание", "график", "привязка к филиалу"])


def _is_seasonal_services_request(text: str) -> bool:
    if not _contains_any(text, ["сезон"]):
        return False
    return _contains_any(text, ["добавить", "скрыть", "обновить", "прайс"])


def _is_revenue_anomaly_request(text: str) -> bool:
    if not _contains_any(text, ["выруч"]):
        return False
    return _contains_any(text, ["аномал", "обычным уровнем", "отклон", "сравни"])


def _is_map_questions_request(text: str) -> bool:
    if not _contains_any(text, ["вопрос"]):
        return False
    return _contains_any(text, ["яндекс", "google-карточ", "google карточ", "карточк", "карт"])


def _is_location_description_quality_request(text: str) -> bool:
    if not _contains_any(text, ["описан"]):
        return False
    return _contains_any(text, ["филиал", "устарев", "одинаковые тексты", "слабые формулировки"])


def _is_problem_digest_request(text: str) -> bool:
    if "дайджест" in text:
        return True
    markers = [
        "негативные отзывы",
        "отменённые записи",
        "отмененные записи",
        "просроченные задачи",
        "необычные расходы",
    ]
    return sum(1 for marker in markers if marker in text) >= 2


def _is_rich_localos_workflow_request(text: str) -> bool:
    lowered = text.lower()
    return any(
        [
            _is_photo_quality_request(lowered),
            _is_competitor_price_request(lowered),
            _is_inventory_control_request(lowered),
            _is_staff_schedule_request(lowered),
            _is_cancellation_reasons_request(lowered),
            _is_admin_response_control_request(lowered),
            _is_faq_from_chats_request(lowered),
            _is_new_employee_check_request(lowered),
            _is_seasonal_services_request(lowered),
            _is_revenue_anomaly_request(lowered),
            _is_map_questions_request(lowered),
            _is_location_description_quality_request(lowered),
            _is_new_service_control_request(lowered),
            _is_customer_questions_request(lowered),
            _is_team_tasks_request(lowered),
            _is_no_discount_promo_request(lowered),
            _is_repeated_complaints_request(lowered),
            _is_manager_report_request(lowered),
            _is_holiday_readiness_request(lowered),
            _is_problem_digest_request(lowered),
        ]
    )


def _source_binding(source: Dict[str, Any], trigger: str) -> Dict[str, Any]:
    binding = {
        "key": str(source.get("binding_key") or source.get("key") or "source"),
        "provider": str(source.get("provider") or source.get("key") or ""),
        "direction": str(source.get("direction") or "external_read"),
        "required": True,
        "approval_required": False,
        "required_config": list(source.get("required_config") or []),
        "default_config": dict(source.get("default_config") or {}),
    }
    capability = str(source.get("default_capability") or "")
    if capability:
        binding["capability"] = capability
    if trigger and trigger != "manual.run":
        binding["trigger"] = trigger
    return binding


def _destination_binding(destination: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "key": str(destination.get("binding_key") or destination.get("key") or "destination"),
        "provider": str(destination.get("provider") or destination.get("key") or ""),
        "direction": str(destination.get("direction") or "request"),
        "capability": str(destination.get("capability") or ""),
        "required": True,
        "approval_required": True,
        "required_config": list(destination.get("required_config") or []),
        "default_config": dict(destination.get("default_config") or {}),
        "default_limits": dict(destination.get("default_limits") or {}),
    }


def _source_step(source: Dict[str, Any], trigger: str) -> Dict[str, Any]:
    source_key = str(source.get("key") or "source")
    if source_key == "manual_context":
        return {
            "key": "collect_manual_context",
            "type": "artifact",
            "title": "Собрать контекст задачи",
            "artifact_type": "agent_input_plan",
            "payload": {
                "trigger": trigger,
                "source": "manual_context",
                "status": "ready",
                "external_dispatch_performed": False,
            },
        }
    if source_key == "telegram":
        return {
            "key": "capture_telegram_trigger",
            "type": "artifact",
            "title": "Принять Telegram-событие",
            "artifact_type": "integration_trigger_event",
            "payload": {
                "trigger": trigger,
                "integration_binding": str(source.get("binding_key") or "telegram_trigger"),
                "source": "telegram",
                "status": "captured",
                "external_dispatch_performed": False,
            },
        }
    return {
        "key": f"read_{source_key}",
        "type": "capability",
        "title": "Прочитать данные источника",
        "capability": str(source.get("default_capability") or ""),
        "requires_approval": False,
        "payload": {
            "integration_binding": str(source.get("binding_key") or source_key),
            "limit": 100,
            "provider_read_performed": False,
        },
        "output_contract": {
            "rows": "orchestrator.result.rows",
            "count": "orchestrator.result.count",
            "source": "orchestrator.result.source",
        },
    }


def _transform_step(source: Dict[str, Any], destination: Dict[str, Any]) -> Dict[str, Any]:
    if destination.get("key") == "localos_finance":
        return {
            "key": "normalize_finance_rows",
            "type": "artifact",
            "title": "Нормализовать финансовые строки",
            "artifact_type": "finance_import_preview",
            "payload": {
                "normalizer": "core.finance_imports.normalize_finance_import_rows",
                "record_type": "entry",
                "duplicate_key_required": True,
                "source_step": f"read_{source.get('key') or 'source'}",
                "localos_write_performed": False,
            },
        }
    if source.get("key") == "telegram" and destination.get("key") == "google_sheets":
        return {
            "key": "prepare_sheet_row",
            "type": "artifact",
            "title": "Подготовить строку таблицы",
            "artifact_type": "sheet_row_draft",
            "payload": {
                "status": "draft",
                "operation": "append_row",
                "integration_binding": str(destination.get("binding_key") or "google_sheets_append"),
                "columns": ["received_at", "telegram_username", "message_text"],
                "row_values": ["{{received_at}}", "{{telegram_username}}", "{{message_text}}"],
                "provider_write_performed": False,
            },
        }
    if source.get("key") == "google_sheets" and destination.get("key") == "telegram":
        return {
            "key": "prepare_telegram_post",
            "type": "artifact",
            "title": "Подготовить пост для Telegram",
            "artifact_type": "telegram_post_draft",
            "payload": {
                "status": "draft",
                "selection_rule": "choose one order from previous day",
                "style": "наши пассажиры насладились поездкой из {from} в {to}",
                "source_step": "read_google_sheets",
                "external_dispatch_performed": False,
                "delivery_state": "not_dispatched",
            },
        }
    return {
        "key": "prepare_destination_payload",
        "type": "artifact",
        "title": "Подготовить данные для действия",
        "artifact_type": "capability_payload_preview",
        "payload": {
            "source": str(source.get("key") or "source"),
            "destination": str(destination.get("key") or "destination"),
            "side_effects_performed": False,
        },
    }


def _approval_step(destination: Dict[str, Any]) -> Dict[str, Any]:
    approval_type = str(destination.get("approval_type") or "external_action")
    reason = "Действие требует подтверждения перед выполнением."
    if approval_type == "finance_transaction_import":
        reason = "Новые категории, низкая уверенность и ошибки требуют проверки перед записью в финансы."
    elif approval_type == "sheet_update":
        reason = "Внешняя запись в Google Sheets требует подтверждения."
    return {
        "key": f"approve_{approval_type}",
        "type": "approval",
        "title": "Подтвердить действие",
        "approval_type": approval_type,
        "payload": {
            "reason": reason,
            "side_effects_performed": False,
        },
    }


def _destination_capability_step(source: Dict[str, Any], destination: Dict[str, Any]) -> Dict[str, Any]:
    destination_key = str(destination.get("key") or "destination")
    capability = str(destination.get("capability") or "")
    payload = {
        "source": str(source.get("key") or "source"),
        "integration_binding": str(destination.get("binding_key") or destination_key),
        "approval_policy": "first_run",
        "provider_write_performed": False,
    }
    if destination_key == "localos_finance":
        payload["localos_write_performed"] = False
        payload["daily_transaction_cap"] = int((destination.get("default_limits") or {}).get("daily_transaction_cap") or 100)
        payload["rows_from_step"] = f"read_{source.get('key') or 'source'}"
        payload["input_mappings"] = [
            {
                "target": "rows",
                "from_step": f"read_{source.get('key') or 'source'}",
                "path": "orchestrator.result.rows",
                "required": True,
            }
        ]
    if destination_key == "google_sheets":
        payload["operation"] = "append_row"
        payload["sheet_name"] = "Leads"
        payload["row_values"] = ["{{received_at}}", "{{telegram_username}}", "{{message_text}}"]
        payload["daily_append_cap"] = int((destination.get("default_limits") or {}).get("daily_append_cap") or 50)
    if destination_key == "telegram":
        payload["message_type"] = "telegram_post_draft"
        payload["channel"] = "telegram"
        payload["daily_post_cap"] = int((destination.get("default_limits") or {}).get("daily_post_cap") or 10)
        payload["rows_from_step"] = f"read_{source.get('key') or 'source'}"
        payload["input_mappings"] = [
            {
                "target": "rows",
                "from_step": f"read_{source.get('key') or 'source'}",
                "path": "orchestrator.result.rows",
                "required": True,
            }
        ]
    return {
        "key": f"request_{destination_key}",
        "type": "capability",
        "title": "Создать заявку на действие",
        "capability": capability,
        "requires_approval": True,
        "required_approval_type": str(destination.get("approval_type") or "external_action"),
        "payload": payload,
    }


def _outcome_step(source: Dict[str, Any], destination: Dict[str, Any]) -> Dict[str, Any]:
    destination_key = str(destination.get("key") or "destination")
    source_step_key = f"read_{source.get('key') or 'source'}"
    journal = ["source_data", "request", "approval", "outcome"]
    if destination_key == "localos_finance":
        journal = ["rows_read", "proposals", "rows_requiring_review", "errors"]
    if destination_key == "telegram":
        journal = ["rows_read", "post_draft", "approval", "publish_request"]
    return {
        "key": f"record_{destination_key}_outcome",
        "type": "artifact",
        "title": "Записать результат",
        "artifact_type": f"{destination_key}_outcome",
        "payload": {
            "status": "request_created",
            "apply_state": "not_applied",
            "journal": journal,
            "source_step": source_step_key if destination_key == "localos_finance" else "",
            "request_step": f"request_{destination_key}",
            "side_effects_performed": False,
        },
    }


def _source_destination_compilation(description: str, intent: Dict[str, Any]) -> Dict[str, Any]:
    source = intent.get("source") if isinstance(intent.get("source"), dict) else {}
    destination = intent.get("destination") if isinstance(intent.get("destination"), dict) else {}
    if source and not destination:
        return _source_only_compilation(description, intent)
    trigger = str(intent.get("trigger") or "manual.run")
    schedule = intent.get("schedule") if isinstance(intent.get("schedule"), dict) else {}
    source_binding = _source_binding(source, trigger)
    destination_binding = _destination_binding(destination)
    steps = [
        _source_step(source, trigger),
        _transform_step(source, destination),
        _approval_step(destination),
        _destination_capability_step(source, destination),
        _outcome_step(source, destination),
    ]
    steps = annotate_steps_with_openclaw_action_refs(steps)
    read_capability = str(source.get("default_capability") or "")
    write_capability = str(destination.get("capability") or "")
    capability_allowlist = [item for item in [read_capability, write_capability] if item]
    approval_type = str(destination.get("approval_type") or "external_action")
    sources = [str(source.get("key") or "source"), str(destination.get("key") or "destination"), "business_profile"]
    limits = {
        "max_items_per_run": 100,
        "autonomous_external_write_allowed": False,
        "autonomous_localos_write_allowed": False,
    }
    limits.update(dict(destination.get("default_limits") or {}))
    version_payload = {
        "goal": description,
        "trigger": trigger,
        "mode": "approved_capability_request",
        "inputs_schema": {
            "type": "object",
            "properties": {
                "integration_id": {"type": "string"},
                "spreadsheet_id": {"type": "string"},
                "sheet_name": {"type": "string"},
                "rows": {"type": "array"},
                "request": {"type": "string"},
            },
        },
        "steps": steps,
        "capability_allowlist": capability_allowlist,
        "approval_policy": {
            "required_for": [approval_type, str(destination.get("direction") or "request")],
            approval_type: "manual_approval_required",
            "first_run": "manual_approval_required",
            "ambiguous_data": "manual_approval_required",
            "mode": "approved_request_only",
        },
        "required_integration_bindings": [source_binding, destination_binding],
        "limits": limits,
        "output_schema": {
            "type": "object",
            "properties": {
                "source_items": {"type": "array"},
                "prepared_request": {"type": "object"},
                "rows_requiring_review": {"type": "array"},
                "errors": {"type": "array"},
                "approval_required": {"type": "boolean"},
            },
        },
        "side_effects_performed": False,
    }
    if schedule:
        version_payload["schedule"] = schedule
    metadata = _metadata(description, "custom", sources)
    metadata["custom_process"] = {
        "kind": "source_destination_workflow",
        "trigger": trigger,
        "schedule": schedule,
        "source": read_capability or str(source.get("key") or ""),
        "target": write_capability,
        "runtime": "agent_blueprints",
        "archetype": f"{source.get('key')}_to_{destination.get('key')}",
        "binding_status": "requires_user_connection",
    }
    metadata["compiled_process"] = {
        "schema": "compiled_source_destination_workflow_v1",
        "source_binding": str(source_binding.get("key") or ""),
        "destination_binding": str(destination_binding.get("key") or ""),
        "runtime_truth": "agent_blueprint_versions.steps_json",
        "approval_boundary": approval_type,
    }
    metadata["compiler_contract"] = {
        "llm_usage": "design_time_only",
        "runtime_truth": "agent_blueprint_versions.steps_json",
        "runtime_llm_required": False,
        "runtime_executes_compiled_steps": True,
    }
    metadata["required_integration_bindings"] = version_payload["required_integration_bindings"]
    metadata["compiled_artifact_candidate"] = build_compiled_artifact_candidate(version_payload, metadata)
    metadata["compiled_validation"] = metadata["compiled_artifact_candidate"]["validation"]
    return {
        "name": _draft_name(description, "Кастомный рабочий агент"),
        "category": "custom",
        "description": description,
        "metadata": metadata,
        "version_payload": version_payload,
        "summary": _summary("custom", sources, steps),
    }


def _custom_integration_compilation(description: str) -> Dict[str, Any]:
    sources = ["telegram_messages", "google_sheets", "business_profile"]
    steps = [
        {
            "key": "capture_telegram_trigger",
            "type": "artifact",
            "title": "Принять Telegram-событие",
            "artifact_type": "integration_trigger_event",
            "payload": {
                "trigger": "telegram.message.received",
                "integration_binding": "telegram_trigger",
                "source": "telegram",
                "status": "captured",
                "external_dispatch_performed": False,
            },
        },
        {
            "key": "prepare_sheet_row",
            "type": "artifact",
            "title": "Подготовить строку таблицы",
            "artifact_type": "sheet_row_draft",
            "payload": {
                "status": "draft",
                "operation": "append_row",
                "integration_binding": "google_sheets_append",
                "columns": ["received_at", "telegram_username", "message_text"],
                "row_values": ["{{received_at}}", "{{telegram_username}}", "{{message_text}}"],
                "provider_write_performed": False,
            },
        },
        {
            "key": "approve_sheet_update",
            "type": "approval",
            "title": "Подтвердить изменение Google Sheets",
            "approval_type": "sheet_update",
            "payload": {
                "reason": "Внешняя запись в Google Sheets требует подтверждения.",
                "provider_write_performed": False,
            },
        },
        {
            "key": "request_sheet_append",
            "type": "capability",
            "title": "Создать заявку на добавление строки",
            "capability": "sheets.append_row_request",
            "requires_approval": True,
            "required_approval_type": "sheet_update",
            "payload": {
                "operation": "append_row",
                "integration_binding": "google_sheets_append",
                "sheet_name": "Leads",
                "row_values": ["{{received_at}}", "{{telegram_username}}", "{{message_text}}"],
                "daily_append_cap": 50,
                "provider_write_performed": False,
            },
        },
        {
            "key": "record_sheet_request",
            "type": "artifact",
            "title": "Записать результат заявки",
            "artifact_type": "sheet_operation_outcome",
            "payload": {
                "status": "request_created",
                "apply_state": "not_applied",
                "provider_write_performed": False,
            },
        },
    ]
    version_payload = {
        "goal": description,
        "trigger": "telegram.message.received",
        "mode": "approved_external_write_request",
        "inputs_schema": {
            "type": "object",
            "properties": {
                "message_text": {"type": "string"},
                "telegram_user_id": {"type": "string"},
                "telegram_username": {"type": "string"},
                "chat_id": {"type": "string"},
                "received_at": {"type": "string"},
                "integration_id": {"type": "string"},
                "spreadsheet_id": {"type": "string"},
                "sheet_name": {"type": "string"},
            },
        },
        "steps": steps,
        "capability_allowlist": ["sheets.append_row_request"],
        "approval_policy": {
            "required_for": ["sheet_update", "external_spreadsheet_write"],
            "external_spreadsheet_write": "manual_approval_required",
            "mode": "approved_request_only",
        },
        "required_integration_bindings": [
            {
                "key": "telegram_trigger",
                "provider": "telegram",
                "direction": "trigger",
                "trigger": "telegram.message.received",
                "required": True,
                "approval_required": False,
            },
            {
                "key": "google_sheets_append",
                "provider": "google_sheets",
                "direction": "external_write",
                "capability": "sheets.append_row_request",
                "required": True,
                "approval_required": True,
                "required_config": ["spreadsheet_id", "sheet_name"],
                "default_config": {"sheet_name": "Leads"},
                "default_limits": {"daily_append_cap": 50},
            },
        ],
        "limits": {
            "daily_append_cap": 50,
            "autonomous_external_write_allowed": False,
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "trigger_event": {"type": "object"},
                "sheet_operation_request": {"type": "object"},
                "approval_required": {"type": "boolean"},
            },
        },
        "external_dispatch_performed": False,
    }
    metadata = _metadata(description, "custom", sources)
    metadata["custom_process"] = {
        "kind": "integration_workflow",
        "trigger": "telegram.message.received",
        "target": "google_sheets.append_row",
        "runtime": "agent_blueprints",
        "showcase": "telegram_to_google_sheets",
        "binding_status": "requires_user_connection",
    }
    metadata["compiled_process"] = {
        "schema": "compiled_integration_workflow_v1",
        "trigger_binding": "telegram_trigger",
        "write_binding": "google_sheets_append",
        "runtime_truth": "agent_blueprint_versions.steps_json",
        "approval_boundary": "sheet_update",
    }
    metadata["required_integration_bindings"] = version_payload["required_integration_bindings"]
    return {
        "name": _draft_name(description, "Кастомный агент интеграций"),
        "category": "custom",
        "description": description,
        "metadata": metadata,
        "version_payload": version_payload,
        "summary": _summary("custom", sources, steps),
    }


def _generic_steps(category: str, description: str, sources: List[str]) -> List[Dict[str, Any]]:
    return [
        {
            "key": "collect_inputs",
            "type": "artifact",
            "title": "Собрать входные данные",
            "artifact_type": "agent_input_plan",
            "payload": {
                "status": "draft",
                "request": description,
                "sources": sources,
                "category": category,
            },
        },
        {
            "key": "extract_context",
            "type": "artifact",
            "title": "Извлечь нужные данные",
            "artifact_type": "agent_extracted_context",
            "payload": {
                "status": "draft",
                "needs_source_upload": category in {"documents", "tables"},
                "source_references_required": True,
            },
        },
        {
            "key": "prepare_output",
            "type": "artifact",
            "title": "Подготовить результат",
            "artifact_type": "agent_output_draft",
            "payload": {
                "status": "draft",
                "format": _output_format_for_category(category),
                "external_dispatch_performed": False,
            },
        },
        {
            "key": "approve_output",
            "type": "approval",
            "title": "Подтвердить результат",
            "approval_type": "final_output",
        },
        {
            "key": "save_result",
            "type": "artifact",
            "title": "Сохранить итог",
            "artifact_type": "agent_final_result",
            "payload": {
                "status": "pending_approval",
                "external_dispatch_performed": False,
                "delivery_state": "not_dispatched",
            },
        },
    ]


def _output_format_for_category(category: str) -> str:
    formats = {
        "communications": "drafts_delivery_report_outcomes",
        "documents": "structured_summary",
        "email": "message_draft",
        "tables": "exceptions_report",
        "reviews": "reply_drafts",
        "partnerships": "proposal_draft",
        "booking": "booking_rules_summary",
        "services": "service_optimization_plan",
    }
    return formats.get(category, "custom_artifact")


def _summary(category: str, sources: List[str], steps: List[Dict[str, Any]]) -> Dict[str, Any]:
    return {
        "category": category,
        "sources": sources,
        "outputs": [_output_format_for_category(category)],
        "approval_boundaries": ["final_output", "external_delivery"],
        "steps": [{"key": step.get("key"), "title": step.get("title"), "type": step.get("type")} for step in steps],
        "approval_required": True,
        "external_dispatch_performed": False,
    }


def _communications_compilation(request_text: str, preferred_template_key: str = "") -> Dict[str, Any]:
    template_key = preferred_template_key or infer_communication_agent_template_key(request_text)
    template = get_communication_agent_template(template_key)
    sources = template["data_sources"]
    draft_step = {
        "key": "send_message",
        "type": "capability",
        "title": "Поставить в подтверждаемую очередь",
        "capability": template["send_capability"],
        "requires_approval": True,
        "required_approval_type": template["approval_type"],
        "payload": {
            "status": "pending_human",
            "mode": template["mode"],
            "trigger": template["trigger"],
            "audience": template["audience"],
            "audience_rules": template["audience_rules"],
            "message_template": template["message_template"],
            "persona": template["persona"],
            "delivery_outcome_journal": template["delivery_outcome_journal"],
            "external_dispatch_performed": False,
            "delivery_state": "queued_not_dispatched",
        },
    }
    if template["mode"] == "draft_only":
        draft_step = {
            "key": "send_message",
            "type": "artifact",
            "title": "Оставить как черновик",
            "artifact_type": "communications_drafts",
            "payload": {
                "status": "draft_only",
                "capability": template["send_capability"],
                "mode": template["mode"],
                "message_template": template["message_template"],
                "persona": template["persona"],
                "external_dispatch_performed": False,
                "delivery_state": "not_dispatched",
            },
        }
    steps = [
        {
            "key": "collect_audience",
            "type": "artifact",
            "title": "Собрать аудиторию",
            "artifact_type": "communications_audience",
            "payload": {
                "status": "draft",
                "trigger": template["trigger"],
                "audience": template["audience"],
                "audience_rules": template["audience_rules"],
                "sources": sources,
            },
        },
        {
            "key": "prepare_message",
            "type": "artifact",
            "title": "Подготовить сообщение",
            "artifact_type": "communications_drafts",
            "payload": {
                "status": "draft",
                "message_goal": template["key"],
                "message_template": template["message_template"],
                "persona": template["persona"],
                "external_dispatch_performed": False,
            },
        },
        {
            "key": "validate_consent",
            "type": "artifact",
            "title": "Проверить согласие и ограничения",
            "artifact_type": "communications_consent_check",
            "payload": {
                "status": "draft",
                "consent_required": True,
                "consent_rules": template["consent_rules"],
                "frequency_cap_required": True,
            },
        },
        {
            "key": "approve_message",
            "type": "approval",
            "title": "Подтвердить результат",
            "approval_type": template["approval_type"],
        },
        draft_step,
        {
            "key": "record_outcome",
            "type": "artifact",
            "title": "Записать результат",
            "artifact_type": "communications_outcomes",
            "payload": {
                "status": "pending_delivery",
                "journal": template["delivery_outcome_journal"],
                "outcomes": [],
                "external_dispatch_performed": False,
            },
        },
    ]
    steps = annotate_steps_with_openclaw_action_refs(steps)
    version_payload = {
        "goal": request_text or "Напоминать клиентам о записи и сообщать про пакетное предложение",
        "inputs_schema": {
            "type": "object",
            "properties": {
                "trigger": {"type": "string", "default": template["trigger"]},
                "audience": {"type": "string", "default": template["audience"]},
                "frequency_cap": {"type": "string", "default": template["frequency_cap"]},
                "daily_cap": {"type": "integer", "default": template["daily_cap"]},
            },
        },
        "steps": steps,
        "capability_allowlist": _communication_capability_allowlist(template["send_capability"]),
        "approval_policy": {
            "required_for": ["first_run", "template", "mass_send", "external_delivery"],
            "first_run": "manual_approval_required",
            "template": "manual_approval_required",
            "mass_send": "manual_approval_required",
            "external_delivery": "manual_approval_required",
            "mode": template["mode"],
            "send_capability": template["send_capability"],
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "drafts": {"type": "array"},
                "delivery_report": {"type": "object"},
                "outcomes": {"type": "array"},
                "delivery_outcome_journal": {"type": "object"},
            },
        },
        "limits": {
            "frequency_cap": template["frequency_cap"],
            "daily_cap": template["daily_cap"],
            "external_send_requires_approval": True,
            "autonomous_send_allowed": False,
        },
        "trigger": template["trigger"],
        "audience": template["audience"],
        "audience_rules": template["audience_rules"],
        "consent_rules": template["consent_rules"],
        "message_template": template["message_template"],
        "persona": template["persona"],
        "send_capability": template["send_capability"],
        "delivery_outcome_journal": template["delivery_outcome_journal"],
        "mode": template["mode"],
        "external_dispatch_performed": False,
        "data_sources": sources,
    }
    metadata = _metadata(request_text, "communications", sources)
    metadata["communication_template_key"] = template["key"]
    metadata["trigger"] = template["trigger"]
    metadata["audience"] = template["audience"]
    metadata["audience_rules"] = template["audience_rules"]
    metadata["consent_rules"] = template["consent_rules"]
    metadata["message_template"] = template["message_template"]
    metadata["persona"] = template["persona"]
    metadata["send_capability"] = template["send_capability"]
    metadata["delivery_outcome_journal"] = template["delivery_outcome_journal"]
    metadata["limits"] = version_payload["limits"]
    metadata["communication_agent_is_blueprint_category"] = True
    metadata["autonomous_send_allowed"] = False
    metadata["compiled_process"] = {
        "schema": "compiled_communications_workflow_v1",
        "trigger": template["trigger"],
        "runtime_truth": "agent_blueprint_versions.steps_json",
        "approval_boundary": template["approval_type"],
    }
    metadata["compiler_contract"] = {
        "llm_usage": "design_time_only",
        "runtime_truth": "agent_blueprint_versions.steps_json",
        "runtime_llm_required": False,
        "runtime_executes_compiled_steps": True,
    }
    metadata["compiled_artifact_candidate"] = build_compiled_artifact_candidate(version_payload, metadata)
    metadata["compiled_validation"] = metadata["compiled_artifact_candidate"]["validation"]
    return {
        "name": _draft_name(request_text, str(template["name"] or "Агент коммуникаций")),
        "category": "communications",
        "description": request_text,
        "metadata": metadata,
        "version_payload": version_payload,
        "summary": _summary("communications", sources, steps)
        | {
            "communication_template_key": template["key"],
            "trigger": template["trigger"],
            "audience": template["audience"],
            "audience_rules": template["audience_rules"],
            "consent_rules": template["consent_rules"],
            "message_template": template["message_template"],
            "persona": template["persona"],
            "send_capability": template["send_capability"],
            "delivery_outcome_journal": template["delivery_outcome_journal"],
            "mode": template["mode"],
            "capability_allowlist": version_payload["capability_allowlist"],
            "limits": version_payload["limits"],
            "output_schema": version_payload["output_schema"],
        },
    }


def _communication_capability_allowlist(send_capability: str) -> List[str]:
    allowlist = ["appointments.read", "communications.draft"]
    if send_capability and send_capability not in allowlist:
        allowlist.append(send_capability)
    return allowlist
