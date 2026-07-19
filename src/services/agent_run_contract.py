from __future__ import annotations

from datetime import date, datetime, time
from typing import Any


RESERVED_AGENT_INPUT_FIELDS = {
    "approval_required_for_external_actions",
    "blueprint_id",
    "blueprint_version_id",
    "business_id",
    "capability_allowlist",
    "category",
    "city",
    "connector_action_handlers",
    "dashboard_source",
    "external_side_effects_allowed",
    "files",
    "goal",
    "google_sheets",
    "integration_id",
    "intent",
    "limit",
    "openclaw_action_plan",
    "openclaw_preview_routes",
    "policy_envelope",
    "preview_context",
    "preview_mode",
    "provider_bindings",
    "required_connectors",
    "schedule_date",
    "schedule_time",
    "scheduled_at",
    "schema",
    "sheet_name",
    "source",
    "source_event",
    "source_ids",
    "telegram",
    "tenant_id",
    "timezone",
    "trace_id",
    "trigger",
    "trigger_event_id",
    "spreadsheet_id",
}


def public_agent_input_schema(schema: Any) -> dict[str, Any]:
    value = schema if isinstance(schema, dict) else {}
    properties = value.get("properties") if isinstance(value.get("properties"), dict) else {}
    public_properties = {
        str(key): dict(field)
        for key, field in properties.items()
        if str(key) not in RESERVED_AGENT_INPUT_FIELDS and isinstance(field, dict)
    }
    required = [
        str(key)
        for key in value.get("required", [])
        if str(key) in public_properties
    ] if isinstance(value.get("required"), list) else []
    return {
        "type": "object",
        "properties": public_properties,
        "required": required,
        "additionalProperties": False,
    }


def effective_agent_input_schema(schema: Any, steps: Any) -> dict[str, Any]:
    result = public_agent_input_schema(schema)
    step_items = steps if isinstance(steps, list) else []
    creates_content_plan_draft = any(
        isinstance(step, dict) and str(step.get("capability") or "") == "content_plan.item.create_draft"
        for step in step_items
    )
    if creates_content_plan_draft:
        result["properties"].setdefault(
            "scheduled_for",
            {
                "type": "string",
                "format": "date",
                "title": "Дата в контент-плане",
                "description": "Выберите будущую дату, на которую сохранить черновик.",
            },
        )
        if "scheduled_for" not in result["required"]:
            result["required"].append("scheduled_for")
    return result


def validate_agent_run_input(schema: Any, payload: Any, steps: Any = None) -> dict[str, Any]:
    public_schema = effective_agent_input_schema(schema, steps)
    values = payload if isinstance(payload, dict) else {}
    errors: list[dict[str, str]] = []
    normalized: dict[str, Any] = {}
    properties = public_schema["properties"]

    for key in public_schema["required"]:
        if key not in values or values.get(key) in (None, "", []):
            errors.append({"field": key, "code": "required", "message": "Заполните обязательное поле."})

    for key, raw_value in values.items():
        if key in RESERVED_AGENT_INPUT_FIELDS:
            continue
        field = properties.get(key)
        if not isinstance(field, dict):
            errors.append({"field": str(key), "code": "unknown", "message": "Поле не поддерживается этой версией агента."})
            continue
        value, field_error = _normalize_field_value(raw_value, field)
        if field_error:
            errors.append({"field": str(key), "code": "invalid", "message": field_error})
            continue
        if "enum" in field and isinstance(field.get("enum"), list) and value not in field["enum"]:
            errors.append({"field": str(key), "code": "enum", "message": "Выберите одно из доступных значений."})
            continue
        normalized[str(key)] = value

    for key, field in properties.items():
        if key not in normalized and key not in values and "default" in field:
            normalized[key] = field.get("default")

    return {
        "valid": not errors,
        "errors": errors,
        "input": normalized,
        "public_schema": public_schema,
    }


def _normalize_field_value(value: Any, field: dict[str, Any]) -> tuple[Any, str]:
    field_type = str(field.get("type") or "string")
    if value is None:
        return None, ""
    if field_type == "string":
        text = str(value).strip()
        format_name = str(field.get("format") or "")
        try:
            if format_name == "date":
                date.fromisoformat(text)
            elif format_name == "time":
                time.fromisoformat(text)
            elif format_name == "date-time":
                datetime.fromisoformat(text.replace("Z", "+00:00"))
        except ValueError:
            return value, "Укажите корректные дату или время."
        return text, ""
    if field_type == "integer":
        try:
            return int(value), ""
        except (TypeError, ValueError):
            return value, "Укажите целое число."
    if field_type == "number":
        try:
            return float(value), ""
        except (TypeError, ValueError):
            return value, "Укажите число."
    if field_type == "boolean":
        if isinstance(value, bool):
            return value, ""
        if str(value).lower() in {"true", "1", "yes", "on"}:
            return True, ""
        if str(value).lower() in {"false", "0", "no", "off"}:
            return False, ""
        return value, "Выберите да или нет."
    if field_type == "array":
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()], ""
        if isinstance(value, str):
            return [item.strip() for item in value.splitlines() if item.strip()], ""
        return value, "Укажите значения списком, по одному в строке."
    return value, "Тип поля не поддерживается."
