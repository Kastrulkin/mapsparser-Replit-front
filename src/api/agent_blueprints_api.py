import json
import uuid
from datetime import datetime, timezone

from flask import Blueprint, Response, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.agent_blueprint_runner import (
    AgentBlueprintRunner,
    default_supervised_outreach_version_payload,
    parse_json_field,
    normalize_steps,
)
from services.agent_blueprint_orchestrator import build_agent_blueprint_orchestrator
from services.agent_blueprint_draft_builder import build_agent_blueprint_draft
from services.agent_builder_billing import charge_agent_creation_credits
from services.agent_builder_session import build_agent_builder_state, preview_to_setup
from services.agent_compiled_artifact import validate_compiled_artifact_candidate
from services.agent_blueprint_workspace import (
    build_agent_version_diff,
    build_blueprint_review,
    build_feedback_version_payload,
    build_learning_loop_summary,
    build_version_payload_from_row,
    normalize_agent_setup,
    normalize_agent_source,
    workspace_parse_json_field,
)
from services.agent_product_layer import (
    attach_persona_to_version,
    attach_product_agent_to_blueprint,
    collect_persona_agent_ids,
    parse_persona_row,
)
from services.agent_legacy_migration import apply_legacy_ai_agent_migration, build_legacy_ai_agent_migration_plan
from services.agent_source_ingestion import build_agent_source_from_upload
from services.agent_datahub import build_agent_datahub_catalog
from services.agent_provider_registry import (
    best_provider_route_state,
    connector_provider_routes,
    integration_execution_boundary,
    integration_provider_catalog,
)
from services.agent_integration_preflight import build_agent_integration_preflight
from services.agent_metrics import build_agent_metrics_summary
from api.agent_builder_api import (
    _apply_selected_provider_routes,
    _missing_required_provider_routes,
    _required_provider_route_bindings,
    _selected_provider_routes,
)


agent_blueprints_bp = Blueprint("agent_blueprints_api", __name__)


def _json_error(message: str, status: int, code: str):
    return jsonify({"success": False, "error": message, "code": code}), status


def _require_auth():
    user_data = require_auth_from_request()
    if not user_data:
        return None, _json_error("Authorization required", 401, "AUTH_REQUIRED")
    return user_data, None


def _user_id(user_data: dict) -> str:
    return str(user_data.get("user_id") or user_data.get("id") or "")


def _normalize_json_row(row: dict) -> dict:
    result = dict(row)
    for key in list(result.keys()):
        if key.endswith("_json"):
            fallback = [] if key in {"steps_json", "capability_allowlist_json"} else {}
            result[key] = parse_json_field(result.get(key), fallback)
    return result


def _load_personas_by_id(cursor, persona_ids: list[str]) -> dict:
    clean_ids = [item for item in persona_ids if item]
    if not clean_ids:
        return {}
    cursor.execute(
        """
        SELECT id, name, type, description, personality, identity, speech_style,
               restrictions_json, variables_json, is_active
        FROM AIAgents
        WHERE id = ANY(%s)
        """,
        (clean_ids,),
    )
    personas = {}
    for row in cursor.fetchall() or []:
        persona = parse_persona_row(dict(row))
        if persona:
            personas[persona["id"]] = persona
    return personas


def _require_business_access(cursor, business_id: str, user_data: dict):
    has_access, owner_id = verify_business_access(cursor, business_id, user_data)
    if not owner_id:
        return False, _json_error("Business not found", 404, "BUSINESS_NOT_FOUND")
    if not has_access:
        return False, _json_error("Forbidden", 403, "FORBIDDEN")
    return True, None


def _load_blueprint(cursor, blueprint_id: str):
    cursor.execute("SELECT * FROM agent_blueprints WHERE id = %s", (blueprint_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def _load_blueprint_version_for_blueprint(cursor, blueprint_id: str, version_id: str):
    cursor.execute(
        """
        SELECT *
        FROM agent_blueprint_versions
        WHERE id = %s
          AND blueprint_id = %s
        """,
        (version_id, blueprint_id),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _load_blueprint_version(cursor, version_id: str):
    cursor.execute("SELECT * FROM agent_blueprint_versions WHERE id = %s", (version_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def _load_latest_blueprint_version(cursor, blueprint_id: str):
    cursor.execute(
        """
        SELECT *
        FROM agent_blueprint_versions
        WHERE blueprint_id = %s
        ORDER BY version_number DESC
        LIMIT 1
        """,
        (blueprint_id,),
    )
    row = cursor.fetchone()
    return dict(row) if row else None


def _blueprint_metadata(blueprint: dict) -> dict:
    metadata = workspace_parse_json_field(blueprint.get("metadata_json"), {})
    return metadata if isinstance(metadata, dict) else {}


def _save_blueprint_metadata(cursor, blueprint_id: str, metadata: dict) -> None:
    cursor.execute(
        """
        UPDATE agent_blueprints
        SET metadata_json = %s::jsonb,
            updated_at = NOW()
        WHERE id = %s
        """,
        (json.dumps(metadata, ensure_ascii=False), blueprint_id),
    )


def _admin_review_text(value) -> str:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False)
    return str(value or "")


def _build_admin_agent_review(row: dict) -> dict:
    metadata = row.get("metadata_json") if isinstance(row.get("metadata_json"), dict) else {}
    fragments = [
        row.get("name"),
        row.get("description"),
        row.get("latest_goal"),
        row.get("steps_json"),
        row.get("approval_policy_json"),
        row.get("capability_allowlist_json"),
        metadata,
        row.get("integration_providers"),
    ]
    text = " ".join(_admin_review_text(item).lower() for item in fragments)
    reasons = []
    level = "low"

    high_keywords = [
        ("оплата или деньги", ["payment", "платеж", "оплат", "списан", "финанс", "finance"]),
        ("удаление или разрушительное действие", ["delete", "удал", "destroy", "wipe"]),
        ("внешняя отправка", ["telegram", "whatsapp", "email", "почт", "сообщен", "send", "отправ"]),
        ("публикация", ["publish", "публи", "пост", "post"]),
        ("секреты или токены", ["api key", "token", "webhook", "secret", "ключ api"]),
    ]
    medium_keywords = [
        ("подключены внешние данные", ["google sheets", "spreadsheet", "таблиц", "google", "интеграц"]),
        ("есть ручное согласование", ["approval", "approve", "согласован", "подтвержд"]),
        ("кастомный процесс", ["custom_process", "custom process", "кастом"]),
    ]

    for reason, keywords in high_keywords:
        if any(keyword in text for keyword in keywords):
            reasons.append(reason)
            level = "high"
    if level != "high":
        for reason, keywords in medium_keywords:
            if any(keyword in text for keyword in keywords):
                reasons.append(reason)
                level = "medium"

    if not reasons:
        reasons.append("явных внешних или опасных действий не найдено")

    return {"risk_level": level, "risk_reasons": reasons[:4]}


def _normalize_agent_integration(row: dict, *, attached: bool = True) -> dict:
    config = workspace_parse_json_field(row.get("config_json"), {})
    limits = workspace_parse_json_field(row.get("limits_json"), {})
    if not isinstance(config, dict):
        config = {}
    if not isinstance(limits, dict):
        limits = {}
    provider = str(row.get("provider") or "").strip()
    return {
        "id": str(row.get("id") or ""),
        "business_id": str(row.get("business_id") or ""),
        "provider": provider,
        "provider_label": _agent_integration_provider_label(provider),
        "status": str(row.get("status") or "draft"),
        "display_name": str(row.get("display_name") or ""),
        "auth_ref": str(row.get("auth_ref") or ""),
        "has_auth_ref": bool(str(row.get("auth_ref") or "").strip()),
        "config": config,
        "limits": limits,
        "attached": attached,
        "connected_by_user_id": str(row.get("connected_by_user_id") or ""),
        "created_at": row.get("created_at"),
        "updated_at": row.get("updated_at"),
        "execution_boundary": _agent_integration_execution_boundary(provider),
    }


def _agent_integration_provider_label(provider: str) -> str:
    labels = {
        "google_sheets": "Google Sheets",
        "browser_use": "Browser use",
        "telegram": "Telegram",
        "whatsapp": "WhatsApp",
        "maton": "Maton.ai",
        "localos_finance": "Финансы LocalOS",
        "composio": "Composio",
    }
    return labels.get(provider, provider or "integration")


def _agent_integration_execution_boundary(provider: str) -> dict:
    boundary = integration_execution_boundary(provider)
    if boundary.get("capabilities"):
        return boundary
    if provider == "google_sheets":
        return {
            "capabilities": ["sheets.append_row_request", "google_sheets.append_row"],
            "approval_required": True,
            "executor": "agent_sheet_provider_executor_v1",
            "external_write": "approved_append_row",
        }
    if provider == "browser_use":
        return {
            "capabilities": ["browser_use.read_page"],
            "approval_required": True,
            "executor": "openclaw_browser_boundary",
            "external_write": "none_read_only",
        }
    if provider in {"telegram", "whatsapp"}:
        return {
            "triggers": [f"{provider}.message.received"],
            "capabilities": ["communications.draft", "communications.send_reminder", "communications.send_offer"],
            "approval_required": True,
            "executor": "channel_router",
            "external_write": "approved_delivery_only",
        }
    return {
        "capabilities": [],
        "approval_required": True,
        "executor": "action_orchestrator",
        "external_write": "approval_required",
    }


def _agent_integration_provider_catalog() -> list[dict]:
    return integration_provider_catalog()


def _agent_connection_plan(
    binding_status: list[dict],
    attached_integrations: list[dict],
    available_integrations: list[dict],
    provider_catalog: list[dict],
) -> dict:
    attached_by_provider = _integrations_by_provider(attached_integrations)
    available_by_provider = _integrations_by_provider(available_integrations)
    catalog_by_provider = {
        str(item.get("provider") or "").strip(): item
        for item in provider_catalog
        if isinstance(item, dict) and str(item.get("provider") or "").strip()
    }
    items = []
    for binding in binding_status:
        if not isinstance(binding, dict):
            continue
        provider = str(binding.get("provider") or "").strip()
        catalog_item = catalog_by_provider.get(provider, {})
        attached = attached_by_provider.get(provider, [])
        available = available_by_provider.get(provider, [])
        status = str(binding.get("status") or "").strip()
        action = _connection_plan_action(binding, attached, available, catalog_item)
        provider_routes = connector_provider_routes(provider, str(binding.get("capability") or ""))
        route_state = "connected" if action in {"ready", "native_ready"} else best_provider_route_state(provider_routes)
        recommended_route = _preferred_provider_route(provider_routes)
        items.append(
            {
                "key": str(binding.get("key") or provider or ""),
                "provider": provider,
                "title": str(catalog_item.get("title") or _agent_integration_provider_label(provider)),
                "capability": str(binding.get("capability") or ""),
                "trigger": str(binding.get("trigger") or ""),
                "direction": str(binding.get("direction") or ""),
                "binding_status": status,
                "action": action,
                "primary_label": _connection_plan_label(action),
                "explanation": _connection_plan_explanation(binding, action),
                "route_state": route_state,
                "route_summary": _connection_plan_route_summary(binding, action, route_state),
                "why_blocked": _connection_plan_why_blocked(binding, action, route_state),
                "setup_cta": _connection_plan_setup_cta(binding, action, route_state, recommended_route),
                "execution_boundary": str(binding.get("execution_boundary") or ""),
                "autonomy_level": str(binding.get("autonomy_level") or ""),
                "credential_state": str(binding.get("credential_state") or ""),
                "approval_state": str(binding.get("approval_state") or ""),
                "policy_summary": str(binding.get("policy_summary") or ""),
                "next_action_label": str(binding.get("next_action_label") or ""),
                "provider_routes": provider_routes,
                "recommended_route": recommended_route,
                "recommended_route_reason": _connection_plan_recommended_route_reason(action, recommended_route),
                "missing_config": binding.get("missing_config") if isinstance(binding.get("missing_config"), list) else [],
                "approval_required": bool(binding.get("approval_required", True)),
                "existing_integrations": [_connection_plan_integration(item) for item in available[:5]],
                "attached_integrations": [_connection_plan_integration(item) for item in attached[:5]],
                "provider_paths": _connection_plan_provider_paths(catalog_item),
            }
        )
    missing_count = len([item for item in items if item.get("action") not in {"ready", "native_ready"}])
    return {
        "schema": "localos_agent_connection_plan_v1",
        "status": "ready" if missing_count == 0 else "needs_action",
        "missing_count": missing_count,
        "items": items,
    }


def _build_agent_post_connect_handoff(connection_plan: dict) -> dict:
    missing_count = _safe_int(connection_plan.get("missing_count"), 0, 0, 100)
    if missing_count == 0:
        return {
            "schema": "localos_agent_post_create_handoff_v1",
            "status": "ready_for_preview",
            "next_step": "run_preview",
            "workspace_mode": "run",
            "next_binding_key": "",
            "next_binding": {},
            "next_route": {},
            "title": "Подключения готовы",
            "description": "Теперь запустите safe preview run: он проверит workflow, preflight, limits и approval gate без внешних действий.",
            "connection_plan": connection_plan,
        }
    next_binding_key = _connection_plan_next_binding_key(connection_plan)
    next_binding = _connection_plan_item_by_key(connection_plan, next_binding_key)
    return {
        "schema": "localos_agent_post_create_handoff_v1",
        "status": "needs_connections",
        "next_step": "connect_required_integrations",
        "workspace_mode": "connections",
        "next_binding_key": next_binding_key,
        "next_binding": next_binding,
        "next_route": _preferred_connection_plan_route(next_binding),
        "title": "Остались подключения",
        "description": "Завершите обязательные подключения, затем LocalOS откроет safe preview run.",
        "connection_plan": connection_plan,
    }


def _connection_plan_next_binding_key(connection_plan: dict) -> str:
    items = connection_plan.get("items") if isinstance(connection_plan.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        action = str(item.get("action") or "").strip()
        if action in {"ready", "native_ready"}:
            continue
        key = str(item.get("key") or "").strip()
        if key:
            return key
    return ""


def _connection_plan_item_by_key(connection_plan: dict, binding_key: str) -> dict:
    items = connection_plan.get("items") if isinstance(connection_plan.get("items"), list) else []
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("key") or "").strip() == binding_key:
            return item
    for item in items:
        if not isinstance(item, dict):
            continue
        if str(item.get("action") or "").strip() not in {"ready", "native_ready"}:
            return item
    return {}


def _preferred_connection_plan_route(plan_item: dict) -> dict:
    routes = plan_item.get("provider_routes") if isinstance(plan_item.get("provider_routes"), list) else []
    return _preferred_provider_route(routes)


def _preferred_provider_route(routes: list) -> dict:
    for provider, state in [
        ("openclaw", "available"),
        ("openclaw", "connected"),
        ("maton", "available"),
        ("maton", "connected"),
        ("native_localos", "available"),
        ("manual", "manual"),
        ("manual", "available"),
        ("composio", "planned"),
    ]:
        for route in routes:
            if not isinstance(route, dict):
                continue
            route_provider = str(route.get("provider") or "").strip()
            route_state = str(route.get("state") or route.get("status") or "").strip()
            if route_provider == provider and route_state == state:
                return route
    for state in ["available", "manual", "planned", "connected"]:
        for route in routes:
            if isinstance(route, dict) and str(route.get("state") or route.get("status") or "") == state:
                return route
    return routes[0] if routes and isinstance(routes[0], dict) else {}


def _connection_plan_recommended_route_reason(action: str, route: dict) -> str:
    if not route:
        return ""
    provider = str(route.get("provider") or "").strip()
    label = str(route.get("label") or provider or "provider route").strip()
    if action in {"ready", "native_ready"}:
        return f"{label} уже закрывает этот binding."
    if provider == "openclaw":
        return "OpenClaw можно использовать как execution boundary под LocalOS policy envelope."
    if provider == "maton":
        return "Maton можно использовать как provider bridge после выбора сохранённого ключа."
    if provider == "manual":
        return "Manual fallback оставит агента в draft/handoff режиме до действия человека."
    return f"{label} доступен как provider route для этого binding."


def _integrations_by_provider(values: list[dict]) -> dict:
    result: dict[str, list[dict]] = {}
    for item in values:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        if not provider:
            continue
        result.setdefault(provider, []).append(item)
    return result


def _connection_plan_action(binding: dict, attached: list[dict], available: list[dict], catalog_item: dict) -> str:
    status = str(binding.get("status") or "").strip()
    resolution = str(binding.get("resolution") or "").strip()
    if resolution in {"provider_route_required", "agent_integration_needs_provider_route", "builder_answer_needs_provider_route"}:
        return "choose_route"
    if status in {"connected", "ready"}:
        return "native_ready" if resolution == "native_localos" else "ready"
    if available:
        return "choose_existing"
    provider_status = str(catalog_item.get("status") or "").strip()
    if provider_status == "planned":
        return "planned_provider"
    if attached:
        return "complete_config"
    return "connect_required"


def _connection_plan_label(action: str) -> str:
    labels = {
        "ready": "Готово",
        "native_ready": "Готово в LocalOS",
        "choose_route": "Выберите маршрут выполнения",
        "choose_existing": "Выберите существующее подключение",
        "complete_config": "Заполните недостающие поля",
        "connect_required": "Подключите сервис",
        "planned_provider": "Будет доступно позже",
    }
    return labels.get(action, "Проверьте подключение")


def _connection_plan_explanation(binding: dict, action: str) -> str:
    provider = str(binding.get("provider") or "сервис").strip()
    missing_config = binding.get("missing_config") if isinstance(binding.get("missing_config"), list) else []
    if action in {"ready", "native_ready"}:
        return "Подключение готово для preflight и активации."
    if action == "choose_route":
        return "Выберите маршрут выполнения для этого шага: существующий доступ, OpenClaw boundary, Maton key или ручной fallback."
    if action == "choose_existing":
        return "У бизнеса уже есть подходящий доступ. Выберите его для этого агента."
    if action == "complete_config":
        return f"Доступ найден, но нужно заполнить: {', '.join([str(item) for item in missing_config])}."
    if action == "planned_provider":
        return "Этот provider есть в roadmap, но пока недоступен для активации агента."
    return f"Подключите {provider}, чтобы агент можно было активировать после preflight."


def _connection_plan_route_summary(binding: dict, action: str, route_state: str) -> str:
    provider = str(binding.get("provider") or "сервис").strip()
    title = _agent_integration_provider_label(provider)
    if action in {"ready", "native_ready"}:
        return f"{title} уже подключён для этого агента."
    if action == "choose_route":
        return f"{title}: выберите route выполнения, прежде чем запускать preview или активацию."
    if action == "choose_existing":
        return f"У бизнеса уже есть подключение {title}; выберите его для шага workflow."
    if action == "complete_config":
        return f"Подключение {title} найдено, но нужно заполнить недостающие настройки."
    if route_state == "available":
        return f"{title} можно подключить через доступный provider route LocalOS/OpenClaw/Maton."
    if route_state == "manual":
        return f"{title} доступен как ручной fallback или загруженный источник."
    if route_state == "planned":
        return f"{title} появится через planned provider route, но сейчас агент нельзя активировать на этом пути."
    return f"Для {title} нет разрешённого provider route."


def _connection_plan_why_blocked(binding: dict, action: str, route_state: str) -> str:
    if action in {"ready", "native_ready"}:
        return ""
    provider = str(binding.get("provider") or "").strip()
    title = _agent_integration_provider_label(provider)
    missing_config = binding.get("missing_config") if isinstance(binding.get("missing_config"), list) else []
    if action == "choose_route":
        return f"{title} найден или описан, но route выполнения ещё не выбран."
    if action == "choose_existing":
        return f"Есть сохранённый доступ {title}, но он ещё не выбран для этого агента."
    if action == "complete_config":
        return f"{title} выбран, но не хватает настроек: {', '.join([str(item) for item in missing_config])}."
    if action == "planned_provider":
        return f"{title} есть в каталоге, но provider route пока не доступен для production-запуска."
    if route_state in {"available", "manual"}:
        return f"Нужно выбрать разрешённый route или добавить доступ {title} перед preview."
    return f"У LocalOS нет разрешённого подключения для {title}."


def _connection_plan_setup_cta(binding: dict, action: str, route_state: str, recommended_route: dict) -> dict:
    provider = str(binding.get("provider") or "").strip()
    binding_key = str(binding.get("key") or provider or "").strip()
    title = _agent_integration_provider_label(provider)
    if action in {"ready", "native_ready"}:
        return {"label": "Готово", "action": "none", "binding_key": binding_key, "provider": provider}
    if action == "choose_route":
        route_provider = str((recommended_route or {}).get("provider") or "").strip()
        return {
            "label": f"Выбрать route {title}",
            "action": "choose_route",
            "binding_key": binding_key,
            "provider": provider,
            "route_provider": route_provider,
        }
    if action == "choose_existing":
        return {"label": f"Выбрать доступ {title}", "action": "choose_existing", "binding_key": binding_key, "provider": provider}
    if action == "complete_config":
        return {"label": f"Заполнить {title}", "action": "complete_config", "binding_key": binding_key, "provider": provider}
    route_provider = str((recommended_route or {}).get("provider") or "").strip()
    if route_provider:
        route_label = str((recommended_route or {}).get("label") or route_provider).strip()
        return {
            "label": f"Выбрать route: {route_label}",
            "action": "choose_route",
            "binding_key": binding_key,
            "provider": provider,
            "route_provider": route_provider,
        }
    if action == "planned_provider":
        return {"label": "Недоступно сейчас", "action": "planned", "binding_key": binding_key, "provider": provider}
    if route_state == "manual":
        return {"label": "Оставить ручной fallback", "action": "choose_route", "binding_key": binding_key, "provider": provider, "route_provider": "manual"}
    return {"label": f"Подключить {title}", "action": "connect", "binding_key": binding_key, "provider": provider}


def _connection_plan_provider_paths(catalog_item: dict) -> list[dict]:
    providers = catalog_item.get("providers") if isinstance(catalog_item.get("providers"), list) else []
    result = []
    for item in providers:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        if provider:
            result.append(
                {
                    "provider": provider,
                    "label": str(item.get("label") or provider),
                    "status": str(item.get("status") or "unknown"),
                }
            )
    return result


def _connection_plan_integration(integration: dict) -> dict:
    return {
        "id": str(integration.get("id") or ""),
        "provider": str(integration.get("provider") or ""),
        "display_name": str(integration.get("display_name") or integration.get("provider_label") or integration.get("provider") or ""),
        "status": str(integration.get("status") or ""),
    }


def _agent_integration_ids(metadata: dict) -> list[str]:
    raw_ids = metadata.get("agent_integration_ids") if isinstance(metadata.get("agent_integration_ids"), list) else []
    result = []
    for item in raw_ids:
        item_id = str(item or "").strip()
        if item_id and item_id not in result:
            result.append(item_id)
    return result


def _agent_connection_context(cursor, business_id: str, metadata: dict) -> dict:
    attached_ids = _agent_integration_ids(metadata)
    try:
        attached_rows = _load_agent_integrations(cursor, business_id, attached_ids) if attached_ids else []
        all_rows = _load_agent_integrations(cursor, business_id)
    except Exception:
        attached_rows = []
        all_rows = []
    attached_lookup = {str(row.get("id") or "") for row in attached_rows}
    return {
        "attached_rows": attached_rows,
        "all_rows": all_rows,
        "attached_integrations": [_normalize_agent_integration(row, attached=True) for row in attached_rows],
        "available_integrations": [
            _normalize_agent_integration(row, attached=False)
            for row in all_rows
            if str(row.get("id") or "") not in attached_lookup
        ],
        "provider_catalog": _agent_integration_provider_catalog(),
    }


def _agent_integration_binding_status(metadata: dict, integrations: list[dict]) -> list[dict]:
    required = metadata.get("required_integration_bindings") if isinstance(metadata.get("required_integration_bindings"), list) else []
    provider_routes = metadata.get("agent_binding_provider_routes") if isinstance(metadata.get("agent_binding_provider_routes"), dict) else {}
    binding_integrations = metadata.get("agent_binding_integrations") if isinstance(metadata.get("agent_binding_integrations"), dict) else {}
    by_provider = {}
    for integration in integrations:
        provider = str(integration.get("provider") or "").strip()
        if provider and provider not in by_provider:
            by_provider[provider] = integration
    result = []
    for item in required:
        if not isinstance(item, dict):
            continue
        binding_key = str(item.get("key") or "")
        provider = str(item.get("provider") or "").strip()
        selected_route = provider_routes.get(binding_key) if isinstance(provider_routes.get(binding_key), dict) else {}
        binding_metadata = binding_integrations.get(binding_key) if isinstance(binding_integrations.get(binding_key), dict) else {}
        answer_config = binding_metadata.get("answer_config") if isinstance(binding_metadata.get("answer_config"), dict) else {}
        route_provider = str(selected_route.get("route_provider") or "").strip()
        route_status = str(selected_route.get("status") or "active").strip()
        if route_provider in {"openclaw", "maton", "manual"} and route_status == "active":
            result.append(
                {
                    "key": binding_key,
                    "provider": provider,
                    "direction": str(item.get("direction") or ""),
                    "required": bool(item.get("required", True)),
                    "approval_required": bool(item.get("approval_required", True)),
                    "capability": str(item.get("capability") or ""),
                    "trigger": str(item.get("trigger") or ""),
                    "status": "connected",
                    "integration_id": str(selected_route.get("integration_id") or selected_route.get("external_account_id") or route_provider),
                    "missing_config": [],
                    "resolution": f"provider_route_{route_provider}",
                    "route_provider": route_provider,
                    "route": selected_route,
                    "answer_config": answer_config,
                }
            )
            continue
        integration = by_provider.get(provider)
        if provider == "localos_finance" and not integration:
            result.append(
                {
                    "key": binding_key,
                    "provider": provider,
                    "direction": str(item.get("direction") or ""),
                    "required": bool(item.get("required", True)),
                    "approval_required": bool(item.get("approval_required", True)),
                    "capability": str(item.get("capability") or ""),
                    "trigger": str(item.get("trigger") or ""),
                    "status": "connected",
                    "integration_id": "native_localos",
                    "missing_config": [],
                    "resolution": "native_localos",
                    "answer_config": answer_config,
                }
            )
            continue
        config = workspace_parse_json_field((integration or {}).get("config_json"), {})
        if not isinstance(config, dict):
            config = {}
        required_config = item.get("required_config") if isinstance(item.get("required_config"), list) else []
        missing_config = [
            str(config_key)
            for config_key in required_config
            if not str(config.get(str(config_key)) or "").strip()
        ]
        status = "connected" if integration and str(integration.get("status") or "") == "active" and not missing_config else "needs_connection"
        result.append(
            {
                "key": binding_key,
                "provider": provider,
                "direction": str(item.get("direction") or ""),
                "required": bool(item.get("required", True)),
                "approval_required": bool(item.get("approval_required", True)),
                "capability": str(item.get("capability") or ""),
                "trigger": str(item.get("trigger") or ""),
                "status": status,
                "integration_id": str((integration or {}).get("id") or ""),
                "missing_config": missing_config,
                "resolution": "agent_integration" if status == "connected" else "missing_integration",
                "answer_config": answer_config,
            }
        )
    return result


def _load_agent_integrations(cursor, business_id: str, integration_ids: list[str] | None = None) -> list[dict]:
    if integration_ids:
        cursor.execute(
            """
            SELECT id, business_id, provider, status, display_name, auth_ref,
                   config_json, limits_json, connected_by_user_id, created_at, updated_at
            FROM agent_integrations
            WHERE business_id = %s
              AND id = ANY(%s)
            ORDER BY updated_at DESC, created_at DESC
            """,
            (business_id, integration_ids),
        )
    else:
        cursor.execute(
            """
            SELECT id, business_id, provider, status, display_name, auth_ref,
                   config_json, limits_json, connected_by_user_id, created_at, updated_at
            FROM agent_integrations
            WHERE business_id = %s
            ORDER BY updated_at DESC, created_at DESC
            LIMIT 100
            """,
            (business_id,),
        )
    return [dict(row) for row in cursor.fetchall() or []]


def _load_direct_builder_connection_inventory(cursor, business_id: str) -> list[dict]:
    result: list[dict] = []
    for row in _load_agent_integrations(cursor, business_id):
        config = parse_json_field(row.get("config_json"), {})
        result.append(
            {
                "id": str(row.get("id") or ""),
                "provider": str(row.get("provider") or ""),
                "status": str(row.get("status") or "active"),
                "display_name": str(row.get("display_name") or row.get("provider") or ""),
                "config": config if isinstance(config, dict) else {},
            }
        )
    try:
        cursor.execute(
            """
            SELECT id, source, display_name
            FROM externalbusinessaccounts
            WHERE business_id = %s
              AND is_active = TRUE
              AND source IN ('maton', 'google_sheets', 'google_business', 'telegram_app')
            ORDER BY updated_at DESC
            LIMIT 50
            """,
            (business_id,),
        )
    except Exception:
        return result
    for row in cursor.fetchall() or []:
        item = dict(row)
        source = str(item.get("source") or "").strip()
        provider = source
        config: dict = {}
        if source == "telegram_app":
            provider = "telegram"
            config = {"bot_mode": "business_bot"}
        elif source == "maton":
            provider = "maton"
            config = {"channel": "maton_bridge"}
        elif source in {"google_sheets", "google_business"}:
            provider = "google_sheets"
        result.append(
            {
                "id": str(item.get("id") or ""),
                "provider": provider,
                "status": "active",
                "display_name": str(item.get("display_name") or source or provider),
                "config": config,
                "auth_ref": str(item.get("id") or "") if source in {"google_sheets", "google_business", "maton"} else "",
                "inventory_source": "external_business_account",
                "credential_source": source,
            }
        )
    try:
        cursor.execute(
            """
            SELECT telegram_bot_token
            FROM Businesses
            WHERE id = %s
            LIMIT 1
            """,
            (business_id,),
        )
        business = cursor.fetchone() or {}
    except Exception:
        business = {}
    if str(dict(business).get("telegram_bot_token") or "").strip():
        result.append(
            {
                "id": "business_telegram_bot",
                "provider": "telegram",
                "status": "active",
                "display_name": "Бот бизнеса",
                "config": {"bot_mode": "business_bot"},
            }
        )
    return result


def _direct_selected_connection_bindings(payload: dict, preview: dict, inventory: list[dict]) -> dict:
    raw = payload.get("selected_connection_bindings")
    if not isinstance(raw, dict):
        raw = payload.get("selected_bindings")
    if not isinstance(raw, dict):
        raw = {}
    summary = preview.get("connection_summary") if isinstance(preview.get("connection_summary"), dict) else {}
    summary_items = summary.get("items") if isinstance(summary.get("items"), list) else []
    allowed_by_key: dict[str, set[str]] = {}
    provider_by_key: dict[str, str] = {}
    single_connection_by_key: dict[str, str] = {}
    for item in summary_items:
        if not isinstance(item, dict):
            continue
        binding_key = str(item.get("key") or "").strip()
        provider = str(item.get("provider") or "").strip()
        if not binding_key:
            continue
        provider_by_key[binding_key] = provider
        allowed = set()
        connections = item.get("connections") if isinstance(item.get("connections"), list) else []
        for connection in connections:
            if isinstance(connection, dict) and str(connection.get("id") or "").strip():
                allowed.add(str(connection.get("id") or "").strip())
        allowed_by_key[binding_key] = allowed
        if len(allowed) == 1:
            single_connection_by_key[binding_key] = next(iter(allowed))
    inventory_by_id = {
        str(item.get("id") or "").strip(): item
        for item in inventory
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    result = {}
    for key, value in raw.items():
        binding_key = str(key or "").strip()
        integration_id = str(value or "").strip()
        if not binding_key or not integration_id or binding_key not in allowed_by_key:
            continue
        allowed_ids = allowed_by_key.get(binding_key) or set()
        if allowed_ids and integration_id not in allowed_ids:
            continue
        integration = inventory_by_id.get(integration_id)
        if not integration:
            continue
        provider = provider_by_key.get(binding_key) or str(integration.get("provider") or "")
        result[binding_key] = {
            "integration_id": integration_id,
            "provider": provider,
            "display_name": str(integration.get("display_name") or provider),
            "config": integration.get("config") if isinstance(integration.get("config"), dict) else {},
        }
    for binding_key, integration_id in single_connection_by_key.items():
        if binding_key in result:
            continue
        integration = inventory_by_id.get(integration_id)
        if not integration:
            continue
        provider = provider_by_key.get(binding_key) or str(integration.get("provider") or "")
        result[binding_key] = {
            "integration_id": integration_id,
            "provider": provider,
            "display_name": str(integration.get("display_name") or provider),
            "config": integration.get("config") if isinstance(integration.get("config"), dict) else {},
            "selection_source": "auto_single_connection",
        }
    return result


def _direct_missing_required_connection_choices(preview: dict, selected_bindings: dict) -> list[dict]:
    summary = preview.get("connection_summary") if isinstance(preview.get("connection_summary"), dict) else {}
    items = summary.get("items") if isinstance(summary.get("items"), list) else []
    missing = []
    for item in items:
        if not isinstance(item, dict):
            continue
        binding_key = str(item.get("key") or "").strip()
        action = str(item.get("action") or "").strip()
        connections = item.get("connections") if isinstance(item.get("connections"), list) else []
        if binding_key and action == "choose_existing" and len(connections) > 1 and binding_key not in selected_bindings:
            missing.append(
                {
                    "key": binding_key,
                    "provider": str(item.get("provider") or ""),
                    "title": str(item.get("title") or item.get("provider") or binding_key),
                    "connection_count": len(connections),
                }
            )
    return missing


def _apply_direct_selected_connection_bindings(metadata: dict, selected_bindings: dict) -> dict:
    if not selected_bindings:
        return metadata
    integration_ids = metadata.get("agent_integration_ids") if isinstance(metadata.get("agent_integration_ids"), list) else []
    capability_integrations = metadata.get("capability_integrations") if isinstance(metadata.get("capability_integrations"), dict) else {}
    binding_integrations = metadata.get("agent_binding_integrations") if isinstance(metadata.get("agent_binding_integrations"), dict) else {}
    custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
    for binding_key, selected in selected_bindings.items():
        if not isinstance(selected, dict):
            continue
        integration_id = str(selected.get("integration_id") or "").strip()
        provider = str(selected.get("provider") or "").strip()
        if not integration_id or not provider:
            continue
        if integration_id not in integration_ids:
            integration_ids.append(integration_id)
        capability_integrations[provider] = integration_id
        binding_integrations[str(binding_key)] = {
            "integration_id": integration_id,
            "provider": provider,
            "source": "direct_agent_draft",
        }
        config = selected.get("config") if isinstance(selected.get("config"), dict) else {}
        binding_config = {"integration_id": integration_id}
        for key, value in config.items():
            binding_config[str(key)] = value
        custom_process[str(binding_key)] = binding_config
        if provider == "google_sheets":
            custom_process["google_sheets"] = dict(binding_config)
        if provider == "telegram":
            custom_process["telegram"] = dict(binding_config)
    metadata["agent_integration_ids"] = integration_ids[-25:]
    metadata["capability_integrations"] = capability_integrations
    metadata["agent_binding_integrations"] = binding_integrations
    metadata["custom_process"] = custom_process
    return metadata


def _load_agent_external_auth_options(cursor, business_id: str) -> list[dict]:
    try:
        cursor.execute(
            """
            SELECT id, source, external_id, display_name, is_active, updated_at
            FROM externalbusinessaccounts
            WHERE business_id = %s
              AND is_active = TRUE
              AND source IN ('google_business', 'telegram_app', 'maton')
            ORDER BY updated_at DESC
            LIMIT 50
            """,
            (business_id,),
        )
    except Exception:
        return []
    return [
        {
            "id": str(row.get("id") or ""),
            "source": str(row.get("source") or ""),
            "provider": "google_sheets" if str(row.get("source") or "") in {"google_business", "google_sheets"} else str(row.get("source") or ""),
            "display_name": str(row.get("display_name") or row.get("external_id") or row.get("source") or ""),
            "updated_at": row.get("updated_at"),
        }
        for row in cursor.fetchall() or []
    ]


def _sanitize_agent_integration_config(provider: str, payload: dict) -> dict:
    source = payload.get("config") if isinstance(payload.get("config"), dict) else payload
    if provider == "google_sheets":
        operation = str(source.get("operation") or payload.get("operation") or "read_write").strip()
        if operation not in {"read_rows", "append_row", "read_write"}:
            operation = "read_write"
        return {
            "spreadsheet_id": str(source.get("spreadsheet_id") or source.get("google_spreadsheet_id") or "").strip(),
            "sheet_name": str(source.get("sheet_name") or source.get("tab") or "Sheet1").strip() or "Sheet1",
            "operation": operation,
            "mode": "approved_executor",
        }
    if provider == "browser_use":
        raw_urls = source.get("target_urls") or source.get("urls") or source.get("target_url") or ""
        if isinstance(raw_urls, str):
            urls = [item.strip() for item in raw_urls.replace("\n", ",").split(",") if item.strip()]
        elif isinstance(raw_urls, list):
            urls = [str(item or "").strip() for item in raw_urls if str(item or "").strip()]
        else:
            urls = []
        return {
            "target_urls": urls[:10],
            "mode": "openclaw_browser_boundary",
            "read_only": True,
        }
    if provider == "telegram":
        return {
            "bot_mode": str(source.get("bot_mode") or "business_bot").strip() or "business_bot",
            "trigger": "telegram.message.received",
            "mode": "trigger_boundary",
        }
    if provider == "whatsapp":
        return {
            "channel_mode": str(source.get("channel_mode") or "whatsapp_business").strip() or "whatsapp_business",
            "trigger": "whatsapp.message.received",
            "mode": "trigger_boundary",
        }
    if provider == "maton":
        return {
            "channel": str(source.get("channel") or "maton_bridge").strip() or "maton_bridge",
            "mode": "approved_delivery_bridge",
        }
    if provider == "localos_finance":
        return {
            "transaction_type": str(source.get("transaction_type") or "auto_detect").strip() or "auto_detect",
            "mode": "approved_localos_write",
        }
    if provider == "composio":
        return {
            "toolkit": str(source.get("toolkit") or "").strip(),
            "mode": "planned_connector_provider",
        }
    return {}


def _sanitize_agent_integration_limits(provider: str, payload: dict) -> dict:
    source = payload.get("limits") if isinstance(payload.get("limits"), dict) else payload
    if provider == "google_sheets":
        return {
            "daily_append_cap": _safe_int(source.get("daily_append_cap"), 50, 1, 500),
            "frequency_cap_minutes": _safe_int(source.get("frequency_cap_minutes"), 0, 0, 1440),
        }
    if provider == "browser_use":
        return {
            "daily_page_check_cap": _safe_int(source.get("daily_page_check_cap"), 50, 1, 500),
            "frequency_cap_minutes": _safe_int(source.get("frequency_cap_minutes"), 60, 0, 1440),
        }
    if provider in {"telegram", "whatsapp"}:
        return {
            "daily_message_cap": _safe_int(source.get("daily_message_cap"), 50, 1, 500),
            "frequency_cap_minutes": _safe_int(source.get("frequency_cap_minutes"), 30, 0, 1440),
        }
    if provider == "maton":
        return {
            "daily_message_cap": _safe_int(source.get("daily_message_cap"), 50, 1, 500),
            "frequency_cap_minutes": _safe_int(source.get("frequency_cap_minutes"), 30, 0, 1440),
        }
    if provider == "localos_finance":
        return {
            "daily_transaction_cap": _safe_int(source.get("daily_transaction_cap"), 100, 1, 1000),
        }
    if provider == "composio":
        return {
            "daily_action_cap": _safe_int(source.get("daily_action_cap"), 50, 1, 500),
            "frequency_cap_minutes": _safe_int(source.get("frequency_cap_minutes"), 0, 0, 1440),
        }
    return {}


def _safe_int(value, fallback: int, minimum: int, maximum: int) -> int:
    try:
        parsed = int(value)
    except Exception:
        parsed = fallback
    return max(minimum, min(parsed, maximum))


def _normalize_custom_process_payload(payload: dict, current_process: dict) -> dict:
    google_sheets = current_process.get("google_sheets") if isinstance(current_process.get("google_sheets"), dict) else {}
    row_values_raw = payload.get("row_values")
    if isinstance(row_values_raw, str):
        row_values = [item.strip() for item in row_values_raw.split(",") if item.strip()]
    elif isinstance(row_values_raw, list):
        row_values = [str(item or "").strip() for item in row_values_raw if str(item or "").strip()]
    else:
        row_values = current_process.get("row_values") if isinstance(current_process.get("row_values"), list) else []
    if not row_values:
        row_values = ["{{received_at}}", "{{telegram_username}}", "{{message_text}}"]
    sheet_name = str(payload.get("sheet_name") or google_sheets.get("sheet_name") or "Leads").strip() or "Leads"
    spreadsheet_id = str(payload.get("spreadsheet_id") or google_sheets.get("spreadsheet_id") or "").strip()
    integration_id = str(payload.get("integration_id") or google_sheets.get("integration_id") or "").strip()
    return {
        "kind": "integration_workflow",
        "trigger": str(payload.get("trigger") or current_process.get("trigger") or "telegram.message.received").strip(),
        "target": str(payload.get("target") or current_process.get("target") or "google_sheets.append_row").strip(),
        "runtime": "agent_blueprints",
        "showcase": str(current_process.get("showcase") or "telegram_to_google_sheets"),
        "binding_status": str(current_process.get("binding_status") or "requires_user_connection"),
        "row_values": row_values,
        "columns": [str(item).replace("{{", "").replace("}}", "") for item in row_values],
        "daily_append_cap": _safe_int(payload.get("daily_append_cap"), int(current_process.get("daily_append_cap") or 50), 1, 500),
        "google_sheets": {
            "integration_id": integration_id,
            "spreadsheet_id": spreadsheet_id,
            "sheet_name": sheet_name,
            "operation": "append_row",
        },
    }


def _apply_custom_process_to_version_payload(version_payload: dict, custom_process: dict) -> dict:
    payload = dict(version_payload)
    row_values = custom_process.get("row_values") if isinstance(custom_process.get("row_values"), list) else []
    columns = custom_process.get("columns") if isinstance(custom_process.get("columns"), list) else []
    google_sheets = custom_process.get("google_sheets") if isinstance(custom_process.get("google_sheets"), dict) else {}
    sheet_name = str(google_sheets.get("sheet_name") or "Leads").strip() or "Leads"
    daily_append_cap = _safe_int(custom_process.get("daily_append_cap"), 50, 1, 500)
    steps = payload.get("steps") if isinstance(payload.get("steps"), list) else []
    next_steps = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        next_step = dict(step)
        step_payload = next_step.get("payload") if isinstance(next_step.get("payload"), dict) else {}
        if next_step.get("key") == "prepare_sheet_row":
            step_payload = {
                **step_payload,
                "columns": columns,
                "row_values": row_values,
            }
        if next_step.get("key") == "request_sheet_append" or next_step.get("capability") == "sheets.append_row_request":
            step_payload = {
                **step_payload,
                "sheet_name": sheet_name,
                "row_values": row_values,
                "daily_append_cap": daily_append_cap,
            }
        next_step["payload"] = step_payload
        next_steps.append(next_step)
    payload["steps"] = next_steps
    output_schema = payload.get("output_schema") if isinstance(payload.get("output_schema"), dict) else {}
    output_schema["sheet_name"] = sheet_name
    output_schema["row_values"] = row_values
    payload["output_schema"] = output_schema
    limits = payload.get("limits") if isinstance(payload.get("limits"), dict) else {}
    limits["daily_append_cap"] = daily_append_cap
    payload["limits"] = limits
    return payload


def _build_custom_process_preview_input(blueprint: dict, payload: dict) -> dict:
    metadata = _blueprint_metadata(blueprint)
    custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
    google_sheets = custom_process.get("google_sheets") if isinstance(custom_process.get("google_sheets"), dict) else {}
    source_event_id = f"preview-{uuid.uuid4()}"
    message_text = str(payload.get("message_text") or "Новая заявка из preview").strip() or "Новая заявка из preview"
    telegram_user_id = str(payload.get("telegram_user_id") or "preview-user").strip() or "preview-user"
    telegram_username = str(payload.get("telegram_username") or "preview_user").strip() or "preview_user"
    telegram_first_name = str(payload.get("telegram_first_name") or "Preview").strip() or "Preview"
    chat_id = str(payload.get("chat_id") or "preview-chat").strip() or "preview-chat"
    message_id = str(payload.get("message_id") or "preview-message").strip() or "preview-message"
    received_at = _utc_now_text()
    telegram = {
        "message_text": message_text,
        "user_id": telegram_user_id,
        "username": telegram_username,
        "first_name": telegram_first_name,
        "chat_id": chat_id,
        "message_id": message_id,
        "received_at": received_at,
        "preview": True,
    }
    return {
        "message_text": message_text,
        "telegram_user_id": telegram_user_id,
        "telegram_username": telegram_username,
        "telegram_first_name": telegram_first_name,
        "chat_id": chat_id,
        "message_id": message_id,
        "received_at": received_at,
        "telegram": telegram,
        "trigger_event_id": source_event_id,
        "source_event": {
            "id": source_event_id,
            "source": "telegram_preview",
            "event_type": "telegram.message.received",
            "preview": True,
            "received_at": received_at,
        },
        "preview_mode": True,
        "integration_id": str(google_sheets.get("integration_id") or "").strip(),
        "spreadsheet_id": str(google_sheets.get("spreadsheet_id") or "").strip(),
        "sheet_name": str(google_sheets.get("sheet_name") or "Leads").strip() or "Leads",
    }


def _build_agent_preview_run_input(blueprint: dict, version: dict | None, payload: dict) -> dict:
    metadata = _blueprint_metadata(blueprint)
    user_input = payload.get("input") if isinstance(payload.get("input"), dict) else {}
    preview = metadata.get("agent_builder_preview") if isinstance(metadata.get("agent_builder_preview"), dict) else {}
    custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
    required_bindings = metadata.get("required_integration_bindings") if isinstance(metadata.get("required_integration_bindings"), list) else []
    if not required_bindings and version:
        version_payload = build_version_payload_from_row(version)
        required_bindings = version_payload.get("required_integration_bindings") if isinstance(version_payload.get("required_integration_bindings"), list) else []
    version_payload = build_version_payload_from_row(version or {}) if version else {}
    capability_allowlist = version_payload.get("capability_allowlist") if isinstance(version_payload.get("capability_allowlist"), list) else []
    steps = version_payload.get("steps") if isinstance(version_payload.get("steps"), list) else []
    trigger_event_id = str(user_input.get("trigger_event_id") or f"preview-{uuid.uuid4()}")
    received_at = _utc_now_text()
    sample_rows = _preview_sample_rows(custom_process, user_input)
    provider_bindings = _preview_provider_bindings(required_bindings)
    connector_action_handlers = _preview_connector_action_handlers(metadata)
    openclaw_action_plan = _preview_openclaw_action_plan(steps)
    openclaw_route_plan = _preview_openclaw_route_plan(connector_action_handlers, required_bindings)
    openclaw_action_plan = _dedupe_preview_openclaw_action_plan(openclaw_action_plan + openclaw_route_plan)
    google_sheets_config = custom_process.get("google_sheets") if isinstance(custom_process.get("google_sheets"), dict) else {}
    telegram_config = custom_process.get("telegram") if isinstance(custom_process.get("telegram"), dict) else {}
    preview_input = {
        **user_input,
        "schema": "localos_agent_preview_input_v1",
        "preview_mode": True,
        "source": "agent_preview",
        "business_id": str(blueprint.get("business_id") or user_input.get("business_id") or ""),
        "blueprint_id": str(blueprint.get("id") or ""),
        "blueprint_version_id": str((version or {}).get("id") or user_input.get("blueprint_version_id") or ""),
        "category": str(blueprint.get("category") or preview.get("category") or ""),
        "goal": str((version or {}).get("goal") or preview.get("understood_task") or blueprint.get("description") or ""),
        "trigger_event_id": trigger_event_id,
        "external_side_effects_allowed": False,
        "approval_required_for_external_actions": True,
        "capability_allowlist": [str(item) for item in capability_allowlist],
        "required_connectors": _preview_required_connectors(metadata, required_bindings),
        "provider_bindings": provider_bindings,
        "connector_action_handlers": connector_action_handlers,
        "openclaw_preview_routes": openclaw_route_plan,
        "openclaw_action_plan": openclaw_action_plan,
        "policy_envelope": {
            "runtime": "localos_compiled_workflow",
            "execution_boundary": "openclaw_action_orchestrator",
            "external_side_effects_allowed_in_preview": False,
            "approval_required_for_external_actions": True,
        },
        "source_event": {
            "id": trigger_event_id,
            "source": "agent_preview",
            "event_type": str(version_payload.get("trigger") or custom_process.get("trigger") or "manual.preview"),
            "preview": True,
            "received_at": received_at,
        },
        "preview_context": {
            "understood_task": str(preview.get("understood_task") or blueprint.get("description") or ""),
            "data_sources": preview.get("data_sources") if isinstance(preview.get("data_sources"), list) else [],
            "manual_control": str(preview.get("manual_control") or "Ручное подтверждение перед внешним действием."),
            "steps": _preview_step_summaries(steps),
            "expected_result": str(preview.get("output_format") or ""),
        },
    }
    if sample_rows:
        preview_input["google_sheets"] = {
            "preview": True,
            "sample_rows": sample_rows,
            "selected_row_strategy": "previous_day_sample",
            "read_only": True,
        }
    if _has_provider(required_bindings, "google_sheets") or google_sheets_config:
        google_sheets_preview = preview_input.get("google_sheets") if isinstance(preview_input.get("google_sheets"), dict) else {}
        google_sheets_preview.update(
            {
                "preview": True,
                "read_only": True,
                "integration_id": str(google_sheets_config.get("integration_id") or "").strip(),
                "spreadsheet_id": str(google_sheets_config.get("spreadsheet_id") or "").strip(),
                "spreadsheet_url": str(google_sheets_config.get("spreadsheet_url") or "").strip(),
                "sheet_name": str(google_sheets_config.get("sheet_name") or "").strip(),
                "gid": str(google_sheets_config.get("gid") or "").strip(),
            }
        )
        preview_input["google_sheets"] = google_sheets_preview
    if _has_provider(required_bindings, "telegram") or "telegram" in custom_process.get("archetype", ""):
        preview_input["telegram"] = {
            "preview": True,
            "draft_only": True,
            "external_publish_performed": False,
            "message_style": _preview_message_style(preview, custom_process),
            "integration_id": str(telegram_config.get("integration_id") or "").strip(),
            "telegram_target": str(telegram_config.get("telegram_target") or telegram_config.get("chat_id") or "").strip(),
            "target_type": str(telegram_config.get("target_type") or "").strip(),
        }
    return preview_input


def _preview_required_connectors(metadata: dict, required_bindings: list) -> list[dict]:
    preview_connectors = metadata.get("required_connectors") if isinstance(metadata.get("required_connectors"), list) else []
    if preview_connectors:
        return preview_connectors
    result = []
    for item in required_bindings:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "key": str(item.get("key") or ""),
                "provider": str(item.get("provider") or ""),
                "capability": str(item.get("capability") or ""),
                "direction": str(item.get("direction") or ""),
            }
        )
    return result


def _preview_provider_bindings(required_bindings: list) -> list[dict]:
    result = []
    for item in required_bindings:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "key": str(item.get("key") or ""),
                "provider": str(item.get("provider") or ""),
                "capability": str(item.get("capability") or ""),
                "required_config": [str(value) for value in item.get("required_config", []) if str(value or "").strip()],
            }
        )
    return result


def _preview_connector_action_handlers(metadata: dict) -> list[dict]:
    handlers = metadata.get("connector_action_handlers") if isinstance(metadata.get("connector_action_handlers"), dict) else {}
    result = []
    for binding_key, handler in handlers.items():
        if not isinstance(handler, dict):
            continue
        result.append(
            {
                "binding_key": str(binding_key or handler.get("binding_key") or ""),
                "route_provider": str(handler.get("route_provider") or ""),
                "handler": str(handler.get("handler") or ""),
                "credential_source": str(handler.get("credential_source") or ""),
                "preflight_resolution": str(handler.get("preflight_resolution") or ""),
                "execution_boundary": str(handler.get("execution_boundary") or ""),
                "approval_required": bool(handler.get("approval_required", True)),
                "audit_required": bool(handler.get("audit_required", True)),
                "external_side_effects_allowed_in_preview": bool(handler.get("external_side_effects_allowed_in_preview")) is True,
                "next_step": str(handler.get("next_step") or ""),
            }
        )
    return result


def _preview_openclaw_route_plan(connector_action_handlers: list, required_bindings: list) -> list[dict]:
    binding_capabilities = {}
    for binding in required_bindings:
        if not isinstance(binding, dict):
            continue
        binding_key = str(binding.get("key") or "").strip()
        capability = str(binding.get("capability") or "").strip()
        provider = str(binding.get("provider") or "").strip()
        if binding_key:
            binding_capabilities[binding_key] = {"capability": capability, "provider": provider}
    result = []
    for handler in connector_action_handlers:
        if not isinstance(handler, dict):
            continue
        if str(handler.get("handler") or "") != "openclaw_policy_boundary":
            continue
        binding_key = str(handler.get("binding_key") or "").strip()
        binding = binding_capabilities.get(binding_key) or {}
        capability = str(binding.get("capability") or "").strip()
        result.append(
            {
                "step_key": binding_key,
                "title": f"OpenClaw preview: {binding_key}",
                "capability": capability,
                "provider": "openclaw",
                "provider_action_ref": _preview_openclaw_action_ref(capability),
                "provider_policy": "localos_envelope",
                "risk_class": "dry_run",
                "approval_class": "preview_only",
                "requires_approval": True,
                "binding_key": binding_key,
                "handler": "openclaw_policy_boundary",
                "preflight_resolution": str(handler.get("preflight_resolution") or ""),
                "external_side_effects_allowed_in_preview": False,
            }
        )
    return result


def _preview_openclaw_action_ref(capability: str) -> str:
    capability_key = str(capability or "").strip()
    if capability_key:
        return f"openclaw.{capability_key}"
    return "openclaw.preview.inspect_binding"


def _dedupe_preview_openclaw_action_plan(items: list) -> list[dict]:
    result = []
    seen = set()
    for item in items:
        if not isinstance(item, dict):
            continue
        key = (
            str(item.get("step_key") or item.get("key") or ""),
            str(item.get("provider_action_ref") or ""),
            str(item.get("capability") or ""),
        )
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def _preview_openclaw_action_plan(steps: list) -> list[dict]:
    result = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        action_ref = str(step.get("provider_action_ref") or "").strip()
        provider = str(step.get("provider") or "").strip()
        capability = str(step.get("capability") or "").strip()
        if not action_ref and provider != "openclaw":
            continue
        result.append(
            {
                "step_key": str(step.get("key") or ""),
                "title": str(step.get("title") or step.get("key") or ""),
                "capability": capability,
                "provider": provider or ("openclaw" if action_ref.startswith("openclaw.") else ""),
                "provider_action_ref": action_ref,
                "provider_policy": str(step.get("provider_policy") or "localos_envelope"),
                "risk_class": str(step.get("provider_risk_class") or ""),
                "approval_class": str(step.get("provider_approval_class") or ""),
                "requires_approval": bool(step.get("requires_approval")),
            }
        )
    return result


def _preview_step_summaries(steps: list) -> list[dict]:
    result = []
    for step in steps[:12]:
        if not isinstance(step, dict):
            continue
        result.append(
            {
                "key": str(step.get("key") or ""),
                "type": str(step.get("type") or ""),
                "title": str(step.get("title") or step.get("key") or ""),
                "capability": str(step.get("capability") or ""),
                "artifact_type": str(step.get("artifact_type") or ""),
                "requires_approval": bool(step.get("requires_approval")),
            }
        )
    return result


def _preview_sample_rows(custom_process: dict, user_input: dict) -> list[dict]:
    rows = user_input.get("sample_rows") if isinstance(user_input.get("sample_rows"), list) else []
    if rows:
        return [item for item in rows[:5] if isinstance(item, dict)]
    archetype = str(custom_process.get("archetype") or "")
    if archetype == "google_sheets_to_telegram":
        return [
            {
                "date": "yesterday",
                "route": "Los Angeles airport → Santa Barbara",
                "passenger_name": "Preview passenger",
                "status": "completed",
            }
        ]
    if str(custom_process.get("source") or "") == "google_sheets.read_rows":
        return [{"date": "yesterday", "amount": "1000", "status": "preview"}]
    return []


def _preview_message_style(preview: dict, custom_process: dict) -> str:
    output_format = str(preview.get("output_format") or "").strip()
    style = str(custom_process.get("style") or custom_process.get("message_style") or "").strip()
    return style or output_format or "Черновик в стиле, описанном пользователем."


def _has_provider(required_bindings: list, provider: str) -> bool:
    return any(isinstance(item, dict) and str(item.get("provider") or "") == provider for item in required_bindings)


def _sync_blueprint_integration_metadata(cursor, blueprint: dict, integration: dict, binding_key: str = "") -> dict:
    blueprint_id = str(blueprint.get("id") or "")
    metadata = _blueprint_metadata(_load_blueprint(cursor, blueprint_id) or blueprint)
    integration_ids = _agent_integration_ids(metadata)
    integration_id = str(integration.get("id") or "").strip()
    if integration_id and integration_id not in integration_ids:
        integration_ids.append(integration_id)
    metadata["agent_integration_ids"] = integration_ids[-25:]
    capability_integrations = metadata.get("capability_integrations") if isinstance(metadata.get("capability_integrations"), dict) else {}
    provider = str(integration.get("provider") or "").strip()
    if provider:
        capability_integrations[provider] = integration_id
    metadata["capability_integrations"] = capability_integrations
    binding_key = str(binding_key or "").strip()
    if binding_key and integration_id:
        binding_integrations = metadata.get("agent_binding_integrations") if isinstance(metadata.get("agent_binding_integrations"), dict) else {}
        binding_integrations[binding_key] = {
            "integration_id": integration_id,
            "provider": provider,
            "attached_at": _utc_now_text(),
        }
        metadata["agent_binding_integrations"] = binding_integrations
    if provider == "google_sheets":
        custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
        custom_process["trigger"] = str(custom_process.get("trigger") or "telegram.message.received")
        config = workspace_parse_json_field(integration.get("config_json"), {})
        if not isinstance(config, dict):
            config = {}
        custom_process["google_sheets"] = {
            "integration_id": integration_id,
            "spreadsheet_id": str(config.get("spreadsheet_id") or "").strip(),
            "sheet_name": str(config.get("sheet_name") or "Sheet1").strip() or "Sheet1",
            "operation": str(config.get("operation") or "read_write").strip() or "read_write",
        }
        if binding_key:
            custom_process[binding_key] = dict(custom_process["google_sheets"])
        custom_process["binding_status"] = "connected"
        metadata["custom_process"] = custom_process
    if provider == "telegram":
        custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
        config = workspace_parse_json_field(integration.get("config_json"), {})
        if not isinstance(config, dict):
            config = {}
        telegram_binding = {
            "integration_id": integration_id,
            "bot_mode": str(config.get("bot_mode") or "business_bot").strip() or "business_bot",
        }
        custom_process["telegram"] = telegram_binding
        if binding_key:
            custom_process[binding_key] = dict(telegram_binding)
        metadata["custom_process"] = custom_process
        triggers = metadata.get("triggers") if isinstance(metadata.get("triggers"), list) else []
        if "telegram.message.received" not in triggers:
            triggers.append("telegram.message.received")
        metadata["triggers"] = triggers[-10:]
    _save_blueprint_metadata(cursor, blueprint_id, metadata)
    return metadata


def _required_binding_by_key(metadata: dict, binding_key: str) -> dict:
    binding_key = str(binding_key or "").strip()
    required = metadata.get("required_integration_bindings") if isinstance(metadata.get("required_integration_bindings"), list) else []
    for item in required:
        if isinstance(item, dict) and str(item.get("key") or "").strip() == binding_key:
            return item
    return {}


def _route_is_allowed_for_binding(binding: dict, route_provider: str) -> bool:
    route_provider = str(route_provider or "").strip()
    if not route_provider:
        return False
    routes = connector_provider_routes(str(binding.get("provider") or ""), str(binding.get("capability") or ""))
    return any(str(route.get("provider") or "").strip() == route_provider and str(route.get("state") or "") in {"available", "manual"} for route in routes)


def _load_external_auth_option(cursor, business_id: str, source: str, account_id: str) -> dict:
    if not business_id or not source or not account_id:
        return {}
    try:
        cursor.execute(
            """
            SELECT id, source, external_id, display_name, is_active, updated_at
            FROM externalbusinessaccounts
            WHERE business_id = %s
              AND source = %s
              AND id = %s
              AND is_active = TRUE
            LIMIT 1
            """,
            (business_id, source, account_id),
        )
        row = cursor.fetchone()
    except Exception:
        row = None
    return dict(row) if row else {}


def _resolve_agent_integration_auth_ref(cursor, business_id: str, provider: str, requested_auth_ref: str = "") -> str | None:
    requested_auth_ref = str(requested_auth_ref or "").strip()
    if requested_auth_ref:
        cursor.execute(
            """
            SELECT id
            FROM externalbusinessaccounts
            WHERE business_id = %s
              AND id = %s
              AND is_active = TRUE
            LIMIT 1
            """,
            (business_id, requested_auth_ref),
        )
        row = cursor.fetchone()
        return str(row.get("id") if hasattr(row, "get") else row[0]) if row else None
    if provider != "google_sheets":
        return None
    try:
        cursor.execute(
            """
            SELECT id
            FROM externalbusinessaccounts
            WHERE business_id = %s
              AND is_active = TRUE
              AND source IN ('google_sheets', 'google_business')
              AND COALESCE(auth_data_encrypted, '') <> ''
            ORDER BY
              CASE WHEN source = 'google_sheets' THEN 0 ELSE 1 END,
              updated_at DESC NULLS LAST,
              created_at DESC NULLS LAST
            LIMIT 1
            """,
            (business_id,),
        )
        row = cursor.fetchone()
    except Exception:
        row = None
    return str(row.get("id") if hasattr(row, "get") else row[0]) if row else None


def _apply_agent_provider_route_metadata(
    cursor,
    blueprint: dict,
    *,
    binding_key: str,
    route_provider: str,
    external_account: dict | None = None,
) -> dict:
    metadata = _blueprint_metadata(_load_blueprint(cursor, str(blueprint.get("id") or "")) or blueprint)
    routes = metadata.get("agent_binding_provider_routes") if isinstance(metadata.get("agent_binding_provider_routes"), dict) else {}
    external_account = external_account if isinstance(external_account, dict) else {}
    route_payload = {
        "binding_key": binding_key,
        "route_provider": route_provider,
        "status": "active",
        "selected_at": _utc_now_text(),
        "selected_by": "user",
    }
    if route_provider == "openclaw":
        route_payload.update(
            {
                "integration_id": "openclaw_boundary",
                "execution_boundary": "localos_policy_envelope",
                "requires_external_credentials": False,
            }
        )
    if route_provider == "maton":
        route_payload.update(
            {
                "integration_id": str(external_account.get("id") or ""),
                "external_account_id": str(external_account.get("id") or ""),
                "auth_ref": str(external_account.get("id") or ""),
                "display_name": str(external_account.get("display_name") or "Maton.ai"),
                "execution_boundary": "localos_policy_envelope",
                "requires_external_credentials": True,
            }
        )
    if route_provider == "manual":
        route_payload.update(
            {
                "integration_id": "manual_fallback",
                "execution_boundary": "human_operated_fallback",
                "requires_external_credentials": False,
                "draft_only_until_human_action": True,
            }
        )
    routes[binding_key] = route_payload
    metadata["agent_binding_provider_routes"] = routes

    binding_integrations = metadata.get("agent_binding_integrations") if isinstance(metadata.get("agent_binding_integrations"), dict) else {}
    binding_integrations[binding_key] = dict(route_payload)
    metadata["agent_binding_integrations"] = binding_integrations
    _save_blueprint_metadata(cursor, str(blueprint.get("id") or ""), metadata)
    return metadata


def _utc_now_text() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _version_number(version: dict | None) -> int:
    try:
        return int((version or {}).get("version_number") or 0)
    except Exception:
        return 0


def _resolve_active_version(cursor, blueprint: dict):
    metadata = _blueprint_metadata(blueprint)
    active_version_id = str(metadata.get("active_version_id") or "").strip()
    if active_version_id:
        version = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), active_version_id)
        if version:
            return version
    return _load_latest_blueprint_version(cursor, str(blueprint.get("id") or ""))


def _remember_active_version(cursor, blueprint: dict, version: dict, user_data: dict, action: str, reason: str = "") -> dict:
    blueprint_id = str(blueprint.get("id") or "")
    refreshed_blueprint = _load_blueprint(cursor, blueprint_id) if blueprint_id else None
    metadata = _blueprint_metadata(refreshed_blueprint or blueprint)
    previous_active_id = str(metadata.get("active_version_id") or "").strip()
    event = {
        "action": action,
        "previous_active_version_id": previous_active_id,
        "active_version_id": str(version.get("id") or ""),
        "active_version_number": _version_number(version),
        "reason": reason,
        "created_by_user_id": _user_id(user_data),
        "created_at": _utc_now_text(),
    }
    events = metadata.get("version_events") if isinstance(metadata.get("version_events"), list) else []
    events.append(event)
    metadata["active_version_id"] = event["active_version_id"]
    metadata["active_version_number"] = event["active_version_number"]
    metadata["active_version_updated_at"] = event["created_at"]
    metadata["version_events"] = events[-50:]
    _save_blueprint_metadata(cursor, blueprint_id, metadata)
    cursor.execute(
        """
        UPDATE agent_blueprints
        SET status = 'active',
            updated_at = NOW()
        WHERE id = %s
          AND status <> 'archived'
        """,
        (blueprint_id,),
    )
    return event


def _version_was_active_before(blueprint: dict, version: dict) -> bool:
    version_id = str((version or {}).get("id") or "").strip()
    if not version_id:
        return False
    metadata = _blueprint_metadata(blueprint)
    if str(metadata.get("active_version_id") or "").strip() == version_id:
        return True
    events = metadata.get("version_events") if isinstance(metadata.get("version_events"), list) else []
    for event in events:
        if not isinstance(event, dict):
            continue
        if str(event.get("active_version_id") or "").strip() == version_id:
            return True
    return False


def _decorate_versions(cursor, blueprint: dict, versions: list[dict]) -> tuple[list[dict], dict | None]:
    active_version = _resolve_active_version(cursor, blueprint)
    active_version_id = str((active_version or {}).get("id") or "")
    by_number = {_version_number(version): version for version in versions}
    decorated = []
    for version in versions:
        previous = by_number.get(_version_number(version) - 1)
        decorated_version = dict(version)
        decorated_version["is_active"] = str(version.get("id") or "") == active_version_id
        decorated_version["active_state"] = "active" if decorated_version["is_active"] else "inactive"
        decorated_version["diff_from_previous"] = build_agent_version_diff(previous, version)
        decorated.append(decorated_version)
    return decorated, active_version


def _require_blueprint_access(cursor, blueprint_id: str, user_data: dict):
    blueprint = _load_blueprint(cursor, blueprint_id)
    if not blueprint:
        return None, _json_error("Blueprint not found", 404, "NOT_FOUND")
    allowed, error_response = _require_business_access(cursor, str(blueprint.get("business_id") or ""), user_data)
    if not allowed:
        return None, error_response
    return blueprint, None


def _without_archived_clause(where_sql: str) -> str:
    if where_sql.strip():
        return f"{where_sql} AND b.status <> 'archived'"
    return "WHERE b.status <> 'archived'"


def _insert_version(cursor, blueprint_id: str, payload: dict, user_data: dict):
    cursor.execute(
        "SELECT COALESCE(MAX(version_number), 0) + 1 AS next_version FROM agent_blueprint_versions WHERE blueprint_id = %s",
        (blueprint_id,),
    )
    version_row = cursor.fetchone() or {}
    version_number = int(version_row.get("next_version") or 1)
    version_id = str(uuid.uuid4())
    steps = normalize_steps(payload.get("steps"))
    cursor.execute(
        """
        INSERT INTO agent_blueprint_versions (
            id, blueprint_id, version_number, goal, inputs_schema_json, steps_json,
            persona_agent_id, capability_allowlist_json, approval_policy_json,
            output_schema_json, created_by_user_id
        )
        VALUES (%s, %s, %s, %s, %s::jsonb, %s::jsonb, %s, %s::jsonb, %s::jsonb, %s::jsonb, %s)
        """,
        (
            version_id,
            blueprint_id,
            version_number,
            str(payload.get("goal") or "").strip(),
            json.dumps(payload.get("inputs_schema") if isinstance(payload.get("inputs_schema"), dict) else {}, ensure_ascii=False),
            json.dumps(steps, ensure_ascii=False),
            str(payload.get("persona_agent_id") or "").strip() or None,
            json.dumps(payload.get("capability_allowlist") if isinstance(payload.get("capability_allowlist"), list) else [], ensure_ascii=False),
            json.dumps(payload.get("approval_policy") if isinstance(payload.get("approval_policy"), dict) else {}, ensure_ascii=False),
            json.dumps(payload.get("output_schema") if isinstance(payload.get("output_schema"), dict) else {}, ensure_ascii=False),
            _user_id(user_data),
        ),
    )
    cursor.execute("SELECT * FROM agent_blueprint_versions WHERE id = %s", (version_id,))
    return _normalize_json_row(dict(cursor.fetchone()))


@agent_blueprints_bp.route("/api/admin/agent-blueprints/overview", methods=["GET"])
def admin_agent_blueprints_overview():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    if not user_data.get("is_superadmin"):
        return _json_error("Forbidden", 403, "FORBIDDEN")

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute(
            """
            SELECT b.id,
                   b.business_id,
                   COALESCE(biz.name, '') business_name,
                   COALESCE(owner.email, '') owner_email,
                   COALESCE(creator.email, '') creator_email,
                   b.name,
                   b.category,
                   b.description,
                   b.status,
                   b.metadata_json,
                   b.created_at,
                   b.updated_at,
                   b.created_by_user_id,
                   v.id latest_version_id,
                   v.version_number latest_version_number,
                   v.goal latest_goal,
                   v.steps_json,
                   v.approval_policy_json,
                   v.capability_allowlist_json,
                   COALESCE(rs.runs_count, 0) runs_count,
                   COALESCE(ap.pending_approvals_count, 0) pending_approvals_count,
                   COALESCE(src.sources_count, 0) sources_count,
                   COALESCE(integ.integration_count, 0) integration_count,
                   COALESCE(integ.providers, '') integration_providers
            FROM agent_blueprints b
            LEFT JOIN businesses biz ON biz.id = b.business_id
            LEFT JOIN users owner ON owner.id = biz.owner_id
            LEFT JOIN users creator ON creator.id = b.created_by_user_id
            LEFT JOIN LATERAL (
                SELECT id, version_number, goal, steps_json, approval_policy_json, capability_allowlist_json
                FROM agent_blueprint_versions
                WHERE blueprint_id = b.id
                ORDER BY version_number DESC
                LIMIT 1
            ) v ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) runs_count
                FROM agent_runs
                WHERE blueprint_id = b.id
            ) rs ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) pending_approvals_count
                FROM agent_approvals a
                JOIN agent_runs r ON r.id = a.run_id
                WHERE r.blueprint_id = b.id
                  AND a.status = 'pending'
            ) ap ON TRUE
            LEFT JOIN LATERAL (
                SELECT COALESCE(jsonb_array_length(CASE WHEN jsonb_typeof(b.metadata_json->'agent_sources') = 'array' THEN b.metadata_json->'agent_sources' ELSE '[]'::jsonb END), 0) sources_count
            ) src ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) integration_count,
                       string_agg(DISTINCT provider, ', ' ORDER BY provider) providers
                FROM agent_integrations
                WHERE business_id = b.business_id
                  AND status = 'active'
            ) integ ON TRUE
            ORDER BY b.created_at DESC
            LIMIT 200
            """
        )
        rows = [_normalize_json_row(dict(row)) for row in (cursor.fetchall() or [])]
        agents = []
        summary = {
            "total": len(rows),
            "draft": 0,
            "active": 0,
            "archived": 0,
            "high_risk": 0,
            "medium_risk": 0,
            "low_risk": 0,
        }
        for row in rows:
            review = _build_admin_agent_review(row)
            status = str(row.get("status") or "draft")
            risk_level = str(review.get("risk_level") or "low")
            if status in summary:
                summary[status] = int(summary[status]) + 1
            if risk_level == "high":
                summary["high_risk"] = int(summary["high_risk"]) + 1
            elif risk_level == "medium":
                summary["medium_risk"] = int(summary["medium_risk"]) + 1
            else:
                summary["low_risk"] = int(summary["low_risk"]) + 1
            agents.append(
                {
                    "id": str(row.get("id") or ""),
                    "business_id": str(row.get("business_id") or ""),
                    "business_name": str(row.get("business_name") or "Без бизнеса"),
                    "owner_email": str(row.get("owner_email") or ""),
                    "creator_email": str(row.get("creator_email") or ""),
                    "name": str(row.get("name") or "Без названия"),
                    "category": str(row.get("category") or "custom"),
                    "description": str(row.get("description") or ""),
                    "status": status,
                    "latest_goal": str(row.get("latest_goal") or ""),
                    "latest_version_number": row.get("latest_version_number"),
                    "runs_count": int(row.get("runs_count") or 0),
                    "pending_approvals_count": int(row.get("pending_approvals_count") or 0),
                    "sources_count": int(row.get("sources_count") or 0),
                    "integration_count": int(row.get("integration_count") or 0),
                    "integration_providers": str(row.get("integration_providers") or ""),
                    "created_at": row.get("created_at").isoformat() if row.get("created_at") else None,
                    "updated_at": row.get("updated_at").isoformat() if row.get("updated_at") else None,
                    "risk_level": risk_level,
                    "risk_reasons": review.get("risk_reasons") or [],
                }
            )
        return jsonify({"success": True, "summary": summary, "agents": agents})
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints", methods=["GET"])
def list_agent_blueprints():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        business_id = str(request.args.get("business_id") or "").strip()
        params = []
        where_sql = ""
        if business_id:
            allowed, access_error = _require_business_access(cursor, business_id, user_data)
            if not allowed:
                return access_error
            where_sql = "WHERE b.business_id = %s"
            params.append(business_id)
        elif not user_data.get("is_superadmin"):
            where_sql = """
            WHERE b.business_id IN (
                SELECT id FROM businesses WHERE owner_id = %s
            )
            """
            params.append(_user_id(user_data))
        cursor.execute(
            f"""
            SELECT b.*,
                   v.id AS latest_version_id,
                   v.version_number AS latest_version_number,
                   v.goal AS latest_goal,
                   v.persona_agent_id latest_persona_agent_id,
                   av.id AS active_version_id,
                   av.version_number AS active_version_number,
                   av.goal AS active_goal,
                   av.persona_agent_id active_persona_agent_id,
                   lr.id last_run_id,
                   lr.status last_run_status,
                   lr.started_at last_run_started_at,
                   lr.completed_at last_run_completed_at,
                   COALESCE(pq.pending_approvals_count, 0) pending_approvals_count,
                   COALESCE(vs.versions_count, 0) versions_count,
                   COALESCE(jsonb_array_length(CASE WHEN jsonb_typeof(b.metadata_json->'agent_sources') = 'array' THEN b.metadata_json->'agent_sources' ELSE '[]'::jsonb END), 0) sources_count,
                   COALESCE(jsonb_array_length(CASE WHEN jsonb_typeof(b.metadata_json->'agent_journal') = 'array' THEN b.metadata_json->'agent_journal' ELSE '[]'::jsonb END), 0) journal_entries_count
            FROM agent_blueprints b
            LEFT JOIN LATERAL (
                SELECT id, version_number, goal, persona_agent_id
                FROM agent_blueprint_versions
                WHERE blueprint_id = b.id
                ORDER BY version_number DESC
                LIMIT 1
            ) v ON TRUE
            LEFT JOIN LATERAL (
                SELECT id, version_number, goal, persona_agent_id
                FROM agent_blueprint_versions
                WHERE blueprint_id = b.id
                  AND id = COALESCE(NULLIF(b.metadata_json->>'active_version_id', ''), v.id)
                LIMIT 1
            ) av ON TRUE
            LEFT JOIN LATERAL (
                SELECT id, status, started_at, completed_at
                FROM agent_runs
                WHERE blueprint_id = b.id
                ORDER BY started_at DESC
                LIMIT 1
            ) lr ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) pending_approvals_count
                FROM agent_approvals a
                JOIN agent_runs r ON r.id = a.run_id
                WHERE r.blueprint_id = b.id
                  AND a.status = 'pending'
            ) pq ON TRUE
            LEFT JOIN LATERAL (
                SELECT COUNT(*) versions_count
                FROM agent_blueprint_versions
                WHERE blueprint_id = b.id
            ) vs ON TRUE
            {_without_archived_clause(where_sql)}
            ORDER BY b.created_at DESC
            LIMIT 200
            """,
            tuple(params),
        )
        rows = [_normalize_json_row(dict(row)) for row in (cursor.fetchall() or [])]
        personas = _load_personas_by_id(cursor, collect_persona_agent_ids(rows))
        decorated_rows = []
        for row in rows:
            active_version = {
                "id": row.get("active_version_id") or row.get("latest_version_id"),
                "version_number": row.get("active_version_number") or row.get("latest_version_number"),
                "persona_agent_id": row.get("active_persona_agent_id") or row.get("latest_persona_agent_id"),
            }
            decorated_rows.append(attach_product_agent_to_blueprint(row, active_version, personas))
        return jsonify({"success": True, "blueprints": decorated_rows})
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints", methods=["POST"])
def create_agent_blueprint():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    name = str(payload.get("name") or "").strip()
    category = str(payload.get("category") or "custom").strip().lower()
    if not business_id or not name:
        return _json_error("business_id and name are required", 400, "VALIDATION_ERROR")

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        allowed, access_error = _require_business_access(cursor, business_id, user_data)
        if not allowed:
            return access_error
        blueprint_id = str(uuid.uuid4())
        template = str(payload.get("template") or "").strip().lower()
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        cursor.execute(
            """
            INSERT INTO agent_blueprints (
                id, business_id, name, category, description, status, created_by_user_id, metadata_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                blueprint_id,
                business_id,
                name,
                category,
                str(payload.get("description") or "").strip() or None,
                str(payload.get("status") or "draft").strip().lower(),
                _user_id(user_data),
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        version = None
        if template == "supervised_outreach" or payload.get("create_default_version"):
            version_payload = default_supervised_outreach_version_payload()
            version_payload["persona_agent_id"] = payload.get("persona_agent_id")
            version = _insert_version(cursor, blueprint_id, version_payload, user_data)
            _remember_active_version(cursor, {"id": blueprint_id, "metadata_json": metadata}, version, user_data, "created")
        db.conn.commit()
        blueprint = _load_blueprint(cursor, blueprint_id)
        return jsonify(
            {
                "success": True,
                "blueprint": _normalize_json_row(blueprint),
                "version": version,
            }
        ), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/draft", methods=["POST"])
def create_agent_blueprint_draft():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    description = str(payload.get("description") or "").strip()
    if not business_id or not description:
        return _json_error("business_id and description are required", 400, "VALIDATION_ERROR")

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        allowed, access_error = _require_business_access(cursor, business_id, user_data)
        if not allowed:
            return access_error
        connection_inventory = _load_direct_builder_connection_inventory(cursor, business_id)
        builder_state = build_agent_builder_state(
            [{"role": "user", "content": description}],
            str(payload.get("category") or ""),
            use_ai=False,
            business_id=business_id,
            user_id=_user_id(user_data),
            connected_integrations=connection_inventory,
        )
        preview = builder_state.get("preview") if isinstance(builder_state.get("preview"), dict) else {}
        feasibility = preview.get("feasibility") if isinstance(preview.get("feasibility"), dict) else {}
        setup_flow = preview.get("setup_flow") if isinstance(preview.get("setup_flow"), dict) else {}
        if feasibility.get("status") == "forbidden":
            return jsonify(
                {
                    "success": False,
                    "error": "Такой агент не может быть создан в рамках политики LocalOS.",
                    "code": "AGENT_REQUEST_FORBIDDEN",
                    "feasibility": feasibility,
                    "setup_flow": setup_flow,
                }
            ), 400
        selected_bindings = _direct_selected_connection_bindings(payload, preview, connection_inventory)
        missing_connection_choices = _direct_missing_required_connection_choices(preview, selected_bindings)
        if missing_connection_choices:
            return jsonify(
                {
                    "success": False,
                    "error": "Выберите, какие существующие подключения использовать для агента.",
                    "code": "AGENT_CONNECTION_CHOICE_REQUIRED",
                    "missing_connection_choices": missing_connection_choices,
                    "connection_summary": preview.get("connection_summary") if isinstance(preview.get("connection_summary"), dict) else {},
                    "setup_flow": setup_flow,
                }
            ), 400
        selected_provider_routes = _selected_provider_routes(payload, preview, connection_inventory)
        missing_provider_routes = _missing_required_provider_routes(preview, selected_provider_routes)
        if missing_provider_routes:
            return jsonify(
                {
                    "success": False,
                    "error": "Выберите provider route для обязательных шагов агента.",
                    "code": "AGENT_PROVIDER_ROUTE_REQUIRED",
                    "missing_provider_routes": missing_provider_routes,
                    "connection_readiness": preview.get("connection_readiness") if isinstance(preview.get("connection_readiness"), dict) else {},
                    "setup_flow": setup_flow,
                }
            ), 400
        if _required_provider_route_bindings(preview) and not bool(payload.get("accepted_provider_routes")):
            return jsonify(
                {
                    "success": False,
                    "error": "Подтвердите выбранные provider routes перед созданием draft.",
                    "code": "AGENT_PROVIDER_ROUTES_CONFIRMATION_REQUIRED",
                    "selected_provider_routes": selected_provider_routes,
                    "connection_readiness": preview.get("connection_readiness") if isinstance(preview.get("connection_readiness"), dict) else {},
                    "setup_flow": setup_flow,
                    "next_step": "accept_provider_routes",
                    "next_step_title": "Подтвердите routes агента",
                }
            ), 400
        planner_context = preview.get("openclaw_planner_context") if isinstance(preview.get("openclaw_planner_context"), dict) else {}
        planner_loop = preview.get("openclaw_planner_loop") if isinstance(preview.get("openclaw_planner_loop"), dict) else {}
        draft = build_agent_blueprint_draft(
            description,
            str(payload.get("category") or ""),
            use_ai=bool(payload.get("use_ai_compiler")),
            business_id=business_id,
            user_id=_user_id(user_data),
            planner_context=planner_context,
        )
        blueprint_id = str(uuid.uuid4())
        billing = charge_agent_creation_credits(
            cursor,
            business_id=business_id,
            user_id=_user_id(user_data),
            source_id=blueprint_id,
            description=description,
            channel="agent_blueprint_draft",
        )
        if billing.get("status") == "blocked":
            db.conn.rollback()
            return jsonify(
                {
                    "success": False,
                    "error": "Недостаточно кредитов для создания агента.",
                    "code": "AGENT_CREATION_BILLING_BLOCKED",
                    "billing": billing,
                }
            ), 402
        metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
        metadata["builder"] = str(metadata.get("builder") or "direct_description_builder_v1")
        metadata["direct_draft_envelope"] = "localos_openclaw_policy_envelope_v1"
        metadata["agent_builder_preview"] = preview
        metadata["feasibility"] = feasibility
        metadata["openclaw_planner_context"] = planner_context
        metadata["openclaw_planner_loop"] = planner_loop
        metadata["required_connectors"] = preview.get("required_connectors") if isinstance(preview.get("required_connectors"), list) else []
        metadata["builder_setup_flow"] = setup_flow
        metadata["agent_setup"] = preview_to_setup(preview)
        metadata["setup_completed"] = bool(setup_flow.get("can_create_draft"))
        metadata["billing"] = billing
        metadata = _apply_direct_selected_connection_bindings(metadata, selected_bindings)
        metadata = _apply_selected_provider_routes(metadata, selected_provider_routes)
        metadata["builder_selected_connection_bindings"] = selected_bindings
        metadata["builder_selected_provider_routes"] = selected_provider_routes
        metadata["builder_provider_routes_accepted"] = bool(payload.get("accepted_provider_routes"))
        cursor.execute(
            """
            INSERT INTO agent_blueprints (
                id, business_id, name, category, description, status, created_by_user_id, metadata_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s::jsonb)
            """,
            (
                blueprint_id,
                business_id,
                str(draft.get("name") or "").strip() or "Кастомный агент",
                str(draft.get("category") or "custom").strip().lower(),
                str(draft.get("description") or "").strip() or None,
                "draft",
                _user_id(user_data),
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        version_payload = draft.get("version_payload") if isinstance(draft.get("version_payload"), dict) else {}
        version = _insert_version(cursor, blueprint_id, version_payload, user_data)
        _remember_active_version(cursor, {"id": blueprint_id, "metadata_json": metadata}, version, user_data, "created")
        connection_preflight = build_agent_integration_preflight(
            cursor,
            business_id=business_id,
            metadata=metadata,
            input_payload={},
        )
        connection_context = _agent_connection_context(cursor, business_id, metadata)
        connection_plan = _activation_connection_plan_from_preflight(
            connection_preflight,
            attached_integrations=connection_context["attached_integrations"],
            available_integrations=connection_context["available_integrations"],
            provider_catalog=connection_context["provider_catalog"],
        )
        post_create_handoff = _build_agent_post_connect_handoff(connection_plan)
        db.conn.commit()
        blueprint = _load_blueprint(cursor, blueprint_id)
        return jsonify(
            {
                "success": True,
                "blueprint": _normalize_json_row(blueprint),
                "version": version,
                "draft": {
                    "category": draft.get("category"),
                    "summary": draft.get("summary") if isinstance(draft.get("summary"), dict) else {},
                },
                "billing": billing,
                "setup_flow": setup_flow,
                "feasibility": feasibility,
                "connection_summary": preview.get("connection_summary") if isinstance(preview.get("connection_summary"), dict) else {},
                "connector_intelligence": preview.get("connector_intelligence") if isinstance(preview.get("connector_intelligence"), dict) else {},
                "openclaw_planner_loop": planner_loop,
                "selected_connection_bindings": selected_bindings,
                "selected_provider_routes": selected_provider_routes,
                "connection_preflight": connection_preflight,
                "connection_plan": connection_plan,
                "post_create_handoff": post_create_handoff,
                "next_step": str(setup_flow.get("post_create_next_step") or setup_flow.get("next_step") or ""),
            }
        ), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/legacy-migration-plan", methods=["GET"])
def get_agent_blueprint_legacy_migration_plan():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    business_id = str(request.args.get("business_id") or "").strip()
    if not business_id:
        return _json_error("business_id is required", 400, "VALIDATION_ERROR")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        allowed, access_error = _require_business_access(cursor, business_id, user_data)
        if not allowed:
            return access_error
        plan = build_legacy_ai_agent_migration_plan(cursor, business_id)
        return jsonify({"success": True, "migration_plan": plan})
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/legacy-migration/apply", methods=["POST"])
def apply_agent_blueprint_legacy_migration():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    if not business_id:
        return _json_error("business_id is required", 400, "VALIDATION_ERROR")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        allowed, access_error = _require_business_access(cursor, business_id, user_data)
        if not allowed:
            return access_error
        result = apply_legacy_ai_agent_migration(cursor, business_id, _user_id(user_data))
        db.conn.commit()
        return jsonify({"success": True, "migration": result})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>", methods=["GET"])
def get_agent_blueprint(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        cursor.execute(
            """
            SELECT *
            FROM agent_blueprint_versions
            WHERE blueprint_id = %s
            ORDER BY version_number DESC
            """,
            (blueprint_id,),
        )
        versions = [_normalize_json_row(dict(row)) for row in (cursor.fetchall() or [])]
        versions, active_version = _decorate_versions(cursor, blueprint, versions)
        personas = _load_personas_by_id(cursor, collect_persona_agent_ids(versions, [active_version] if active_version else []))
        versions = [attach_persona_to_version(version, personas) for version in versions]
        if active_version:
            active_version = attach_persona_to_version(_normalize_json_row(active_version), personas)
        decorated_blueprint = attach_product_agent_to_blueprint(_normalize_json_row(blueprint), active_version, personas)
        run_status = str(request.args.get("run_status") or "").strip().lower()
        run_params = [blueprint_id]
        run_where = "WHERE blueprint_id = %s"
        if run_status:
            run_where = f"{run_where} AND status = %s"
            run_params.append(run_status)
        cursor.execute(
            f"""
            SELECT *
            FROM agent_runs
            {run_where}
            ORDER BY started_at DESC
            LIMIT 50
            """,
            tuple(run_params),
        )
        runs = [_normalize_json_row(dict(row)) for row in (cursor.fetchall() or [])]
        cursor.execute(
            """
            SELECT a.*,
                   r.status run_status,
                   r.started_at run_started_at
            FROM agent_approvals a
            JOIN agent_runs r ON r.id = a.run_id
            WHERE r.blueprint_id = %s
              AND a.status = 'pending'
            ORDER BY a.requested_at ASC
            LIMIT 50
            """,
            (blueprint_id,),
        )
        approval_queue = [_normalize_json_row(dict(row)) for row in (cursor.fetchall() or [])]
        metadata = _blueprint_metadata(blueprint)
        learning_events = metadata.get("learning_events") if isinstance(metadata.get("learning_events"), list) else []
        version_events = metadata.get("version_events") if isinstance(metadata.get("version_events"), list) else []
        feedback_history = metadata.get("feedback_history") if isinstance(metadata.get("feedback_history"), list) else []
        legacy_migration = metadata.get("legacy_migration") if isinstance(metadata.get("legacy_migration"), dict) else {}
        metrics = build_agent_metrics_summary(decorated_blueprint, versions, active_version, runs, approval_queue, metadata)
        activation_gate = _build_activation_gate_summary(
            cursor,
            blueprint=blueprint,
            active_version=active_version,
            metadata=metadata,
        )
        return jsonify(
            {
                "success": True,
                "blueprint": decorated_blueprint,
                "active_version": active_version if active_version else None,
                "active_version_id": str((active_version or {}).get("id") or ""),
                "active_version_number": _version_number(active_version),
                "versions": versions,
                "runs": runs,
                "approval_queue": approval_queue,
                "learning_events": learning_events[-50:],
                "version_events": version_events[-50:],
                "feedback_history": feedback_history[-20:],
                "legacy_migration": legacy_migration,
                "metrics": metrics,
                "activation_gate": activation_gate,
            }
        )
    finally:
        db.close()


def _build_activation_gate_summary(cursor, blueprint: dict, active_version: dict | None, metadata: dict) -> dict:
    blockers = []
    compiled_validation = {}
    version_payload = {}
    preview_run_status = _activation_preview_run_status(
        cursor,
        str(blueprint.get("id") or ""),
        str((active_version or {}).get("id") or ""),
    )
    if not active_version:
        blockers.append({"type": "version", "message": "Создайте или выберите версию агента."})
    else:
        version_payload = build_version_payload_from_row(active_version)
        compiled_validation = validate_compiled_artifact_candidate(
            version_payload,
            metadata,
        )
        if not compiled_validation.get("ready"):
            blockers.append({"type": "compiled_validation", "message": "Compiled workflow не прошёл проверку."})
    approval_policy_status = _build_activation_approval_policy_status(version_payload, compiled_validation)
    if active_version and not approval_policy_status.get("ready"):
        blockers.append({"type": "approval_policy", "message": str(approval_policy_status.get("summary") or "Approval policy и limits требуют проверки.")})
    preflight = build_agent_integration_preflight(
        cursor,
        business_id=str(blueprint.get("business_id") or ""),
        metadata=metadata,
        input_payload={},
    )
    connection_context = _agent_connection_context(cursor, str(blueprint.get("business_id") or ""), metadata)
    connection_plan = _activation_connection_plan_from_preflight(
        preflight,
        attached_integrations=connection_context["attached_integrations"],
        available_integrations=connection_context["available_integrations"],
        provider_catalog=connection_context["provider_catalog"],
    )
    connection_plan_items = connection_plan.get("items") if isinstance(connection_plan.get("items"), list) else []
    connection_plan_by_key = {
        str(item.get("key") or ""): item
        for item in connection_plan_items
        if isinstance(item, dict)
    }
    if not preflight.get("ready"):
        for item in preflight.get("missing") or []:
            if not isinstance(item, dict):
                continue
            blockers.append(_activation_connection_blocker(item, connection_plan_by_key.get(str(item.get("key") or ""))))
    if active_version and not preview_run_status.get("ready"):
        blockers.append({"type": "preview_run", "message": "Запустите безопасный preview run перед активацией."})
    ready = (
        bool(active_version)
        and bool(compiled_validation.get("ready"))
        and bool(approval_policy_status.get("ready"))
        and bool(preflight.get("ready"))
        and bool(preview_run_status.get("ready"))
    )
    next_step = "activate_version" if ready else _activation_gate_next_step(blockers)
    human_blockers = _activation_gate_human_blockers(blockers, preflight, compiled_validation)
    return {
        "schema": "localos_agent_activation_gate_v1",
        "status": "ready" if ready else "blocked",
        "can_activate": ready,
        "active_version_id": str((active_version or {}).get("id") or ""),
        "requires_compiled_validation": True,
        "requires_preflight_ready": True,
        "requires_preview_run": True,
        "requires_approval_policy": True,
        "compiled_validation": compiled_validation,
        "approval_policy_status": approval_policy_status,
        "preflight": preflight,
        "preview_run_status": preview_run_status,
        "blockers": blockers,
        "human_blockers": human_blockers,
        "summary": _activation_gate_summary_text(ready, next_step, human_blockers),
        "primary_action_label": _activation_gate_primary_action_label(next_step),
        "connection_plan": connection_plan,
        "next_binding_key": _connection_plan_next_binding_key(connection_plan),
        "next_step": next_step,
    }


def _activation_connection_blocker(preflight_item: dict, plan_item: dict | None = None) -> dict:
    plan_item = plan_item if isinstance(plan_item, dict) else {}
    provider = str(preflight_item.get("provider") or plan_item.get("provider") or "").strip()
    binding_key = str(preflight_item.get("key") or plan_item.get("key") or provider or "").strip()
    missing_config = preflight_item.get("missing_config") if isinstance(preflight_item.get("missing_config"), list) else []
    provider_routes = plan_item.get("provider_routes") if isinstance(plan_item.get("provider_routes"), list) else []
    preferred_route = _preferred_connection_plan_route(plan_item)
    message = str(plan_item.get("explanation") or preflight_item.get("summary") or "").strip()
    if not message:
        if missing_config:
            message = f"Заполните настройки {_agent_integration_provider_label(provider)}: {', '.join([str(value) for value in missing_config])}."
        else:
            message = f"Подключите {_agent_integration_provider_label(provider)} или выберите provider route."
    action = str(plan_item.get("action") or "connect_required")
    return {
        "type": "route" if action == "choose_route" else "connection",
        "provider": provider,
        "binding_key": binding_key,
        "message": message,
        "missing_config": missing_config,
        "binding_status": str(preflight_item.get("status") or plan_item.get("binding_status") or ""),
        "resolution": str(preflight_item.get("resolution") or ""),
        "action": action,
        "route_state": str(plan_item.get("route_state") or ""),
        "route_summary": str(plan_item.get("route_summary") or ""),
        "primary_label": str(plan_item.get("primary_label") or _connection_plan_label(str(plan_item.get("action") or "connect_required"))),
        "preferred_route": preferred_route,
        "provider_routes": provider_routes[:6],
    }


def _activation_preview_run_status(cursor, blueprint_id: str, version_id: str) -> dict:
    accepted_statuses = ["completed", "waiting_approval"]
    if not blueprint_id or not version_id:
        return {
            "schema": "localos_agent_preview_run_status_v1",
            "required": True,
            "ready": False,
            "status": "missing_version",
            "accepted_statuses": accepted_statuses,
            "message": "Создайте версию агента, затем запустите preview.",
        }
    cursor.execute(
        """
        SELECT id, status, input_json, output_json, error_text, started_at, completed_at, updated_at
        FROM agent_runs
        WHERE blueprint_id = %s
          AND blueprint_version_id = %s
        ORDER BY started_at DESC
        LIMIT 20
        """,
        (blueprint_id, version_id),
    )
    preview_runs = []
    for row in cursor.fetchall() or []:
        normalized = _normalize_json_row(dict(row))
        run_input = normalized.get("input_json") if isinstance(normalized.get("input_json"), dict) else {}
        if run_input.get("preview_mode") is not True:
            continue
        if run_input.get("external_side_effects_allowed") is not False:
            continue
        preview_runs.append(
            {
                "id": str(normalized.get("id") or ""),
                "status": str(normalized.get("status") or ""),
                "started_at": normalized.get("started_at"),
                "completed_at": normalized.get("completed_at"),
                "error_text": str(normalized.get("error_text") or ""),
                "source": str(run_input.get("source") or ""),
            }
        )
    latest_run = preview_runs[0] if preview_runs else None
    passed_run = next((item for item in preview_runs if item.get("status") in accepted_statuses), None)
    if passed_run:
        return {
            "schema": "localos_agent_preview_run_status_v1",
            "required": True,
            "ready": True,
            "status": "passed",
            "accepted_statuses": accepted_statuses,
            "latest_run": latest_run,
            "passed_run": passed_run,
            "checked_count": len(preview_runs),
            "message": "Безопасный preview run пройден.",
        }
    return {
        "schema": "localos_agent_preview_run_status_v1",
        "required": True,
        "ready": False,
        "status": "missing_passed_preview",
        "accepted_statuses": accepted_statuses,
        "latest_run": latest_run,
        "checked_count": len(preview_runs),
        "message": "Запустите preview run без внешних действий перед активацией.",
    }


def _build_activation_approval_policy_status(version_payload: dict, compiled_validation: dict) -> dict:
    candidate = compiled_validation.get("candidate") if isinstance(compiled_validation.get("candidate"), dict) else {}
    dsl = candidate.get("dsl") if isinstance(candidate.get("dsl"), dict) else {}
    steps = version_payload.get("steps") if isinstance(version_payload.get("steps"), list) else dsl.get("steps") if isinstance(dsl.get("steps"), list) else []
    approval_policy = (
        version_payload.get("approval_policy")
        if isinstance(version_payload.get("approval_policy"), dict)
        else dsl.get("approval_policy")
        if isinstance(dsl.get("approval_policy"), dict)
        else {}
    )
    limits = (
        version_payload.get("limits")
        if isinstance(version_payload.get("limits"), dict)
        else dsl.get("limits")
        if isinstance(dsl.get("limits"), dict)
        else {}
    )
    write_steps = []
    missing_approval = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        if str(step.get("type") or "") != "capability":
            continue
        capability = str(step.get("capability") or "").strip()
        if not _activation_capability_requires_policy(capability):
            continue
        step_key = str(step.get("key") or capability or "capability").strip()
        approval_type = str(step.get("required_approval_type") or "").strip()
        write_steps.append(
            {
                "key": step_key,
                "capability": capability,
                "requires_approval": step.get("requires_approval") is True,
                "required_approval_type": approval_type,
            }
        )
        if step.get("requires_approval") is not True or not approval_type:
            missing_approval.append(step_key)
            continue
        if approval_type not in approval_policy and not _activation_has_approval_step(steps, approval_type):
            missing_approval.append(step_key)
    autonomous_writes_allowed = bool(limits.get("autonomous_external_write_allowed") is True or limits.get("autonomous_localos_write_allowed") is True)
    ready = not missing_approval and not autonomous_writes_allowed
    if ready:
        summary = "Approval policy и limits готовы: внешние действия остаются за human gate."
    elif autonomous_writes_allowed:
        summary = "Limits не должны разрешать автономную внешнюю или LocalOS-запись."
    else:
        summary = "Для write-capability нужен declared approval gate."
    return {
        "schema": "localos_agent_approval_policy_status_v1",
        "ready": ready,
        "status": "ready" if ready else "blocked",
        "summary": summary,
        "write_steps": write_steps,
        "missing_approval_steps": missing_approval,
        "limits": limits,
        "autonomous_writes_allowed": autonomous_writes_allowed,
    }


def _activation_capability_requires_policy(capability: str) -> bool:
    markers = [".create", ".send", ".publish", ".settle", ".reserve", "append_row", "send_"]
    return any(marker in capability for marker in markers)


def _activation_has_approval_step(steps: list, approval_type: str) -> bool:
    for step in steps:
        if not isinstance(step, dict):
            continue
        if str(step.get("type") or "") == "approval" and str(step.get("approval_type") or "").strip() == approval_type:
            return True
    return False


def _activation_gate_next_step(blockers: list[dict]) -> str:
    blocker_types = {str(item.get("type") or "") for item in blockers if isinstance(item, dict)}
    if "version" in blocker_types:
        return "create_version"
    if "compiled_validation" in blocker_types or "approval_policy" in blocker_types:
        return "fix_compiled_workflow"
    if "route" in blocker_types:
        return "choose_provider_route"
    if "connection" in blocker_types:
        return "connect_required_integrations"
    if "preview_run" in blocker_types:
        return "run_preview"
    return "review_blockers"


def _activation_gate_human_blockers(blockers: list[dict], preflight: dict, compiled_validation: dict) -> list[dict]:
    result = []
    for item in blockers:
        if not isinstance(item, dict):
            continue
        blocker_type = str(item.get("type") or "").strip()
        if blocker_type in {"connection", "route"}:
            provider = str(item.get("provider") or "").strip()
            message = str(item.get("message") or "").strip()
            route_blocker = blocker_type == "route"
            result.append(
                {
                    "type": blocker_type,
                    "provider": provider,
                    "binding_key": str(item.get("binding_key") or ""),
                    "title": _agent_integration_provider_label(provider),
                    "message": message or (
                        f"Выберите маршрут выполнения для {_agent_integration_provider_label(provider)}, затем запустите preflight ещё раз."
                        if route_blocker
                        else f"Подключите {_agent_integration_provider_label(provider)}, затем запустите preflight ещё раз."
                    ),
                    "action": "choose_provider_route" if route_blocker else "open_connections",
                    "missing_config": item.get("missing_config") if isinstance(item.get("missing_config"), list) else [],
                    "route_state": str(item.get("route_state") or ""),
                    "route_summary": str(item.get("route_summary") or ""),
                    "preferred_route": item.get("preferred_route") if isinstance(item.get("preferred_route"), dict) else {},
                    "provider_routes": item.get("provider_routes") if isinstance(item.get("provider_routes"), list) else [],
                }
            )
        elif blocker_type == "compiled_validation":
            errors = []
            validation = compiled_validation.get("validation") if isinstance(compiled_validation.get("validation"), dict) else {}
            for error in validation.get("errors") if isinstance(validation.get("errors"), list) else []:
                if isinstance(error, dict):
                    errors.append(str(error.get("message") or error.get("field") or "").strip())
            result.append(
                {
                    "type": "compiled_validation",
                    "title": "Логика агента не прошла проверку",
                    "message": errors[0] if errors and errors[0] else "Откройте логику агента и исправьте compiled workflow.",
                    "action": "open_logic",
                }
            )
        elif blocker_type == "approval_policy":
            result.append(
                {
                    "type": "approval_policy",
                    "title": "Проверьте approval policy и limits",
                    "message": str(item.get("message") or "Для внешних действий нужен human gate и безопасные limits."),
                    "action": "open_logic",
                }
            )
        elif blocker_type == "version":
            result.append(
                {
                    "type": "version",
                    "title": "Нет активной версии",
                    "message": "Создайте или выберите версию агента.",
                    "action": "open_logic",
                }
            )
        elif blocker_type == "preview_run":
            result.append(
                {
                    "type": "preview_run",
                    "title": "Нужен preview run",
                    "message": "Сначала проверьте агента на примере: preview покажет шаги, черновики и approval gate без внешних действий.",
                    "action": "run_preview",
                }
            )
    if not result and preflight and not preflight.get("ready"):
        result.append(
            {
                "type": "preflight",
                "title": "Preflight не пройден",
                "message": "Проверьте подключения, лимиты и обязательные поля агента.",
                "action": "open_connections",
            }
        )
    return result


def _activation_gate_summary_text(ready: bool, next_step: str, human_blockers: list[dict]) -> str:
    if ready:
        return "Версию можно активировать: compiled workflow и preflight готовы. Внешние действия останутся за approval gate."
    if human_blockers:
        return str(human_blockers[0].get("message") or "")
    if next_step == "connect_required_integrations":
        return "Подключите обязательные сервисы перед активацией."
    if next_step == "choose_provider_route":
        return "Выберите маршруты выполнения перед активацией."
    if next_step == "fix_compiled_workflow":
        return "Исправьте логику агента перед активацией."
    if next_step == "create_version":
        return "Создайте первую версию агента."
    if next_step == "run_preview":
        return "Запустите безопасный preview run перед активацией."
    return "Проверьте требования активации агента."


def _activation_gate_primary_action_label(next_step: str) -> str:
    labels = {
        "activate_version": "Активировать версию",
        "connect_required_integrations": "Открыть подключения",
        "choose_provider_route": "Выбрать маршрут",
        "fix_compiled_workflow": "Открыть логику",
        "create_version": "Создать версию",
        "run_preview": "Запустить preview",
        "review_blockers": "Проверить требования",
    }
    return labels.get(next_step, "Проверить требования")


def _activation_connection_plan_from_preflight(
    preflight: dict,
    attached_integrations: list[dict] | None = None,
    available_integrations: list[dict] | None = None,
    provider_catalog: list[dict] | None = None,
) -> dict:
    items = preflight.get("items") if isinstance(preflight.get("items"), list) else []
    attached_by_provider = _integrations_by_provider(attached_integrations or [])
    available_by_provider = _integrations_by_provider(available_integrations or [])
    catalog_by_provider = {
        str(item.get("provider") or "").strip(): item
        for item in (provider_catalog or _agent_integration_provider_catalog())
        if isinstance(item, dict) and str(item.get("provider") or "").strip()
    }
    plan_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        catalog_item = catalog_by_provider.get(provider, {})
        status = str(item.get("status") or "").strip()
        resolution = str(item.get("resolution") or "").strip()
        action = "ready" if status == "ready" else "connect_required"
        if resolution in {"provider_route_required", "agent_integration_needs_provider_route", "builder_answer_needs_provider_route"}:
            action = "choose_route"
        if action == "ready" and resolution == "native_localos":
            action = "native_ready"
        attached = attached_by_provider.get(provider, [])
        available = available_by_provider.get(provider, [])
        if action == "connect_required" and available:
            action = "choose_existing"
        elif action == "connect_required" and attached:
            action = "complete_config"
        provider_routes = connector_provider_routes(provider, str(item.get("capability") or ""))
        route_state = "connected" if action in {"ready", "native_ready"} else best_provider_route_state(provider_routes)
        recommended_route = _preferred_provider_route(provider_routes)
        plan_items.append(
            {
                "key": str(item.get("key") or provider or ""),
                "provider": provider,
                "title": str(catalog_item.get("title") or _agent_integration_provider_label(provider)),
                "capability": str(item.get("capability") or ""),
                "trigger": str(item.get("trigger") or ""),
                "direction": str(item.get("direction") or ""),
                "binding_status": status,
                "action": action,
                "primary_label": _connection_plan_label(action),
                "explanation": _activation_connection_explanation(provider, action, item),
                "route_state": route_state,
                "route_summary": _connection_plan_route_summary(item, action, route_state),
                "why_blocked": _connection_plan_why_blocked(item, action, route_state),
                "setup_cta": _connection_plan_setup_cta(item, action, route_state, recommended_route),
                "execution_boundary": str(item.get("execution_boundary") or ""),
                "autonomy_level": str(item.get("autonomy_level") or ""),
                "credential_state": str(item.get("credential_state") or ""),
                "approval_state": str(item.get("approval_state") or ""),
                "policy_summary": str(item.get("policy_summary") or ""),
                "next_action_label": str(item.get("next_action_label") or ""),
                "provider_routes": provider_routes,
                "recommended_route": recommended_route,
                "recommended_route_reason": _connection_plan_recommended_route_reason(action, recommended_route),
                "missing_config": item.get("missing_config") if isinstance(item.get("missing_config"), list) else [],
                "approval_required": bool(item.get("required", True)),
                "existing_integrations": [_connection_plan_integration(value) for value in available[:5]],
                "attached_integrations": [_connection_plan_integration(value) for value in attached[:5]],
                "provider_paths": _connection_plan_provider_paths(catalog_item),
            }
        )
    missing_count = len([item for item in plan_items if item.get("action") not in {"ready", "native_ready"}])
    return {
        "schema": "localos_agent_connection_plan_v1",
        "status": "ready" if missing_count == 0 else "needs_action",
        "missing_count": missing_count,
        "items": plan_items,
    }


def _activation_connection_explanation(provider: str, action: str, item: dict) -> str:
    if action in {"ready", "native_ready"}:
        return "Подключение готово для активации."
    if action == "choose_route":
        return "Выберите route выполнения: существующий доступ, OpenClaw boundary, Maton key или ручной fallback."
    missing_config = item.get("missing_config") if isinstance(item.get("missing_config"), list) else []
    if missing_config:
        return f"{_agent_integration_provider_label(provider)}: заполните {', '.join([str(value) for value in missing_config])}."
    return f"Подключите {_agent_integration_provider_label(provider)}, чтобы активировать агента."


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>", methods=["DELETE"])
def archive_agent_blueprint(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        metadata = _blueprint_metadata(blueprint)
        archived_event = {
            "action": "archived",
            "reason": "Archived from agent cockpit",
            "user_id": _user_id(user_data),
            "created_at": _utc_now_text(),
        }
        events = metadata.get("version_events") if isinstance(metadata.get("version_events"), list) else []
        metadata["version_events"] = (events + [archived_event])[-50:]
        cursor.execute(
            """
            UPDATE agent_blueprints
            SET status = 'archived',
                metadata_json = %s::jsonb,
                updated_at = NOW()
            WHERE id = %s
            """,
            (json.dumps(metadata, ensure_ascii=False), str(blueprint.get("id") or blueprint_id)),
        )
        db.conn.commit()
        return jsonify({"success": True, "blueprint_id": str(blueprint.get("id") or blueprint_id), "status": "archived"})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/versions", methods=["POST"])
def create_agent_blueprint_version(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    rebuild_from_description = bool(payload.get("rebuild_from_description"))
    if not rebuild_from_description and not str(payload.get("goal") or "").strip():
        return _json_error("goal is required", 400, "VALIDATION_ERROR")
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        version_payload = payload
        if rebuild_from_description:
            description = str(
                payload.get("description")
                or blueprint.get("description")
                or blueprint.get("latest_goal")
                or blueprint.get("name")
                or ""
            ).strip()
            if not description:
                return _json_error("description is required for rebuild", 400, "VALIDATION_ERROR")
            draft = build_agent_blueprint_draft(
                description,
                str(payload.get("category") or blueprint.get("category") or "custom"),
                use_ai=bool(payload.get("use_ai_compiler")),
                business_id=str(blueprint.get("business_id") or ""),
                user_id=_user_id(user_data),
            )
            version_payload = draft.get("version_payload") if isinstance(draft.get("version_payload"), dict) else {}
            metadata = {
                **_blueprint_metadata(blueprint),
                **(draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}),
            }
            metadata["builder"] = str(metadata.get("builder") or "rebuild_from_description_v1")
            metadata["rebuild_reason"] = str(payload.get("reason") or "manual_rebuild_from_dashboard")
            _save_blueprint_metadata(cursor, str(blueprint.get("id")), metadata)
        version = _insert_version(cursor, str(blueprint.get("id")), version_payload, user_data)
        db.conn.commit()
        refreshed_blueprint = _load_blueprint(cursor, str(blueprint.get("id") or ""))
        active_version_id = str(_blueprint_metadata(refreshed_blueprint or blueprint).get("active_version_id") or "").strip()
        active_version = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), active_version_id) if active_version_id else None
        return jsonify(
            {
                "success": True,
                "version": version,
                "candidate_version": version,
                "active_version": _normalize_json_row(active_version) if active_version else None,
                "version_event": None,
                "activation_state": "candidate_requires_preview",
                "rebuild_applied": rebuild_from_description,
            }
        ), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/versions/<version_id>/diff", methods=["GET"])
def get_agent_blueprint_version_diff(blueprint_id: str, version_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        version = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), version_id)
        if not version:
            return _json_error("Blueprint version not found", 404, "VERSION_NOT_FOUND")
        compare_to_id = str(request.args.get("compare_to_version_id") or "").strip()
        compare_to = None
        if compare_to_id:
            compare_to = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), compare_to_id)
            if not compare_to:
                return _json_error("Compare version not found", 404, "COMPARE_VERSION_NOT_FOUND")
        else:
            cursor.execute(
                """
                SELECT *
                FROM agent_blueprint_versions
                WHERE blueprint_id = %s
                  AND version_number < %s
                ORDER BY version_number DESC
                LIMIT 1
                """,
                (blueprint.get("id"), _version_number(version)),
            )
            row = cursor.fetchone()
            compare_to = dict(row) if row else None
        diff = build_agent_version_diff(compare_to, version)
        return jsonify({"success": True, "version": _normalize_json_row(version), "compare_to": _normalize_json_row(compare_to) if compare_to else None, "diff": diff})
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/versions/<version_id>/activate", methods=["POST"])
def activate_agent_blueprint_version(blueprint_id: str, version_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        version = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), version_id)
        if not version:
            return _json_error("Blueprint version not found", 404, "VERSION_NOT_FOUND")
        activation_gate = _build_activation_gate_summary(
            cursor,
            blueprint=blueprint,
            active_version=version,
            metadata=_blueprint_metadata(blueprint),
        )
        if not activation_gate.get("can_activate"):
            return jsonify(
                {
                    "success": False,
                    "error": str(activation_gate.get("summary") or "Перед активацией нужно пройти проверки агента."),
                    "code": "AGENT_ACTIVATION_GATE_BLOCKED",
                    "activation_gate": activation_gate,
                }
            ), 400
        active_before = _resolve_active_version(cursor, blueprint)
        event = _remember_active_version(cursor, blueprint, version, user_data, "activated", str(payload.get("reason") or ""))
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "active_version": _normalize_json_row(version),
                "previous_active_version": _normalize_json_row(active_before) if active_before else None,
                "diff": build_agent_version_diff(active_before, version),
                "version_event": event,
            }
        )
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/versions/<version_id>/rollback", methods=["POST"])
def rollback_agent_blueprint_version(blueprint_id: str, version_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        version = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), version_id)
        if not version:
            return _json_error("Blueprint version not found", 404, "VERSION_NOT_FOUND")
        active_before = _resolve_active_version(cursor, blueprint)
        if active_before and str(active_before.get("id") or "") == str(version.get("id") or ""):
            return _json_error("Version is already active", 400, "VERSION_ALREADY_ACTIVE")
        reason = str(payload.get("reason") or "rollback").strip()
        rollback_gate = {}
        if not _version_was_active_before(blueprint, version):
            rollback_gate = _build_activation_gate_summary(
                cursor,
                blueprint=blueprint,
                active_version=version,
                metadata=_blueprint_metadata(blueprint),
            )
            if not rollback_gate.get("can_activate"):
                return jsonify(
                    {
                        "success": False,
                        "error": str(rollback_gate.get("summary") or "Эта версия не была активной раньше. Сначала нужен safe preview."),
                        "code": "AGENT_ROLLBACK_GATE_BLOCKED",
                        "rollback_gate": rollback_gate,
                    }
                ), 400
        event = _remember_active_version(cursor, blueprint, version, user_data, "rollback", reason)
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "active_version": _normalize_json_row(version),
                "previous_active_version": _normalize_json_row(active_before) if active_before else None,
                "diff": build_agent_version_diff(active_before, version),
                "version_event": event,
                "rollback_gate": rollback_gate,
            }
        )
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/setup", methods=["POST"])
def setup_agent_blueprint(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        metadata = _blueprint_metadata(blueprint)
        setup = normalize_agent_setup(payload)
        metadata["agent_setup"] = setup
        metadata["setup_completed"] = True
        _save_blueprint_metadata(cursor, blueprint_id, metadata)
        version = None
        latest_version = _load_latest_blueprint_version(cursor, blueprint_id)
        if latest_version:
            version_payload = build_version_payload_from_row(latest_version)
            input_schema = version_payload.get("inputs_schema") if isinstance(version_payload.get("inputs_schema"), dict) else {}
            input_schema["agent_setup"] = setup
            version_payload["inputs_schema"] = input_schema
            output_schema = version_payload.get("output_schema") if isinstance(version_payload.get("output_schema"), dict) else {}
            output_schema["human_review"] = True
            version_payload["output_schema"] = output_schema
            version = _insert_version(cursor, blueprint_id, version_payload, user_data)
        db.conn.commit()
        refreshed = _load_blueprint(cursor, blueprint_id)
        activation_gate = (
            _build_activation_gate_summary(
                cursor,
                blueprint=refreshed or blueprint,
                active_version=version,
                metadata=_blueprint_metadata(refreshed or blueprint),
            )
            if version
            else {}
        )
        return jsonify(
            {
                "success": True,
                "blueprint": _normalize_json_row(refreshed),
                "setup": setup,
                "version": version,
                "candidate_version": version,
                "version_event": None,
                "activation_gate": activation_gate,
            }
        )
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/integrations", methods=["GET"])
def list_agent_blueprint_integrations(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        business_id = str(blueprint.get("business_id") or "")
        metadata = _blueprint_metadata(blueprint)
        attached_ids = _agent_integration_ids(metadata)
        attached_rows = _load_agent_integrations(cursor, business_id, attached_ids) if attached_ids else []
        all_rows = _load_agent_integrations(cursor, business_id)
        attached_lookup = {str(row.get("id") or "") for row in attached_rows}
        integrations = [_normalize_agent_integration(row, attached=True) for row in attached_rows]
        binding_status = _agent_integration_binding_status(metadata, attached_rows)
        available = [
            _normalize_agent_integration(row, attached=False)
            for row in all_rows
            if str(row.get("id") or "") not in attached_lookup
        ]
        provider_catalog = _agent_integration_provider_catalog()
        connection_plan = _agent_connection_plan(binding_status, integrations, available, provider_catalog)
        return jsonify(
            {
                "success": True,
                "integrations": integrations,
                "available_integrations": available,
                "provider_catalog": provider_catalog,
                "external_auth_options": _load_agent_external_auth_options(cursor, business_id),
                "capability_integrations": metadata.get("capability_integrations") if isinstance(metadata.get("capability_integrations"), dict) else {},
                "custom_process": metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {},
                "required_integration_bindings": metadata.get("required_integration_bindings") if isinstance(metadata.get("required_integration_bindings"), list) else [],
                "binding_status": binding_status,
                "connection_plan": connection_plan,
            }
        )
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/integrations", methods=["POST"])
def save_agent_blueprint_integration(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    provider = str(payload.get("provider") or "").strip().lower()
    if provider not in {"google_sheets", "browser_use", "telegram", "whatsapp", "maton", "localos_finance", "composio"}:
        return _json_error("Unsupported integration provider", 400, "UNSUPPORTED_PROVIDER")
    status = str(payload.get("status") or "active").strip().lower()
    if status not in {"draft", "active", "paused"}:
        return _json_error("Unsupported integration status", 400, "UNSUPPORTED_STATUS")
    config = _sanitize_agent_integration_config(provider, payload)
    if provider == "google_sheets" and not str(config.get("spreadsheet_id") or "").strip():
        return _json_error("spreadsheet_id is required for Google Sheets integration", 400, "SPREADSHEET_REQUIRED")
    if provider == "browser_use" and not config.get("target_urls"):
        return _json_error("target_urls is required for Browser use integration", 400, "TARGET_URLS_REQUIRED")
    limits = _sanitize_agent_integration_limits(provider, payload)
    integration_id = str(payload.get("integration_id") or payload.get("id") or "").strip()
    if not integration_id:
        integration_id = str(uuid.uuid4())
    display_name = str(payload.get("display_name") or _agent_integration_provider_label(provider)).strip()
    requested_auth_ref = str(payload.get("auth_ref") or "").strip()

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        business_id = str(blueprint.get("business_id") or "")
        auth_ref = _resolve_agent_integration_auth_ref(cursor, business_id, provider, requested_auth_ref)
        cursor.execute(
            """
            SELECT id
            FROM agent_integrations
            WHERE id = %s
              AND business_id = %s
            """,
            (integration_id, business_id),
        )
        existing = cursor.fetchone()
        if existing:
            cursor.execute(
                """
                UPDATE agent_integrations
                SET provider = %s,
                    status = %s,
                    display_name = %s,
                    auth_ref = %s,
                    config_json = %s::jsonb,
                    limits_json = %s::jsonb,
                    connected_by_user_id = %s,
                    updated_at = NOW()
                WHERE id = %s
                  AND business_id = %s
                """,
                (
                    provider,
                    status,
                    display_name,
                    auth_ref,
                    json.dumps(config, ensure_ascii=False),
                    json.dumps(limits, ensure_ascii=False),
                    _user_id(user_data),
                    integration_id,
                    business_id,
                ),
            )
        else:
            cursor.execute(
                """
                INSERT INTO agent_integrations (
                    id, business_id, provider, status, display_name, auth_ref,
                    config_json, limits_json, connected_by_user_id
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s)
                """,
                (
                    integration_id,
                    business_id,
                    provider,
                    status,
                    display_name,
                    auth_ref,
                    json.dumps(config, ensure_ascii=False),
                    json.dumps(limits, ensure_ascii=False),
                    _user_id(user_data),
                ),
            )
        cursor.execute(
            """
            SELECT id, business_id, provider, status, display_name, auth_ref,
                   config_json, limits_json, connected_by_user_id, created_at, updated_at
            FROM agent_integrations
            WHERE id = %s
              AND business_id = %s
            """,
            (integration_id, business_id),
        )
        integration = dict(cursor.fetchone())
        metadata = _sync_blueprint_integration_metadata(cursor, blueprint, integration, str(payload.get("binding_key") or ""))
        attached_ids = _agent_integration_ids(metadata)
        attached_rows = _load_agent_integrations(cursor, business_id, attached_ids) if attached_ids else []
        all_rows = _load_agent_integrations(cursor, business_id)
        attached_lookup = {str(row.get("id") or "") for row in attached_rows}
        attached_integrations = [_normalize_agent_integration(row, attached=True) for row in attached_rows]
        available_integrations = [
            _normalize_agent_integration(row, attached=False)
            for row in all_rows
            if str(row.get("id") or "") not in attached_lookup
        ]
        binding_status = _agent_integration_binding_status(metadata, attached_rows)
        connection_plan = _agent_connection_plan(
            binding_status,
            attached_integrations,
            available_integrations,
            _agent_integration_provider_catalog(),
        )
        post_connect_handoff = _build_agent_post_connect_handoff(connection_plan)
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "integration": _normalize_agent_integration(integration, attached=True),
                "capability_integrations": metadata.get("capability_integrations") if isinstance(metadata.get("capability_integrations"), dict) else {},
                "custom_process": metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {},
                "binding_status": binding_status,
                "connection_plan": connection_plan,
                "post_connect_handoff": post_connect_handoff,
                "next_step": str(post_connect_handoff.get("next_step") or ""),
            }
        ), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/provider-routes", methods=["POST"])
def choose_agent_blueprint_provider_route(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    binding_key = str(payload.get("binding_key") or "").strip()
    route_provider = str(payload.get("route_provider") or payload.get("provider") or "").strip().lower()
    if not binding_key:
        return _json_error("binding_key is required", 400, "BINDING_KEY_REQUIRED")
    if route_provider not in {"openclaw", "maton", "manual"}:
        return _json_error("Unsupported provider route", 400, "UNSUPPORTED_PROVIDER_ROUTE")

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        business_id = str(blueprint.get("business_id") or "")
        metadata = _blueprint_metadata(blueprint)
        binding = _required_binding_by_key(metadata, binding_key)
        if not binding:
            return _json_error("Binding was not found on this agent", 404, "BINDING_NOT_FOUND")
        if not _route_is_allowed_for_binding(binding, route_provider):
            return _json_error("Provider route is not allowed for this binding", 400, "PROVIDER_ROUTE_NOT_ALLOWED")

        external_account = {}
        if route_provider == "maton":
            external_account_id = str(payload.get("external_account_id") or payload.get("auth_ref") or "").strip()
            external_account = _load_external_auth_option(cursor, business_id, "maton", external_account_id)
            if not external_account:
                return _json_error("Active Maton key was not found for this business", 400, "MATON_KEY_REQUIRED")

        metadata = _apply_agent_provider_route_metadata(
            cursor,
            blueprint,
            binding_key=binding_key,
            route_provider=route_provider,
            external_account=external_account,
        )
        attached_ids = _agent_integration_ids(metadata)
        attached_rows = _load_agent_integrations(cursor, business_id, attached_ids) if attached_ids else []
        all_rows = _load_agent_integrations(cursor, business_id)
        attached_lookup = {str(row.get("id") or "") for row in attached_rows}
        attached_integrations = [_normalize_agent_integration(row, attached=True) for row in attached_rows]
        available_integrations = [
            _normalize_agent_integration(row, attached=False)
            for row in all_rows
            if str(row.get("id") or "") not in attached_lookup
        ]
        binding_status = _agent_integration_binding_status(metadata, attached_rows)
        connection_plan = _agent_connection_plan(
            binding_status,
            attached_integrations,
            available_integrations,
            _agent_integration_provider_catalog(),
        )
        preflight = build_agent_integration_preflight(
            cursor,
            business_id=business_id,
            metadata=metadata,
            input_payload={},
        )
        post_connect_handoff = _build_agent_post_connect_handoff(connection_plan)
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "binding_key": binding_key,
                "route_provider": route_provider,
                "provider_route": metadata.get("agent_binding_provider_routes", {}).get(binding_key, {}),
                "binding_status": binding_status,
                "connection_plan": connection_plan,
                "preflight": preflight,
                "post_connect_handoff": post_connect_handoff,
                "next_step": str(post_connect_handoff.get("next_step") or ""),
            }
        )
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/custom-process", methods=["POST"])
def save_agent_blueprint_custom_process(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        metadata = _blueprint_metadata(blueprint)
        current_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
        custom_process = _normalize_custom_process_payload(payload, current_process)
        metadata["custom_process"] = custom_process
        compiled_process = metadata.get("compiled_process") if isinstance(metadata.get("compiled_process"), dict) else {}
        compiled_process["schema"] = str(compiled_process.get("schema") or "compiled_integration_workflow_v1")
        compiled_process["last_edited_by_user_id"] = _user_id(user_data)
        compiled_process["last_edited_at"] = _utc_now_text()
        metadata["compiled_process"] = compiled_process
        _save_blueprint_metadata(cursor, blueprint_id, metadata)
        latest_version = _load_latest_blueprint_version(cursor, blueprint_id)
        version = None
        if latest_version:
            version_payload = build_version_payload_from_row(latest_version)
            version_payload = _apply_custom_process_to_version_payload(version_payload, custom_process)
            version = _insert_version(cursor, blueprint_id, version_payload, user_data)
        db.conn.commit()
        refreshed = _load_blueprint(cursor, blueprint_id)
        activation_gate = (
            _build_activation_gate_summary(
                cursor,
                blueprint=refreshed or blueprint,
                active_version=version,
                metadata=_blueprint_metadata(refreshed or blueprint),
            )
            if version
            else {}
        )
        return jsonify(
            {
                "success": True,
                "custom_process": custom_process,
                "version": version,
                "candidate_version": version,
                "version_event": None,
                "activation_gate": activation_gate,
                "activation_state": "candidate_requires_preview" if version else "",
            }
        )
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/custom-process/preview", methods=["POST"])
def preview_agent_blueprint_custom_process(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        active_version = _resolve_active_version(cursor, blueprint)
        version_id = str((active_version or {}).get("id") or "").strip()
        if not version_id:
            return _json_error("Blueprint has no version", 400, "NO_VERSION")
        preview_input = _build_custom_process_preview_input(blueprint, payload)
        runner = AgentBlueprintRunner(cursor, build_agent_blueprint_orchestrator())
        result = runner.start_run(version_id, preview_input, user_data)
        db.conn.commit()
        if not result.get("success"):
            return _json_error(str(result.get("error") or "preview run failed"), 400, "PREVIEW_RUN_FAILED")
        return jsonify({**result, "preview_input": preview_input}), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/sources", methods=["POST"])
def add_agent_blueprint_source(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        metadata = _blueprint_metadata(blueprint)
        sources = metadata.get("agent_sources") if isinstance(metadata.get("agent_sources"), list) else []
        source = normalize_agent_source(payload)
        sources.append(source)
        metadata["agent_sources"] = sources[-50:]
        _save_blueprint_metadata(cursor, blueprint_id, metadata)
        db.conn.commit()
        return jsonify({"success": True, "source": source, "sources": metadata["agent_sources"]}), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/sources/catalog", methods=["GET"])
def list_agent_blueprint_source_catalog(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        metadata = _blueprint_metadata(blueprint)
        sources = metadata.get("agent_sources") if isinstance(metadata.get("agent_sources"), list) else []
        catalog = build_agent_datahub_catalog(cursor, str(blueprint.get("business_id") or ""), sources)
        return jsonify({"success": True, "catalog": catalog})
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/sources/upload", methods=["POST"])
def upload_agent_blueprint_source(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    uploaded_file = request.files.get("file")
    preferred_name = str(request.form.get("name") or "").strip()
    source_payload, upload_error = build_agent_source_from_upload(uploaded_file, preferred_name)
    if upload_error:
        return _json_error(str(upload_error.get("message") or "file upload failed"), 400, str(upload_error.get("code") or "UPLOAD_FAILED"))
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        metadata = _blueprint_metadata(blueprint)
        sources = metadata.get("agent_sources") if isinstance(metadata.get("agent_sources"), list) else []
        source = normalize_agent_source(source_payload)
        sources.append(source)
        metadata["agent_sources"] = sources[-50:]
        _save_blueprint_metadata(cursor, blueprint_id, metadata)
        db.conn.commit()
        return jsonify({"success": True, "source": source, "sources": metadata["agent_sources"]}), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/review", methods=["GET"])
def review_agent_blueprint(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        return jsonify({"success": True, "review": build_blueprint_review(cursor, str(blueprint.get("id") or ""))})
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/preflight", methods=["POST"])
def preflight_agent_blueprint_run(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        version_id = str(payload.get("blueprint_version_id") or "").strip()
        version = None
        if version_id:
            version = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), version_id)
            if not version:
                return _json_error("Blueprint version does not belong to this blueprint", 400, "VERSION_BLUEPRINT_MISMATCH")
        else:
            version = _resolve_active_version(cursor, blueprint)
        if not version:
            return _json_error("Blueprint has no version", 400, "NO_VERSION")
        raw_input = payload.get("input") if isinstance(payload.get("input"), dict) else {}
        run_input = _build_agent_preview_run_input(blueprint, version, payload) if raw_input.get("preview_mode") else raw_input
        metadata = _blueprint_metadata(blueprint)
        preflight = build_agent_integration_preflight(
            cursor,
            business_id=str(blueprint.get("business_id") or ""),
            metadata=metadata,
            input_payload=run_input,
        )
        preview_run_gate = {
            "schema": "localos_agent_preview_run_gate_v1",
            "status": "ready" if bool(preflight.get("ready")) else "blocked",
            "can_preview_run": bool(preflight.get("ready")),
            "requires_preflight_ready": True,
            "external_side_effects_allowed": False,
            "approval_required_for_external_actions": True,
            "next_step": "start_preview_run" if bool(preflight.get("ready")) else "connect_required_integrations",
        }
        connection_context = _agent_connection_context(cursor, str(blueprint.get("business_id") or ""), metadata)
        connection_plan = _activation_connection_plan_from_preflight(
            preflight,
            attached_integrations=connection_context["attached_integrations"],
            available_integrations=connection_context["available_integrations"],
            provider_catalog=connection_context["provider_catalog"],
        )
        return jsonify(
            {
                "success": True,
                "blueprint_id": str(blueprint.get("id") or ""),
                "blueprint_version_id": str(version.get("id") or ""),
                "preflight": preflight,
                "connection_plan": connection_plan,
                "next_binding_key": _connection_plan_next_binding_key(connection_plan),
                "preview_run_gate": preview_run_gate,
                "preview_input": run_input if run_input.get("preview_mode") else {},
                "can_start": bool(preflight.get("ready")),
            }
        )
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-blueprints/<blueprint_id>/runs", methods=["POST"])
def start_agent_blueprint_run(blueprint_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        blueprint, access_error = _require_blueprint_access(cursor, blueprint_id, user_data)
        if access_error:
            return access_error
        version_id = str(payload.get("blueprint_version_id") or "").strip()
        if not version_id:
            active_version = _resolve_active_version(cursor, blueprint)
            version_id = str((active_version or {}).get("id") or "")
        elif not _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), version_id):
            return _json_error("Blueprint version does not belong to this blueprint", 400, "VERSION_BLUEPRINT_MISMATCH")
        if not version_id:
            return _json_error("Blueprint has no version", 400, "NO_VERSION")
        version = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), version_id)
        raw_input = payload.get("input") if isinstance(payload.get("input"), dict) else {}
        run_input = _build_agent_preview_run_input(blueprint, version, payload) if raw_input.get("preview_mode") else raw_input
        runner = AgentBlueprintRunner(cursor, build_agent_blueprint_orchestrator())
        result = runner.start_run(version_id, run_input, user_data)
        db.conn.commit()
        if not result.get("success"):
            if result.get("code") == "AGENT_INTEGRATIONS_REQUIRED":
                return jsonify(result), 400
            return _json_error(str(result.get("error") or "run failed"), 400, "RUN_FAILED")
        return jsonify(result), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-runs/<run_id>", methods=["GET"])
def get_agent_run(run_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT blueprint_id FROM agent_runs WHERE id = %s", (run_id,))
        row = cursor.fetchone()
        if not row:
            return _json_error("Run not found", 404, "NOT_FOUND")
        blueprint, access_error = _require_blueprint_access(cursor, str(row.get("blueprint_id") or ""), user_data)
        if access_error:
            return access_error
        runner = AgentBlueprintRunner(cursor, build_agent_blueprint_orchestrator())
        return jsonify({"success": True, "run": runner.load_run(run_id, user_data)})
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-runs/<run_id>/support-export", methods=["GET"])
def get_agent_run_support_export(run_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT blueprint_id FROM agent_runs WHERE id = %s", (run_id,))
        row = cursor.fetchone()
        if not row:
            return _json_error("Run not found", 404, "NOT_FOUND")
        blueprint, access_error = _require_blueprint_access(cursor, str(row.get("blueprint_id") or ""), user_data)
        if access_error:
            return access_error
        runner = AgentBlueprintRunner(cursor, build_agent_blueprint_orchestrator())
        if str(request.args.get("format") or "").strip().lower() == "markdown":
            return Response(runner.render_run_support_export_markdown(run_id, user_data), mimetype="text/markdown")
        result = runner.build_run_support_export(run_id, user_data)
        if not result.get("success"):
            return _json_error(str(result.get("error") or "support export failed"), 400, "SUPPORT_EXPORT_FAILED")
        return jsonify(result)
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-runs/<run_id>/finance-requests/apply", methods=["POST"])
def apply_agent_run_finance_requests(run_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT blueprint_id FROM agent_runs WHERE id = %s", (run_id,))
        row = cursor.fetchone()
        if not row:
            return _json_error("Run not found", 404, "NOT_FOUND")
        blueprint, access_error = _require_blueprint_access(cursor, str(row.get("blueprint_id") or ""), user_data)
        if access_error:
            return access_error
        runner = AgentBlueprintRunner(cursor, build_agent_blueprint_orchestrator())
        result = runner.apply_finance_requests(run_id, user_data)
        if not result.get("success"):
            db.conn.rollback()
            return _json_error(str(result.get("error") or "finance apply failed"), 400, "FINANCE_APPLY_FAILED")
        db.conn.commit()
        return jsonify(result)
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-runs/<run_id>/feedback", methods=["POST"])
def create_agent_run_feedback(run_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    feedback_text = str(payload.get("feedback") or "").strip()
    if not feedback_text:
        return _json_error("feedback is required", 400, "VALIDATION_ERROR")
    trigger_type = str(payload.get("trigger_type") or payload.get("feedback_type") or "manual_feedback").strip().lower()
    if trigger_type not in {"manual_edit", "approval_rejected", "bad_outcome", "runtime_error", "manual_feedback", "run_review"}:
        trigger_type = "manual_feedback"
    auto_activate = bool(payload.get("auto_activate") is True)
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT * FROM agent_runs WHERE id = %s", (run_id,))
        run = cursor.fetchone()
        if not run:
            return _json_error("Run not found", 404, "NOT_FOUND")
        run = dict(run)
        blueprint, access_error = _require_blueprint_access(cursor, str(run.get("blueprint_id") or ""), user_data)
        if access_error:
            return access_error
        version = _load_blueprint_version_for_blueprint(cursor, str(blueprint.get("id") or ""), str(run.get("blueprint_version_id") or ""))
        if not version:
            return _json_error("Blueprint version not found", 404, "VERSION_NOT_FOUND")
        feedback = {
            "run_id": run_id,
            "feedback": feedback_text,
            "trigger_type": trigger_type,
            "manual_edit": payload.get("manual_edit") if isinstance(payload.get("manual_edit"), dict) else {},
            "outcome": payload.get("outcome") if isinstance(payload.get("outcome"), dict) else {},
            "error": payload.get("error") if isinstance(payload.get("error"), dict) else {},
            "created_by_user_id": _user_id(user_data),
            "source": "learning_loop",
            "created_at": _utc_now_text(),
        }
        metadata = _blueprint_metadata(blueprint)
        history = metadata.get("feedback_history") if isinstance(metadata.get("feedback_history"), list) else []
        history.append(feedback)
        metadata["feedback_history"] = history[-20:]
        learning_events = metadata.get("learning_events") if isinstance(metadata.get("learning_events"), list) else []
        _save_blueprint_metadata(cursor, str(blueprint.get("id") or ""), metadata)
        version_payload = build_feedback_version_payload(version, feedback)
        new_version = _insert_version(cursor, str(blueprint.get("id") or ""), version_payload, user_data)
        diff = build_agent_version_diff(version, new_version)
        event = None
        auto_activation_gate = {}
        auto_activation_applied = False
        if auto_activate:
            candidate_blueprint = _load_blueprint(cursor, str(blueprint.get("id") or "")) or blueprint
            auto_activation_gate = _build_activation_gate_summary(
                cursor,
                blueprint=candidate_blueprint,
                active_version=new_version,
                metadata=_blueprint_metadata(candidate_blueprint),
            )
            if auto_activation_gate.get("can_activate"):
                event = _remember_active_version(cursor, candidate_blueprint, new_version, user_data, "feedback_applied", feedback_text)
                auto_activation_applied = True
        refreshed_blueprint = _load_blueprint(cursor, str(blueprint.get("id") or ""))
        refreshed_metadata = _blueprint_metadata(refreshed_blueprint or blueprint)
        learning_summary = build_learning_loop_summary(feedback, version, new_version, diff, auto_activation_applied)
        if auto_activate and not auto_activation_applied:
            learning_summary["activation_state"] = "candidate_requires_preview"
            learning_summary["human_gate_required"] = True
            learning_summary["auto_activation_blocked"] = True
            learning_summary["auto_activation_blocked_reason"] = str(
                auto_activation_gate.get("summary") or "Перед активацией новой версии нужно пройти activation gate."
            )
            learning_summary["activation_gate"] = auto_activation_gate
        learning_events = refreshed_metadata.get("learning_events") if isinstance(refreshed_metadata.get("learning_events"), list) else learning_events
        learning_events.append(
            {
                "run_id": run_id,
                "trigger_type": trigger_type,
                "feedback": feedback_text,
                "previous_version_id": str(version.get("id") or ""),
                "candidate_version_id": str(new_version.get("id") or ""),
                "candidate_version_number": _version_number(new_version),
                "activation_state": learning_summary["activation_state"],
                "auto_activation_requested": auto_activate,
                "auto_activation_applied": auto_activation_applied,
                "created_by_user_id": _user_id(user_data),
                "created_at": feedback["created_at"],
            }
        )
        refreshed_metadata["learning_events"] = learning_events[-50:]
        _save_blueprint_metadata(cursor, str(blueprint.get("id") or ""), refreshed_metadata)
        db.conn.commit()
        return jsonify(
            {
                "success": True,
                "feedback": feedback,
                "version": new_version,
                "candidate_version": new_version,
                "diff": diff,
                "learning": learning_summary,
                "version_event": event,
                "auto_activation_requested": auto_activate,
                "auto_activation_applied": auto_activation_applied,
                "auto_activation_gate": auto_activation_gate if auto_activate else {},
            }
        ), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_blueprints_bp.route("/api/agent-runs/<run_id>/approvals/<approval_id>/approve", methods=["POST"])
def approve_agent_run(run_id: str, approval_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    return _decide_agent_run_approval(run_id, approval_id, user_data, "approve", str(payload.get("reason") or ""))


@agent_blueprints_bp.route("/api/agent-runs/<run_id>/approvals/<approval_id>/reject", methods=["POST"])
def reject_agent_run(run_id: str, approval_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    return _decide_agent_run_approval(run_id, approval_id, user_data, "reject", str(payload.get("reason") or ""))


def _decide_agent_run_approval(run_id: str, approval_id: str, user_data: dict, decision: str, reason: str):
    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        cursor.execute("SELECT blueprint_id FROM agent_runs WHERE id = %s", (run_id,))
        row = cursor.fetchone()
        if not row:
            return _json_error("Run not found", 404, "NOT_FOUND")
        blueprint, access_error = _require_blueprint_access(cursor, str(row.get("blueprint_id") or ""), user_data)
        if access_error:
            return access_error
        runner = AgentBlueprintRunner(cursor, build_agent_blueprint_orchestrator())
        if decision == "approve":
            result = runner.approve(run_id, approval_id, user_data, reason)
        else:
            result = runner.reject(run_id, approval_id, user_data, reason)
        db.conn.commit()
        if not result.get("success"):
            return _json_error(str(result.get("error") or "approval decision failed"), 400, "APPROVAL_DECISION_FAILED")
        return jsonify(result)
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()
