from __future__ import annotations

import json
import sys
from typing import Any, Callable

from services.agent_compiler_registry import (
    allowed_compiler_capabilities,
    allowed_compiler_connectors,
    allowed_compiler_destinations,
    allowed_compiler_sources,
    allowed_compiler_triggers,
    compiled_template_prompt_lines,
    get_compiled_agent_template,
    infer_compiled_template_key,
)
from services.gigachat_client import analyze_text_with_gigachat


IntentGenerator = Callable[[str, str, str], str]


def infer_agent_workflow_intent(
    description: str,
    *,
    business_id: str = "",
    user_id: str = "",
    planner_context: dict[str, Any] | None = None,
    intent_generator: IntentGenerator | None = None,
) -> dict[str, Any]:
    text = str(description or "").strip()
    if not text:
        return {"status": "empty_description", "intent": {}, "source": "none"}
    generator = intent_generator or _default_intent_generator
    try:
        raw = generator(_build_agent_compiler_prompt(text, planner_context=planner_context), business_id, user_id)
    except Exception:
        return {
            "status": "llm_unavailable",
            "intent": {},
            "source": "gigachat",
            "error": str(sys.exc_info()[1]),
        }
    parsed = _parse_json_object(raw)
    if not parsed:
        return {
            "status": "invalid_json",
            "intent": {},
            "source": "gigachat",
            "raw_preview": str(raw or "")[:500],
        }
    intent = _sanitize_intent(parsed)
    if not intent:
        return {
            "status": "unsupported_intent",
            "intent": {},
            "source": "gigachat",
            "raw": parsed,
        }
    return {
        "status": "compiled_intent",
        "intent": intent,
        "source": "gigachat",
        "raw": parsed,
    }


def _default_intent_generator(prompt: str, business_id: str, user_id: str) -> str:
    return analyze_text_with_gigachat(
        prompt,
        task_type="agent_compiler",
        business_id=business_id,
        user_id=user_id,
    )


def _build_agent_compiler_prompt(description: str, *, planner_context: dict[str, Any] | None = None) -> str:
    context = planner_context if isinstance(planner_context, dict) else {}
    return "\n".join(
        [
            "Ты compiler intent extractor для LocalOS AI agents.",
            "Не выполняй задачу пользователя. Верни только JSON без markdown.",
            "LocalOS сам проверит capabilities, approvals, billing, limits и providers.",
            "Работай только внутри LocalOS/OpenClaw policy envelope ниже.",
            "",
            "Схема JSON:",
            "{",
            '  "trigger": "manual.run | schedule.daily | telegram.message.received",',
            '  "compiled_template_key": "one of supported templates below or empty string",',
            '  "source": "google_sheets | telegram | manual",',
            '  "destination": "localos_finance | google_sheets | telegram | communications | manual",',
            '  "read_capability": "google_sheets.read_rows | communications.draft | empty string",',
            '  "write_capability": "finance.transaction.create | sheets.append_row_request | communications.draft | communications.send_reminder | communications.send_offer | empty string",',
            '  "required_connectors": ["google_sheets"],',
            '  "approval_reasons": ["external_write", "localos_finance_write", "mass_send", "ambiguous_data"],',
            '  "limits": {"max_items_per_run": 100},',
            '  "clarifying_questions": ["..."],',
            '  "confidence": 0.0',
            "}",
            "",
            "Supported compiled templates:",
            *compiled_template_prompt_lines(),
            "",
            "LocalOS/OpenClaw policy envelope:",
            _planner_context_prompt_block(context),
            "",
            "Правила:",
            "- Если задача совпадает с template, заполни compiled_template_key.",
            "- Для чтения Google Sheets используй google_sheets.read_rows.",
            "- Для записи строки в Google Sheets используй sheets.append_row_request.",
            "- Для создания доходов/расходов/оплат/транзакций в LocalOS используй finance.transaction.create.",
            "- Для черновика публикации, ответа или сообщения используй communications.draft.",
            "- Для сообщений клиентам используй communications.draft и send capability только если пользователь просит отправку.",
            "- Любая запись, отправка, публикация, платеж и массовое действие требует approval_reasons.",
            "- Если нужны подключения, перечисли business-facing providers: google_sheets, telegram, localos_finance, maton, composio.",
            "- Если данных не хватает, добавь clarifying_questions, но всё равно заполни лучший безопасный draft intent.",
            "- Если envelope показывает missing_connections, не считай агента готовым: добавь clarifying_questions или required_connectors.",
            "- Если envelope показывает forbidden/unsupported, не придумывай обходные инструменты.",
            "- Не возвращай capabilities, connectors, triggers или destinations вне поддержанного списка.",
            "",
            f"Описание пользователя:\n{description[:3000]}",
        ]
    )


def _planner_context_prompt_block(context: dict[str, Any]) -> str:
    if not context:
        return "{}"
    allowed = {
        "schema": context.get("schema"),
        "purpose": context.get("purpose"),
        "category": context.get("category"),
        "business_scope": context.get("business_scope") if isinstance(context.get("business_scope"), dict) else {},
        "allowed_capabilities": context.get("allowed_capabilities") if isinstance(context.get("allowed_capabilities"), list) else [],
        "required_bindings": context.get("required_bindings") if isinstance(context.get("required_bindings"), list) else [],
        "connection_state": context.get("connection_state") if isinstance(context.get("connection_state"), dict) else {},
        "forbidden_action_classes": context.get("forbidden_action_classes") if isinstance(context.get("forbidden_action_classes"), list) else [],
        "approval_required_action_classes": (
            context.get("approval_required_action_classes") if isinstance(context.get("approval_required_action_classes"), list) else []
        ),
        "billing": context.get("billing") if isinstance(context.get("billing"), dict) else {},
        "output_contract": context.get("output_contract") if isinstance(context.get("output_contract"), dict) else {},
        "feasibility_status": context.get("feasibility_status"),
        "next_action": context.get("next_action"),
    }
    return json.dumps(allowed, ensure_ascii=False, sort_keys=True)[:6000]


def _parse_json_object(value: Any) -> dict[str, Any]:
    raw = str(value or "").strip()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        start = raw.find("{")
        end = raw.rfind("}") + 1
        if start < 0 or end <= start:
            return {}
        try:
            parsed = json.loads(raw[start:end])
        except Exception:
            return {}
    return parsed if isinstance(parsed, dict) else {}


def _sanitize_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        clean = str(item or "").strip()
        if clean:
            result.append(clean)
    return result[:12]


def _sanitize_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _sanitize_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _sanitize_intent(parsed: dict[str, Any]) -> dict[str, Any]:
    allowed_sources = allowed_compiler_sources()
    allowed_destinations = allowed_compiler_destinations()
    allowed_capabilities = allowed_compiler_capabilities()
    allowed_connectors = allowed_compiler_connectors()
    allowed_triggers = allowed_compiler_triggers()
    template_key = str(parsed.get("compiled_template_key") or "").strip()
    template = get_compiled_agent_template(template_key)
    source = str(parsed.get("source") or "").strip().lower()
    destination = str(parsed.get("destination") or "").strip().lower()
    if template:
        source = str(template.get("source") or source)
        destination = str(template.get("destination") or destination)
    if source not in allowed_sources or destination not in allowed_destinations:
        return {}
    read_capability = str(parsed.get("read_capability") or "").strip()
    write_capability = str(parsed.get("write_capability") or "").strip()
    if template:
        read_capability = str(template.get("read_capability") or read_capability)
        write_capability = str(template.get("write_capability") or write_capability)
    if read_capability and read_capability not in allowed_capabilities:
        read_capability = ""
    if write_capability and write_capability not in allowed_capabilities:
        write_capability = ""
    if not template_key:
        template_key = infer_compiled_template_key(source, destination, read_capability, write_capability)
    limits = parsed.get("limits") if isinstance(parsed.get("limits"), dict) else {}
    max_items = _sanitize_int(limits.get("max_items_per_run"), 100)
    max_items = max(1, min(max_items, 500))
    trigger = str(parsed.get("trigger") or "manual.run").strip()
    if template and template.get("trigger"):
        trigger = str(template.get("trigger") or trigger)
    if trigger not in allowed_triggers:
        trigger = "manual.run"
    confidence = _sanitize_float(parsed.get("confidence"), 0.0)
    confidence = max(0.0, min(confidence, 1.0))
    connectors = _sanitize_list(parsed.get("required_connectors"))
    if template and not connectors:
        connectors = [str(item) for item in (template.get("required_connectors") or [])]
    connectors = [item for item in connectors if item in allowed_connectors][:12]
    approval_reasons = _sanitize_list(parsed.get("approval_reasons"))
    if template and not approval_reasons:
        approval_reasons = [str(item) for item in (template.get("approval_reasons") or []) if str(item or "").strip()]
    return {
        "trigger": trigger,
        "compiled_template_key": template_key,
        "source": source,
        "destination": destination,
        "read_capability": read_capability,
        "write_capability": write_capability,
        "required_connectors": connectors,
        "approval_reasons": approval_reasons,
        "limits": {"max_items_per_run": max_items},
        "clarifying_questions": _sanitize_list(parsed.get("clarifying_questions"))[:3],
        "confidence": confidence,
    }
