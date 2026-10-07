"""Shared, guarded application operations for creating agent blueprint drafts."""
from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any

from core.auth_helpers import verify_business_write_access
from services.agent_blueprint_draft_builder import build_agent_blueprint_draft
from services.agent_builder_billing import (
    AGENT_CREATION_ESTIMATED_CREDITS,
    build_agent_creation_cost_preview,
    charge_agent_creation_credits,
)
from services.agent_builder_session import build_agent_builder_state, preview_to_setup
from services.agent_version_store import insert_version
from services.agent_schedule_contract import describe_schedule
from services.operator_conversations import _row


def _inventory(cursor: Any, business_id: str) -> list[dict]:
    result: list[dict] = []
    cursor.execute(
        """SELECT id,business_id,provider,status,display_name,auth_ref,config_json
           FROM agent_integrations WHERE business_id=%s ORDER BY updated_at DESC,created_at DESC LIMIT 100""",
        (business_id,),
    )
    for raw in cursor.fetchall() or []:
        item = _row(cursor, raw)
        config = item.get("config_json")
        if isinstance(config, str):
            try:
                config = json.loads(config)
            except (TypeError, ValueError):
                config = {}
        result.append({"id": str(item.get("id") or ""), "provider": str(item.get("provider") or ""),
                       "status": str(item.get("status") or "active"),
                       "display_name": str(item.get("display_name") or item.get("provider") or ""),
                       "config": config if isinstance(config, dict) else {}, "auth_ref": str(item.get("auth_ref") or "")})
    try:
        cursor.execute(
            """SELECT id,source,display_name FROM externalbusinessaccounts
               WHERE business_id=%s AND is_active=TRUE
                 AND source IN ('maton','google_sheets','google_business','telegram_app')
               ORDER BY updated_at DESC LIMIT 50""",
            (business_id,),
        )
        for raw in cursor.fetchall() or []:
            item = _row(cursor, raw)
            source = str(item.get("source") or "")
            provider = {"telegram_app": "telegram", "google_business": "google_sheets"}.get(source, source)
            result.append({"id": str(item.get("id") or ""), "provider": provider, "status": "active",
                           "display_name": str(item.get("display_name") or source or provider),
                           "config": {"bot_mode": "business_bot"} if source == "telegram_app" else {"channel": "maton_bridge"} if source == "maton" else {},
                           "auth_ref": str(item.get("id") or ""), "inventory_source": "external_business_account",
                           "credential_source": source})
    except Exception:
        pass
    try:
        cursor.execute("SELECT telegram_bot_token FROM Businesses WHERE id=%s LIMIT 1", (business_id,))
        business = _row(cursor, cursor.fetchone())
        if str(business.get("telegram_bot_token") or "").strip():
            result.append({"id": "business_telegram_bot", "provider": "telegram", "status": "active",
                           "display_name": "Бот бизнеса", "config": {"bot_mode": "business_bot"}})
    except Exception:
        pass
    return result


def _selected_bindings(payload: dict, preview: dict, inventory: list[dict]) -> dict:
    raw = payload.get("selected_connection_bindings")
    if not isinstance(raw, dict):
        raw = payload.get("selected_bindings")
    if not isinstance(raw, dict):
        raw = {}
    summary = preview.get("connection_summary") if isinstance(preview.get("connection_summary"), dict) else {}
    allowed_by_key: dict[str, set[str]] = {}
    provider_by_key: dict[str, str] = {}
    single_by_key: dict[str, str] = {}
    for entry in summary.get("items") or []:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("key") or "").strip()
        connections = entry.get("connections") if isinstance(entry.get("connections"), list) else []
        allowed = {str(connection.get("id") or "").strip() for connection in connections if isinstance(connection, dict) and str(connection.get("id") or "").strip()}
        if key:
            allowed_by_key[key] = allowed
            provider_by_key[key] = str(entry.get("provider") or "")
            if len(allowed) == 1:
                single_by_key[key] = next(iter(allowed))
    by_id = {str(item.get("id") or ""): item for item in inventory}
    selected = {}
    for raw_key, raw_id in raw.items():
        key, integration_id = str(raw_key or "").strip(), str(raw_id or "").strip()
        item = by_id.get(integration_id)
        if not key or not integration_id or key not in allowed_by_key or (allowed_by_key[key] and integration_id not in allowed_by_key[key]) or not item:
            continue
        provider = provider_by_key.get(key) or str(item.get("provider") or "")
        selected[key] = {"integration_id": integration_id, "provider": provider,
                         "display_name": str(item.get("display_name") or provider),
                         "config": item.get("config") if isinstance(item.get("config"), dict) else {}}
    for key, integration_id in single_by_key.items():
        if key in selected or integration_id not in by_id:
            continue
        item = by_id[integration_id]
        provider = provider_by_key.get(key) or str(item.get("provider") or "")
        selected[key] = {"integration_id": integration_id, "provider": provider,
                         "display_name": str(item.get("display_name") or provider),
                         "config": item.get("config") if isinstance(item.get("config"), dict) else {},
                         "selection_source": "auto_single_connection"}
    return selected


def _missing_connection_choices(preview: dict, selected: dict) -> list[dict]:
    summary = preview.get("connection_summary") if isinstance(preview.get("connection_summary"), dict) else {}
    result = []
    for entry in summary.get("items") or []:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("key") or "").strip()
        connections = entry.get("connections") if isinstance(entry.get("connections"), list) else []
        if key and entry.get("action") == "choose_existing" and len(connections) > 1 and key not in selected:
            result.append({"key": key, "provider": str(entry.get("provider") or ""),
                           "title": str(entry.get("title") or entry.get("provider") or key),
                           "connection_count": len(connections)})
    return result


def _apply_bindings(metadata: dict, selected: dict) -> dict:
    if not selected:
        return metadata
    integration_ids = metadata.get("agent_integration_ids") if isinstance(metadata.get("agent_integration_ids"), list) else []
    capability_integrations = metadata.get("capability_integrations") if isinstance(metadata.get("capability_integrations"), dict) else {}
    binding_integrations = metadata.get("agent_binding_integrations") if isinstance(metadata.get("agent_binding_integrations"), dict) else {}
    custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
    for key, item in selected.items():
        integration_id, provider = str(item.get("integration_id") or "").strip(), str(item.get("provider") or "").strip()
        if not integration_id or not provider:
            continue
        if integration_id not in integration_ids:
            integration_ids.append(integration_id)
        capability_integrations[provider] = integration_id
        binding_integrations[key] = {"integration_id": integration_id, "provider": provider, "source": "direct_agent_draft"}
        config = item.get("config") if isinstance(item.get("config"), dict) else {}
        binding_config = {"integration_id": integration_id, **config}
        custom_process[key] = binding_config
        if provider in {"google_sheets", "telegram"}:
            custom_process[provider] = dict(binding_config)
    metadata["agent_integration_ids"] = integration_ids[-25:]
    metadata["capability_integrations"] = capability_integrations
    metadata["agent_binding_integrations"] = binding_integrations
    metadata["custom_process"] = custom_process
    return metadata


def _conditions(cursor, business_id: str, payload: dict) -> dict:
    """Pin the same reviewed domain conditions and schedule for API and Operator."""
    result = {}
    if "outreach_config" in payload:
        from services.outreach_continuation import normalize_config
        config = normalize_config(payload["outreach_config"])
        if config.get("version") != 2:
            raise ValueError("outreach_target_count_required")
        result["outreach_config"] = config
    schedule = payload.get("schedule") or {}
    if not isinstance(schedule, dict):
        raise ValueError("invalid_schedule")
    mode = payload.get("execution_mode") or ("scheduled" if schedule else "manual")
    if mode not in {"manual", "one_off", "scheduled"}:
        raise ValueError("invalid_execution_mode")
    result["execution_mode"] = mode
    if mode == "scheduled":
        from services.agent_schedule_contract import apply_schedule
        from services.business_input_settings import resolve
        changes = dict(schedule)
        for field, legacy in (("time", "schedule_time"), ("timezone", "schedule_timezone")):
            if payload.get(legacy) and field not in changes:
                changes[field] = payload[legacy]
        normalized = apply_schedule({}, changes, business_timezone=resolve(cursor, business_id).get("timezone"))
        result.update(schedule=normalized["schedule"], trigger=normalized["trigger"])
    else:
        result.update(schedule={}, trigger="manual.run")
    return result


def _outreach_version(version: dict, config: dict, description: str) -> dict:
    # A native compiled workflow, not a script with network access. The one
    # durable step delegates to the existing search/model/campaign services.
    return {**version, "goal": description,
            "steps": [{"key": "outreach", "type": "capability", "title": "Поиск и подготовка обращений",
                       "capability": "outreach.continue", "payload": {}}],
            "inputs_schema": {"type": "object", "properties": {}, "additionalProperties": False},
            "capability_allowlist": ["outreach.continue"],
            "approval_policy": {"required_for": [], "external_delivery": "separate_ai_rules_required"},
            "runtime_config": {"outreach_config": config}, "required_integration_bindings": []}


def _outreach_draft(description: str, config: dict, conditions: dict) -> dict:
    from services.agent_blueprint_draft_builder import _attach_compiled_metadata, _summary
    draft = build_agent_blueprint_draft(description, "outreach", use_ai=False)
    version = _outreach_version(draft["version_payload"], config, description)
    version.update(execution_mode=conditions["execution_mode"], trigger=conditions["trigger"], schedule=conditions["schedule"])
    draft["version_payload"] = version
    draft["summary"] = _summary("outreach", ["prospectingleads", "business_profile"], version["steps"])
    draft["summary"].update(capability_allowlist=version["capability_allowlist"], trigger=conditions["trigger"],
                            audience=config["audience"], approval_boundaries=["automation_conditions", "ai_sending_rules"],
                            outputs=["Новые подходящие компании, письма выбранных этапов и отчёт с подтверждениями"])
    _attach_compiled_metadata(draft["metadata"], version, "compiled_outreach_workflow_v1", "ai_sending_rules")
    draft["metadata"]["compiler_contract"].update(llm_usage="native_outreach_services", runtime_llm_required=True,
                                                   runtime_model_steps=["qualification", "drafting_and_review"])
    return draft


def _is_content_handoff_request(description: str) -> bool:
    text = str(description or "").lower()
    content = any(token in text for token in ("пост", "публикац", "контент"))
    telegram = any(token in text for token in ("telegram", "телеграм", "бот"))
    delivery = any(token in text for token in ("отправ", "передав", "присыл", "достав"))
    return content and telegram and delivery


def _content_handoff_draft(description: str, *, business_id: str, recipient_user_id: str, conditions: dict) -> dict:
    from services.agent_blueprint_draft_builder import _attach_compiled_metadata, _summary

    timezone_name = str((conditions.get("schedule") or {}).get("timezone") or "")
    schedule_time = str((conditions.get("schedule") or {}).get("time") or "")
    platforms = ["telegram", "vk", "max"]
    step = {
        "key": "send_due_content_to_telegram",
        "type": "capability",
        "title": "Передать готовые посты и фото в Telegram",
        "capability": "content.publish_handoff",
        "requires_approval": True,
        "required_approval_type": "content_handoff_activation",
        "payload": {
            "business_id": business_id,
            "recipient_user_id": recipient_user_id,
            "platforms": platforms,
            "lead_days": 1,
            "time": schedule_time,
            "timezone": timezone_name,
        },
    }
    version = {
        "goal": description,
        "execution_mode": "scheduled",
        "trigger": conditions["trigger"],
        "schedule": conditions["schedule"],
        "steps": [step],
        "inputs_schema": {"type": "object", "properties": {}, "additionalProperties": False},
        "capability_allowlist": ["content.publish_handoff"],
        "approval_policy": {
            "required_for": [],
            "content_handoff_activation": "one_time_exact_scope_consent",
        },
        "limits": {"max_posts_per_run": 100, "publication_status_changes": False},
        "output_schema": {"type": "object", "properties": {"deliveries": {"type": "array"}}},
        "required_integration_bindings": [],
    }
    draft = build_agent_blueprint_draft(description, "content", use_ai=False)
    draft["version_payload"] = version
    draft["summary"] = _summary("content", ["content_plan", "telegram_bot"], [step])
    draft["summary"].update(
        approval_boundaries=["exact_recipient_and_channels", "activation_consent"],
        outputs=["Квитанции доставки отдельно от публикации на площадках"],
        external_dispatch_performed=False,
    )
    _attach_compiled_metadata(draft["metadata"], version, "compiled_content_handoff_v1", "content_handoff_activation")
    return draft


def _outreach_builder_context(description: str, config: dict, conditions: dict) -> str:
    return description + "\nУсловия поручения: " + json.dumps({
        "источники поиска": config["queries"], "аудитория": config["audience"],
        "страна компаний": config["agency_country"], "продаваемое направление": config["sold_destination"],
        "проверка": "Найти новые подходящие компании с подтверждённым контактом; дубли не засчитывать",
        "результат": "Список компаний и отчёт; письма только для выбранных этапов",
        "количество": config["target_count"], "режим": config["mode"],
        "контроль": "Подтверждение условий; отправка только по отдельно согласованным AI-правилам",
        "расписание": conditions["schedule"], "запуск": conditions["execution_mode"],
    }, ensure_ascii=False)


def preview_creation(cursor: Any, *, business_id: str, user_id: str, actor_context: dict, payload: dict) -> dict:
    actor = dict(actor_context or {})
    if actor.get("session_kind") == "demo" or actor.get("impersonating") or actor.get("impersonated_by"):
        return {"status": "blocked", "code": "FORBIDDEN", "error": "Нужен обычный аккаунт владельца бизнеса."}
    allowed, _owner_id = verify_business_write_access(cursor, business_id, {**actor, "user_id": user_id, "is_active": actor.get("is_active", True)})
    if not allowed:
        return {"status": "blocked", "code": "FORBIDDEN", "error": "Недостаточно прав на изменение бизнеса."}
    description = str(payload.get("description") or "").strip()[:4000]
    handoff_requested = _is_content_handoff_request(description)
    conditions_payload = dict(payload)
    if handoff_requested and not isinstance(payload.get("schedule"), dict):
        from services.business_input_settings import resolve
        business_timezone = str(resolve(cursor, business_id).get("timezone") or "")
        if business_timezone:
            conditions_payload.update(execution_mode="scheduled", schedule={"time": "10:00", "timezone": business_timezone})
    try:
        conditions = _conditions(cursor, business_id, conditions_payload)
    except (ValueError, TypeError) as exc:
        return {"status": "clarification_required", "code": getattr(exc, "code", "CONDITIONS_INVALID"), "error": str(exc)}
    if handoff_requested:
        from services.business_input_settings import resolve
        business_timezone = str(resolve(cursor, business_id).get("timezone") or "")
        if (conditions.get("execution_mode") != "scheduled"
                or (conditions.get("schedule") or {}).get("time") != "10:00"
                or (conditions.get("schedule") or {}).get("timezone") != business_timezone):
            return {"status": "clarification_required", "code": "CONTENT_HANDOFF_SCHEDULE_REQUIRED",
                    "error": "Для передачи контента нужен ежедневный запуск в 10:00 по часовому поясу точки."}
    clone_metadata = {}
    if payload.get("clone_from_blueprint_id"):
        cursor.execute("SELECT business_id,metadata_json FROM agent_blueprints WHERE id=%s", (str(payload.get("clone_from_blueprint_id")),))
        source = _row(cursor, cursor.fetchone())
        if str(source.get("business_id") or "") != business_id:
            return {"status": "blocked", "blocked_reasons": ["clone_business_mismatch"]}
        source_metadata = source.get("metadata_json") if isinstance(source.get("metadata_json"), dict) else {}
        clone_metadata = {key: source_metadata[key] for key in ("agent_sources", "agent_integration_ids", "agent_integration_bindings", "agent_binding_provider_routes", "required_integration_bindings", "agent_setup") if key in source_metadata}
    if len(description) < 8:
        return {"status": "clarification_required", "code": "VALIDATION_ERROR", "error": "Опишите повторяющуюся работу, которую должен выполнять ИИ-сотрудник."}
    inventory = _inventory(cursor, business_id)
    config = conditions.get("outreach_config")
    builder_description = _outreach_builder_context(description, config, conditions) if config else description
    state = build_agent_builder_state([{"role": "user", "content": builder_description}],
        "outreach" if config else str(payload.get("category") or ""), use_ai=False, business_id=business_id,
        user_id=user_id, connected_integrations=inventory,
        compiled_draft=(
            _outreach_draft(description, config, conditions) if config else
            _content_handoff_draft(description, business_id=business_id, recipient_user_id=user_id, conditions=conditions) if handoff_requested else None
        ))
    preview = state.get("preview") if isinstance(state.get("preview"), dict) else {}
    if config:
        preview["manual_control"] = "Условия согласуются до запуска. AI-отправка требует отдельного действующего разрешения на точные правила; повторное подтверждение неизменных правил не требуется."
        preview["reviewed_conditions"] = conditions
    feasibility = preview.get("feasibility") if isinstance(preview.get("feasibility"), dict) else {}
    setup_flow = preview.get("setup_flow") if isinstance(preview.get("setup_flow"), dict) else {}
    if feasibility.get("status") == "forbidden":
        return {"status": "blocked", "code": "AGENT_REQUEST_FORBIDDEN", "error": "Такую автоматизацию нельзя создавать по правилам LocalOS.", "feasibility": feasibility, "setup_flow": setup_flow}
    selected_bindings = _selected_bindings(payload, preview, inventory)
    missing_connections = _missing_connection_choices(preview, selected_bindings)
    if missing_connections:
        return {"status": "clarification_required", "code": "AGENT_CONNECTION_CHOICE_REQUIRED", "error": "Выберите существующее подключение для каждого обязательного шага.", "missing_connection_choices": missing_connections, "connection_summary": preview.get("connection_summary") or {}, "setup_flow": setup_flow}
    from api.agent_builder_api import _missing_required_provider_routes, _required_provider_route_bindings, _selected_provider_routes
    selected_routes = _selected_provider_routes(payload, preview, inventory)
    missing_routes = _missing_required_provider_routes(preview, selected_routes)
    if missing_routes:
        return {"status": "clarification_required", "code": "AGENT_PROVIDER_ROUTE_REQUIRED", "error": "Выберите provider route для обязательных шагов.", "missing_provider_routes": missing_routes,
                "connection_readiness": preview.get("connection_readiness") or {}, "setup_flow": setup_flow}
    required_routes = _required_provider_route_bindings(preview)
    if required_routes and not bool(payload.get("accepted_provider_routes")):
        return {"status": "clarification_required", "code": "AGENT_PROVIDER_ROUTES_CONFIRMATION_REQUIRED", "error": "Подтвердите выбранные provider routes.",
                "selected_provider_routes": selected_routes, "connection_readiness": preview.get("connection_readiness") or {},
                "setup_flow": setup_flow, "next_step": "accept_provider_routes"}
    return {"status": "ready", "conditions": conditions, "preview": preview, "feasibility": feasibility, "setup_flow": setup_flow,
            "selected_bindings": selected_bindings, "selected_provider_routes": selected_routes,
            "content_handoff_requested": handoff_requested,
            "clone_metadata": clone_metadata,
            "planner_context": preview.get("openclaw_planner_context") if isinstance(preview.get("openclaw_planner_context"), dict) else {},
            "planner_loop": preview.get("openclaw_planner_loop") if isinstance(preview.get("openclaw_planner_loop"), dict) else {},
            "connection_inventory": inventory}


def prepare_creation(cursor: Any, *, business_id: str, user_id: str, actor_context: dict, payload: dict) -> dict:
    preview = preview_creation(cursor, business_id=business_id, user_id=user_id, actor_context=actor_context, payload=payload)
    if preview.get("status") != "ready":
        return preview
    from services.agent_builder_billing import build_paid_action_preflight
    paid = build_paid_action_preflight(cursor, business_id=business_id, user_id=user_id,
        action_key="agent_creation", estimated_credits=AGENT_CREATION_ESTIMATED_CREDITS)
    if paid.get("status") != "ready":
        return {"status": "blocked", "code": "AGENT_CREATION_BILLING_BLOCKED", "error": "Создание сейчас недоступно по кредитам.", "billing": paid}
    allowed_keys = ("name", "description", "category", "execution_mode", "schedule_time", "schedule_timezone",
                    "schedule", "outreach_config", "selected_connection_bindings", "selected_bindings",
                    "selected_provider_routes", "selected_routes", "accepted_provider_routes", "clone_from_blueprint_id", "use_ai_compiler")
    envelope_payload = {key: payload[key] for key in allowed_keys if key in payload}
    # Pin defaults in the approval so a later business timezone edit cannot
    # silently change what was reviewed. Hash ALL conditions, not just the title.
    conditions = preview.get("conditions") or {}
    if conditions:
        envelope_payload["execution_mode"] = conditions["execution_mode"]
        if conditions["execution_mode"] == "scheduled":
            envelope_payload["schedule"] = {**conditions["schedule"], "trigger": conditions["trigger"]}
        if conditions.get("outreach_config"):
            envelope_payload["outreach_config"] = conditions["outreach_config"]
    key_parts = json.dumps({"business_id": business_id, "user_id": user_id, "payload": envelope_payload}, ensure_ascii=False, sort_keys=True)
    request_key = hashlib.sha256(key_parts.encode("utf-8")).hexdigest()
    summary = f"Создать черновик ИИ-сотрудника: {str(payload.get('name') or 'Новый сценарий').strip()[:120]}"
    if conditions.get("schedule"):
        summary += "; " + describe_schedule(conditions["trigger"], conditions["schedule"])
    if conditions.get("outreach_config"):
        cfg = conditions["outreach_config"]
        mode_label = {"find_only": "поиск и проверка", "prepare_only": "подготовка писем", "auto_send": "подготовка и разрешённая отправка"}.get(cfg["mode"], cfg["mode"])
        summary += f"; {cfg['target_count']} новых подходящих компаний; страна: {cfg['agency_country']}; направление: {cfg['sold_destination']}; режим: {mode_label}; лимит поиска: {cfg['search_budget_cents']} центов, {cfg['max_search_calls']} запросов"
    envelope = {"business_id": business_id, "idempotency_key": request_key, "payload": envelope_payload}
    return {"status": "approval_required", "chat_response": f"{summary}. Оценка — около 3 кредитов за создание; черновик не будет запущен.",
            "approval": {"status": "pending", "capability": "agents.create", "summary": summary,
                         "envelope": envelope, "billing": build_agent_creation_cost_preview(), "paid_preflight": paid},
            "reviewed_conditions": conditions,
            "builder_preview": {"feasibility": preview.get("feasibility"), "setup_flow": preview.get("setup_flow"),
                                "connection_summary": preview.get("preview", {}).get("connection_summary"),
                                "connection_readiness": preview.get("preview", {}).get("connection_readiness"),
                                "selected_provider_routes": preview.get("selected_provider_routes")},
            "external_writes_performed": False}


def create_draft(cursor: Any, *, business_id: str, user_id: str, actor_context: dict, payload: dict, idempotency_key: str) -> dict:
    actor = dict(actor_context or {})
    if actor.get("session_kind") == "demo" or actor.get("impersonating") or actor.get("impersonated_by"):
        return {"status": "blocked", "blocked_reasons": ["access_denied"]}
    allowed, _owner_id = verify_business_write_access(cursor, business_id, {**actor, "user_id": user_id, "is_active": actor.get("is_active", True)})
    if not allowed:
        return {"status": "blocked", "blocked_reasons": ["access_denied"]}
    key = str(idempotency_key or "").strip()
    if not key:
        return {"status": "blocked", "blocked_reasons": ["idempotency_key_required"]}
    cursor.execute("SELECT pg_advisory_xact_lock(hashtext(%s))", (f"agent-create:{business_id}:{user_id}:{key}",))
    cursor.execute("SELECT id,metadata_json FROM agent_blueprints WHERE business_id=%s AND metadata_json->>'create_request_key'=%s LIMIT 1", (business_id, key))
    prior = _row(cursor, cursor.fetchone())
    if prior:
        metadata = prior.get("metadata_json") if isinstance(prior.get("metadata_json"), dict) else {}
        payload_digest = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
        if metadata.get("creation_input_hash") and metadata.get("creation_input_hash") != payload_digest:
            return {"status": "blocked", "blocked_reasons": ["idempotency_key_reused_with_different_input"]}
        return {"status": "completed", "blueprint_id": str(prior.get("id") or ""), "idempotent_replay": True,
                "chat_response": "Этот черновик уже создан. Повторно списывать кредиты не нужно.", "external_writes_performed": False}
    checked = preview_creation(cursor, business_id=business_id, user_id=user_id, actor_context=actor, payload=payload)
    if checked.get("status") != "ready":
        return {**checked, "status": "blocked" if checked.get("status") == "clarification_required" else checked.get("status")}
    description = str(payload.get("description") or "").strip()[:4000]
    blueprint_id = str(uuid.uuid5(uuid.NAMESPACE_URL, f"localos-agent-create:{business_id}:{user_id}:{key}"))
    planner_context = checked.get("planner_context") or {}
    conditions = checked.get("conditions") or _conditions(cursor, business_id, payload)
    draft = (_outreach_draft(description, conditions["outreach_config"], conditions) if conditions.get("outreach_config") else
        _content_handoff_draft(description, business_id=business_id, recipient_user_id=user_id, conditions=conditions)
        if checked.get("content_handoff_requested") else
        build_agent_blueprint_draft(description, str(payload.get("category") or ""),
            use_ai=bool(payload.get("use_ai_compiler")), business_id=business_id, user_id=user_id,
            planner_context=planner_context))
    billing = charge_agent_creation_credits(cursor, business_id=business_id, user_id=user_id,
        source_id=blueprint_id, description=description, channel="operator" if actor.get("operator_confirmation") else "agent_blueprint_draft")
    if billing.get("status") == "blocked":
        return {"status": "blocked", "blocked_reasons": [str(billing.get("code") or "agent_creation_billing_blocked")], "billing": billing}
    metadata = {**(checked.get("clone_metadata") if isinstance(checked.get("clone_metadata"), dict) else {}),
                **(draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {})}
    metadata["create_request_key"] = key
    metadata["creation_input_hash"] = hashlib.sha256(json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str).encode("utf-8")).hexdigest()
    metadata["original_request"] = description
    metadata["agent_builder_preview"] = checked.get("preview") or {}
    metadata["feasibility"] = checked.get("feasibility") or {}
    metadata["openclaw_planner_context"] = checked.get("planner_context") or {}
    metadata["openclaw_planner_loop"] = checked.get("planner_loop") or {}
    metadata["builder_setup_flow"] = checked.get("setup_flow") or {}
    metadata["agent_setup"] = preview_to_setup(checked.get("preview") or {})
    metadata["setup_completed"] = bool((checked.get("setup_flow") or {}).get("can_create_draft"))
    metadata["billing"] = billing
    metadata["execution_mode"] = str(payload.get("execution_mode") or "").strip().lower()
    custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
    version_payload = dict(draft.get("version_payload") if isinstance(draft.get("version_payload"), dict) else {})
    conditions = checked.get("conditions") or _conditions(cursor, business_id, payload)
    requested_mode = conditions["execution_mode"]
    metadata["execution_mode"] = requested_mode
    custom_process["trigger"] = conditions["trigger"]
    if conditions["schedule"]:
        custom_process["schedule"] = conditions["schedule"]
    else:
        custom_process.pop("schedule", None)
    if conditions.get("outreach_config"):
        version_payload = _outreach_version(version_payload, conditions["outreach_config"], description)
        custom_process["outreach_config"] = conditions["outreach_config"]
    metadata["custom_process"] = custom_process
    metadata["execution_mode_confirmed_at"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    metadata["execution_mode_confirmed_by_user_id"] = user_id
    if payload.get("clone_from_blueprint_id"):
        metadata["cloned_from_blueprint_id"] = str(payload.get("clone_from_blueprint_id"))
    metadata["builder"] = str(metadata.get("builder") or "direct_description_builder_v1")
    metadata["direct_draft_envelope"] = "localos_openclaw_policy_envelope_v1"
    metadata["required_connectors"] = ((checked.get("preview") or {}).get("required_connectors") or [])
    metadata = _apply_bindings(metadata, checked.get("selected_bindings") or {})
    from api.agent_builder_api import _apply_selected_provider_routes
    metadata = _apply_selected_provider_routes(metadata, checked.get("selected_provider_routes") or {})
    metadata["builder_selected_connection_bindings"] = checked.get("selected_bindings") or {}
    metadata["builder_selected_provider_routes"] = checked.get("selected_provider_routes") or {}
    metadata["builder_provider_routes_accepted"] = bool(payload.get("accepted_provider_routes"))
    metadata["agent_draft_summary"] = draft.get("summary") if isinstance(draft.get("summary"), dict) else {}
    version_payload["execution_mode"] = requested_mode
    version_payload["trigger"] = conditions["trigger"]
    version_payload["runtime_config"] = dict(custom_process)
    version_payload["schedule"] = custom_process.get("schedule") if isinstance(custom_process.get("schedule"), dict) else {}
    if conditions.get("outreach_config"):
        metadata["required_integration_bindings"] = []
    version_payload["required_integration_bindings"] = metadata.get("required_integration_bindings") if isinstance(metadata.get("required_integration_bindings"), list) else version_payload.get("required_integration_bindings") or []
    cursor.execute(
        """INSERT INTO agent_blueprints(id,business_id,name,category,description,status,created_by_user_id,metadata_json)
           VALUES(%s,%s,%s,%s,%s,'draft',%s,%s::jsonb)""",
        (blueprint_id, business_id, str(payload.get("name") or draft.get("name") or "Кастомный агент").strip()[:160],
         str(draft.get("category") or "custom").strip().lower(), str(draft.get("description") or description).strip(),
         user_id, json.dumps(metadata, ensure_ascii=False, default=str)),
    )
    version = insert_version(cursor, blueprint_id, version_payload, {"user_id": user_id})
    return {"status": "completed", "blueprint_id": blueprint_id,
            "name": str(payload.get("name") or draft.get("name") or "Кастомный агент"),
            "candidate_version": {"id": version.get("id"), "version_number": version.get("version_number"),
                                  "goal": version.get("goal"), "trigger": version.get("trigger")},
            "draft": {"category": draft.get("category"), "summary": draft.get("summary") if isinstance(draft.get("summary"), dict) else {}},
            "billing": billing, "setup_flow": checked.get("setup_flow"), "feasibility": checked.get("feasibility"),
            "connection_summary": (checked.get("preview") or {}).get("connection_summary") or {},
            "openclaw_planner_loop": checked.get("planner_loop") or {},
            "selected_connection_bindings": checked.get("selected_bindings") or {},
            "selected_provider_routes": checked.get("selected_provider_routes") or {},
            "chat_response": "Создал черновик ИИ-сотрудника. Проверьте сценарий и подключения перед включением.",
            "ui_actions": [{"type": "open_result", "label": "Проверить сценарий", "href": f"/dashboard/agents?blueprint_id={blueprint_id}"}],
            "active": False, "external_writes_performed": False}
