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
    request_text = _normalized_text(description)
    category = _normalized_category(preferred_category) or infer_blueprint_category(request_text)
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
    allowed = {"documents", "email", "tables", "outreach", "reviews", "partnerships", "booking", "services", "custom"}
    aliases = {
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
