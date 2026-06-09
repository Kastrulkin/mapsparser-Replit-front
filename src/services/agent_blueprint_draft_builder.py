from __future__ import annotations

from typing import Any, Dict, List

from services.agent_blueprint_runner import default_supervised_outreach_version_payload


def _normalized_text(value: Any) -> str:
    return str(value or "").strip()


def _contains_any(text: str, words: List[str]) -> bool:
    lowered = text.lower()
    return any(word in lowered for word in words)


def infer_blueprint_category(description: str) -> str:
    text = description.lower()
    if _contains_any(text, ["напом", "запис", "appointment", "reminder", "клиентам о записи", "пакет"]):
        return "communications"
    if _contains_any(text, ["документ", "договор", "pdf", "docx", "акт", "счёт", "счет"]):
        return "documents"
    if _contains_any(text, ["письм", "email", "почт", "рассыл"]):
        return "email"
    if _contains_any(text, ["таблиц", "xlsx", "excel", "csv", "строк"]):
        return "tables"
    if _contains_any(text, ["лид", "lead", "shortlist", "сообщени", "найди клиентов", "поиск клиентов", "outreach"]):
        return "outreach"
    if _contains_any(text, ["отзыв", "review", "ответ"]):
        return "reviews"
    if _contains_any(text, ["партн", "предложен", "коллаб"]):
        return "partnerships"
    return "custom"


def build_agent_blueprint_draft(description: str, preferred_category: str = "") -> Dict[str, Any]:
    return compile_agent_blueprint(description, preferred_category)


def compile_agent_blueprint(description: str, preferred_category: str = "") -> Dict[str, Any]:
    request_text = _normalized_text(description)
    category = _normalized_category(preferred_category) or infer_blueprint_category(request_text)
    if category == "communications":
        return _communications_compilation(request_text)
    if category == "outreach":
        version_payload = default_supervised_outreach_version_payload()
        version_payload["goal"] = request_text or version_payload["goal"]
        return {
            "name": _draft_name(request_text, "Агент поиска клиентов"),
            "category": category,
            "description": request_text,
            "metadata": _metadata(request_text, category, ["prospectingleads", "business_profile"]),
            "version_payload": version_payload,
            "summary": _summary(category, ["prospectingleads", "business_profile"], version_payload["steps"]),
        }

    sources = _sources_for_category(category)
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
    return {
        "name": _draft_name(request_text, _default_name_for_category(category)),
        "category": category,
        "description": request_text,
        "metadata": _metadata(request_text, category, sources),
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


def _communications_compilation(request_text: str) -> Dict[str, Any]:
    sources = ["appointments", "services", "packages", "business_profile"]
    steps = [
        {
            "key": "collect_audience",
            "type": "artifact",
            "title": "Собрать клиентов с записью",
            "artifact_type": "communications_audience",
            "payload": {
                "status": "draft",
                "trigger": "appointment.reminder.before",
                "audience": "clients_with_upcoming_appointments",
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
                "message_goal": "appointment_reminder_with_package_offer",
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
                "frequency_cap_required": True,
            },
        },
        {
            "key": "approve_message",
            "type": "approval",
            "title": "Подтвердить шаблон и отправку",
            "approval_type": "communications_send",
        },
        {
            "key": "send_message",
            "type": "artifact",
            "title": "Отправить через разрешённый канал",
            "artifact_type": "communications_send_queue",
            "payload": {
                "status": "pending_approval",
                "capability": "communications.send",
                "external_dispatch_performed": False,
                "delivery_state": "not_dispatched",
            },
        },
        {
            "key": "record_outcome",
            "type": "artifact",
            "title": "Записать результат",
            "artifact_type": "communications_outcomes",
            "payload": {
                "status": "pending_delivery",
                "outcomes": [],
            },
        },
    ]
    version_payload = {
        "goal": request_text or "Напоминать клиентам о записи и сообщать про пакетное предложение",
        "inputs_schema": {
            "type": "object",
            "properties": {
                "trigger": {"type": "string", "default": "appointment.reminder.before"},
                "audience": {"type": "string", "default": "clients_with_upcoming_appointments"},
                "frequency_cap": {"type": "string", "default": "one_message_per_client_per_appointment"},
                "daily_cap": {"type": "integer", "default": 10},
            },
        },
        "steps": steps,
        "capability_allowlist": [
            "appointments.read",
            "communications.draft",
            "communications.send_reminder",
            "communications.send_offer",
        ],
        "approval_policy": {
            "required_for": ["first_run", "template", "mass_send", "external_delivery"],
            "first_run": "manual_approval_required",
            "template": "manual_approval_required",
            "mass_send": "manual_approval_required",
            "external_delivery": "manual_approval_required",
        },
        "output_schema": {
            "type": "object",
            "properties": {
                "drafts": {"type": "array"},
                "delivery_report": {"type": "object"},
                "outcomes": {"type": "array"},
            },
        },
        "limits": {
            "frequency_cap": "one_message_per_client_per_appointment",
            "daily_cap": 10,
            "external_send_requires_approval": True,
        },
        "trigger": "appointment.reminder.before",
        "audience": "clients_with_upcoming_appointments",
        "data_sources": sources,
    }
    metadata = _metadata(request_text, "communications", sources)
    metadata["trigger"] = "appointment.reminder.before"
    metadata["audience"] = "clients_with_upcoming_appointments"
    metadata["limits"] = version_payload["limits"]
    metadata["communication_agent_is_blueprint_category"] = True
    return {
        "name": _draft_name(request_text, "Агент напоминаний о записи"),
        "category": "communications",
        "description": request_text,
        "metadata": metadata,
        "version_payload": version_payload,
        "summary": _summary("communications", sources, steps)
        | {
            "trigger": "appointment.reminder.before",
            "audience": "clients_with_upcoming_appointments",
            "capability_allowlist": version_payload["capability_allowlist"],
            "limits": version_payload["limits"],
            "output_schema": version_payload["output_schema"],
        },
    }
