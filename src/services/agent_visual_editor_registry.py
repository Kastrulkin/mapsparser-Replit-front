from copy import deepcopy
from typing import Any, Dict, List


VISUAL_EDITOR_REGISTRY: Dict[str, Any] = {
    "schema": "localos_agent_visual_editor_registry_v1",
    "triggers": [
        {"key": "manual", "title": "По команде", "trigger": "manual.run", "execution_mode": "manual"},
        {"key": "daily", "title": "Каждый день", "trigger": "schedule.daily", "execution_mode": "scheduled"},
        {"key": "weekly", "title": "Раз в неделю", "trigger": "schedule.weekly", "execution_mode": "scheduled"},
    ],
    "sources": [
        {"key": "business_profile", "title": "Профиль бизнеса", "kind": "internal", "source": "business_profile"},
        {"key": "reviews", "title": "Отзывы", "kind": "internal", "source": "external_reviews"},
        {"key": "services", "title": "Услуги", "kind": "internal", "source": "services"},
        {"key": "appointments", "title": "Записи", "kind": "internal", "source": "appointments"},
        {"key": "finance", "title": "Финансовые показатели", "kind": "internal", "source": "finance"},
        {"key": "content", "title": "Контент и задачи", "kind": "internal", "source": "content"},
        {"key": "partnerships", "title": "Партнёрства", "kind": "internal", "source": "partnerships"},
        {"key": "google_sheets", "title": "Google Sheets — только чтение", "kind": "external_read", "source": "google_sheets"},
    ],
    "checks": [
        {"key": "required_data", "title": "Остановиться, если данных нет", "check": "required_data"},
        {"key": "deduplicate", "title": "Убрать повторы", "check": "deduplicate"},
        {"key": "limit_items", "title": "Ограничить объём", "check": "limit_items"},
    ],
    "ai_presets": [
        {"key": "owner_digest", "title": "Сводка владельцу", "output_schema": "owner_digest_v1"},
        {"key": "negative_review_reply_drafts", "title": "Черновики ответов на отзывы", "output_schema": "review_reply_drafts_v1"},
        {"key": "service_seo_audit", "title": "SEO-проверка услуг", "output_schema": "service_seo_audit_v1"},
        {"key": "card_post_drafts", "title": "Три черновика новостей", "output_schema": "card_post_drafts_v1"},
        {"key": "tomorrow_booking_risks", "title": "Риски записей на завтра", "output_schema": "tomorrow_booking_risks_v1"},
        {"key": "sheet_business_digest", "title": "Сводка строк таблицы", "output_schema": "sheet_business_digest_v1"},
    ],
    "approvals": [
        {"key": "none", "title": "Не требуется для внутреннего результата"},
        {"key": "manual_review", "title": "Проверить результат человеком", "approval_type": "manual_result_review"},
    ],
    "results": [
        {"key": "internal_result", "title": "Сохранить результат в LocalOS", "artifact_type": "agent_final_result"},
        {"key": "review_queue", "title": "Сохранить в очередь проверки", "artifact_type": "agent_final_result"},
    ],
    "limits": {
        "max_items_per_run": {"title": "Элементов за запуск", "minimum": 1, "maximum": 500, "default": 100},
        "max_model_calls_per_run": {"title": "AI-шагов за запуск", "minimum": 1, "maximum": 1, "default": 1},
    },
    "forbidden_fields": [
        "code",
        "provider",
        "provider_action_ref",
        "capability",
        "task_key",
        "prompt",
        "autonomous_external_write_allowed",
        "autonomous_localos_write_allowed",
    ],
}


def visual_editor_registry() -> Dict[str, Any]:
    return deepcopy(VISUAL_EDITOR_REGISTRY)


def validate_visual_editor_settings(settings: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[Dict[str, str]] = []
    allowed_fields = {
        "execution_mode",
        "schedule",
        "trigger_key",
        "source_keys",
        "check_keys",
        "ai_preset_key",
        "approval_key",
        "result_preset_key",
        "limits",
    }
    for field in settings:
        if field not in allowed_fields:
            errors.append({"field": field, "code": "field_not_editable", "message": "Поле нельзя менять в безопасном редакторе."})
    _validate_selected_keys(errors, settings, "trigger_key", "triggers", multiple=False)
    _validate_selected_keys(errors, settings, "source_keys", "sources", multiple=True)
    _validate_selected_keys(errors, settings, "check_keys", "checks", multiple=True)
    _validate_selected_keys(errors, settings, "ai_preset_key", "ai_presets", multiple=False)
    _validate_selected_keys(errors, settings, "approval_key", "approvals", multiple=False)
    _validate_selected_keys(errors, settings, "result_preset_key", "results", multiple=False)
    limits = settings.get("limits") if isinstance(settings.get("limits"), dict) else {}
    for key, value in limits.items():
        contract = VISUAL_EDITOR_REGISTRY["limits"].get(key)
        if not contract:
            errors.append({"field": f"limits.{key}", "code": "limit_not_registered", "message": "Лимит не зарегистрирован."})
            continue
        if not isinstance(value, int) or isinstance(value, bool) or value < contract["minimum"] or value > contract["maximum"]:
            errors.append({"field": f"limits.{key}", "code": "limit_out_of_range", "message": "Значение лимита вне безопасного диапазона."})
    return {"valid": not errors, "errors": errors}


def apply_visual_editor_settings(version_payload: Dict[str, Any], settings: Dict[str, Any]) -> Dict[str, Any]:
    validation = validate_visual_editor_settings(settings)
    if not validation["valid"]:
        raise ValueError("Invalid visual editor settings")
    result = deepcopy(version_payload)
    trigger = _selected("triggers", str(settings.get("trigger_key") or ""))
    if trigger:
        result["trigger"] = trigger["trigger"]
        result["execution_mode"] = trigger["execution_mode"]
    source_keys = settings.get("source_keys") if isinstance(settings.get("source_keys"), list) else []
    sources = [_selected("sources", str(key)) for key in source_keys]
    sources = [item for item in sources if item]
    check_keys = settings.get("check_keys") if isinstance(settings.get("check_keys"), list) else []
    checks = [_selected("checks", str(key)) for key in check_keys]
    checks = [item for item in checks if item]
    ai_preset = _selected("ai_presets", str(settings.get("ai_preset_key") or ""))
    approval = _selected("approvals", str(settings.get("approval_key") or "none"))
    result_preset = _selected("results", str(settings.get("result_preset_key") or "internal_result"))
    if sources and ai_preset and result_preset:
        steps, capabilities, bindings = _build_registered_steps(sources, checks, ai_preset, approval, result_preset)
        result["steps"] = steps
        result["capability_allowlist"] = capabilities
        result["required_integration_bindings"] = bindings
    safe_limits = deepcopy(result.get("limits") if isinstance(result.get("limits"), dict) else {})
    safe_limits.update(settings.get("limits") if isinstance(settings.get("limits"), dict) else {})
    safe_limits["autonomous_external_write_allowed"] = False
    safe_limits["autonomous_localos_write_allowed"] = False
    safe_limits["duplicate_policy"] = "idempotency_key_required"
    result["limits"] = safe_limits
    max_items = safe_limits.get("max_items_per_run")
    for step in result.get("steps") if isinstance(result.get("steps"), list) else []:
        if not isinstance(step, dict):
            continue
        payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
        if max_items and (
            step.get("bounded_model_call") is True
            or str(step.get("capability") or "") in {"google_sheets.read_rows", "appointments.read"}
        ):
            payload["max_items"] = max_items
            if str(step.get("capability") or "") == "google_sheets.read_rows":
                payload["limit"] = max_items
            step["payload"] = payload
    return result


def _build_registered_steps(
    sources: List[Dict[str, Any]],
    checks: List[Dict[str, Any]],
    ai_preset: Dict[str, Any],
    approval: Dict[str, Any],
    result_preset: Dict[str, Any],
) -> tuple[List[Dict[str, Any]], List[str], List[Dict[str, Any]]]:
    steps = []
    capabilities = []
    bindings = []
    source_scope = [str(item["source"]) for item in sources]
    if any(item["key"] == "google_sheets" for item in sources):
        capabilities.append("google_sheets.read_rows")
        bindings.append(
            {
                "key": "google_sheets_read",
                "provider": "google_sheets",
                "direction": "external_read",
                "required": True,
                "approval_required": False,
                "required_config": ["spreadsheet_id", "sheet_name"],
                "default_config": {"sheet_name": "Sheet1"},
                "capability": "google_sheets.read_rows",
            }
        )
        steps.append(
            {
                "key": "read_google_sheets",
                "type": "capability",
                "title": "Прочитать Google Sheets",
                "capability": "google_sheets.read_rows",
                "requires_approval": False,
                "payload": {"integration_binding": "google_sheets_read", "provider_write_performed": False},
                "provider": "openclaw",
                "provider_action_ref": "openclaw.google_sheets.read_rows",
            }
        )
    if any(item["key"] == "appointments" for item in sources):
        capabilities.append("appointments.read")
        steps.append(
            {
                "key": "read_tomorrow_appointments",
                "type": "capability",
                "title": "Прочитать записи на завтра",
                "capability": "appointments.read",
                "requires_approval": False,
                "payload": {"date_range": "tomorrow", "provider_write_performed": False},
            }
        )
    internal_scope = [item for item in source_scope if item not in {"google_sheets", "appointments"}]
    if internal_scope:
        steps.insert(
            0,
            {
                "key": "collect_registered_sources",
                "type": "artifact",
                "title": "Собрать разрешённые данные",
                "artifact_type": "agent_input_plan",
                "payload": {"sources": internal_scope, "source_scope": "registered_business_sources_only"},
            },
        )
    for check in checks:
        steps.append(
            {
                "key": f"check_{check['key']}",
                "type": "artifact",
                "title": check["title"],
                "artifact_type": "registered_workflow_check",
                "payload": {"check": check["check"], "source_scope": source_scope},
            }
        )
    steps.append(
        {
            "key": "prepare_bounded_result",
            "type": "artifact",
            "title": ai_preset["title"],
            "artifact_type": "agent_output_draft",
            "bounded_model_call": True,
            "model_task_key": "agent_bounded_workflow_step",
            "model_preset": ai_preset["key"],
            "purpose": ai_preset["title"],
            "input_schema": "registered_business_sources_v1",
            "output_schema": ai_preset["output_schema"],
            "fallback": "deterministic_summary_then_human_review",
            "payload": {"format": ai_preset["output_schema"], "source_scope": source_scope, "external_dispatch_performed": False},
        }
    )
    if approval and approval.get("approval_type"):
        steps.append(
            {
                "key": "review_result",
                "type": "approval",
                "title": approval["title"],
                "approval_type": approval["approval_type"],
            }
        )
    steps.append(
        {
            "key": "save_internal_result",
            "type": "artifact",
            "title": result_preset["title"],
            "artifact_type": result_preset["artifact_type"],
            "payload": {"source_step": "prepare_bounded_result", "external_dispatch_performed": False, "delivery_state": "internal_only"},
        }
    )
    return steps, capabilities, bindings


def _selected(group: str, key: str) -> Dict[str, Any]:
    for item in VISUAL_EDITOR_REGISTRY[group]:
        if item["key"] == key:
            return deepcopy(item)
    return {}


def _validate_selected_keys(
    errors: List[Dict[str, str]],
    settings: Dict[str, Any],
    field: str,
    group: str,
    *,
    multiple: bool,
) -> None:
    value = settings.get(field)
    if value in (None, "", []):
        return
    values = value if multiple and isinstance(value, list) else [value]
    if multiple and not isinstance(value, list):
        errors.append({"field": field, "code": "invalid_selection", "message": "Ожидается список зарегистрированных значений."})
        return
    allowed = {item["key"] for item in VISUAL_EDITOR_REGISTRY[group]}
    for item in values:
        if not isinstance(item, str) or item not in allowed:
            errors.append({"field": field, "code": "selection_not_registered", "message": "Выбрано незарегистрированное значение."})
