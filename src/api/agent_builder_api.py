import json
import uuid
from datetime import datetime, timezone

from flask import Blueprint, jsonify, request

from core.auth_helpers import require_auth_from_request, verify_business_access
from database_manager import DatabaseManager
from services.agent_blueprint_draft_builder import compile_agent_blueprint
from services.agent_blueprint_runner import normalize_steps, parse_json_field
from services.agent_builder_billing import charge_agent_creation_credits
from services.agent_builder_session import append_user_message, build_agent_builder_state, preview_to_setup
from services.agent_integration_preflight import build_agent_integration_preflight
from services.agent_provider_registry import best_provider_route_state, connector_provider_routes, integration_provider_catalog


agent_builder_bp = Blueprint("agent_builder_api", __name__)


def _json_error(message: str, status: int, code: str):
    return jsonify({"success": False, "error": message, "code": code}), status


def _require_auth():
    user_data = require_auth_from_request()
    if not user_data:
        return None, _json_error("Authorization required", 401, "AUTH_REQUIRED")
    return user_data, None


def _user_id(user_data: dict) -> str:
    return str(user_data.get("user_id") or user_data.get("id") or "")


def _require_business_access(cursor, business_id: str, user_data: dict):
    has_access, owner_id = verify_business_access(cursor, business_id, user_data)
    if not owner_id:
        return False, _json_error("Business not found", 404, "BUSINESS_NOT_FOUND")
    if not has_access:
        return False, _json_error("Forbidden", 403, "FORBIDDEN")
    return True, None


def _use_ai_compiler(payload: dict) -> bool:
    if "use_ai_compiler" not in payload:
        return True
    return bool(payload.get("use_ai_compiler"))


def _compiler_plan_requires_confirmation(preview: dict) -> bool:
    if not isinstance(preview, dict):
        return False
    review = preview.get("compiler_policy_review") if isinstance(preview.get("compiler_policy_review"), dict) else {}
    workflow_draft = preview.get("compiler_workflow_draft") if isinstance(preview.get("compiler_workflow_draft"), dict) else {}
    if not workflow_draft:
        workflow_draft = review.get("workflow_draft") if isinstance(review.get("workflow_draft"), dict) else {}
    approval_points = preview.get("compiler_approval_points") if isinstance(preview.get("compiler_approval_points"), list) else []
    if not approval_points:
        approval_points = review.get("approval_points") if isinstance(review.get("approval_points"), list) else []
    unsupported_requests = preview.get("compiler_unsupported_requests") if isinstance(preview.get("compiler_unsupported_requests"), list) else []
    if not unsupported_requests:
        unsupported_requests = review.get("unsupported_requests") if isinstance(review.get("unsupported_requests"), list) else []
    steps = workflow_draft.get("steps") if isinstance(workflow_draft.get("steps"), list) else []
    return bool(workflow_draft.get("trigger") or steps or approval_points or unsupported_requests)


def _normalize_session(row: dict) -> dict:
    result = dict(row)
    result["messages"] = parse_json_field(result.pop("messages_json", []), [])
    result["preview"] = parse_json_field(result.pop("preview_json", {}), {})
    result["missing_questions"] = parse_json_field(result.pop("missing_questions_json", []), [])
    return result


def _load_session(cursor, session_id: str):
    cursor.execute("SELECT * FROM agent_builder_sessions WHERE id = %s", (session_id,))
    row = cursor.fetchone()
    return dict(row) if row else None


def _load_builder_connection_inventory(cursor, business_id: str) -> list[dict]:
    result = []
    cursor.execute(
        """
        SELECT id, provider, status, display_name, config_json
        FROM agent_integrations
        WHERE business_id = %s
          AND status IN ('active', 'connected', 'ready')
        ORDER BY updated_at DESC, created_at DESC
        LIMIT 50
        """,
        (business_id,),
    )
    for row in cursor.fetchall() or []:
        item = dict(row)
        config = parse_json_field(item.get("config_json"), {})
        result.append(
            {
                "id": str(item.get("id") or ""),
                "provider": str(item.get("provider") or ""),
                "status": str(item.get("status") or "active"),
                "display_name": str(item.get("display_name") or item.get("provider") or ""),
                "config": config if isinstance(config, dict) else {},
                "inventory_source": "agent_integration",
            }
        )
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
    for row in cursor.fetchall() or []:
        item = dict(row)
        source = str(item.get("source") or "").strip()
        provider = source
        config = {}
        if source == "telegram_app":
            provider = "telegram"
            config = {"bot_mode": "business_bot"}
        elif source == "google_business":
            provider = "google_sheets"
            config = {"auth_ref": str(item.get("id") or ""), "source": "google_business"}
        elif source == "google_sheets":
            provider = "google_sheets"
            config = {"auth_ref": str(item.get("id") or ""), "source": "google_sheets"}
        elif source == "maton":
            provider = "maton"
            config = {"channel": "maton_bridge"}
        result.append(
            {
                "id": str(item.get("id") or ""),
                "provider": provider,
                "status": "active",
                "display_name": str(item.get("display_name") or source or provider),
                "config": config,
                "inventory_source": "external_business_account",
            }
        )
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


def _selected_connection_bindings(payload: dict, preview: dict, inventory: list[dict]) -> dict:
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
        key = str(item.get("key") or "").strip()
        provider = str(item.get("provider") or "").strip()
        if not key:
            continue
        provider_by_key[key] = provider
        allowed = set()
        for connection in item.get("connections") if isinstance(item.get("connections"), list) else []:
            if isinstance(connection, dict) and str(connection.get("id") or "").strip():
                allowed.add(str(connection.get("id") or "").strip())
        allowed_by_key[key] = allowed
        if len(allowed) == 1:
            single_connection_by_key[key] = next(iter(allowed))
    inventory_by_id = {
        str(item.get("id") or "").strip(): item
        for item in inventory
        if isinstance(item, dict) and str(item.get("id") or "").strip()
    }
    result = {}
    for key, value in raw.items():
        binding_key = str(key or "").strip()
        integration_id = str(value or "").strip()
        if not binding_key or not integration_id:
            continue
        if binding_key not in allowed_by_key:
            continue
        if integration_id not in inventory_by_id:
            continue
        allowed_ids = allowed_by_key.get(binding_key) or set()
        if allowed_ids and integration_id not in allowed_ids:
            continue
        integration = inventory_by_id[integration_id]
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
        if integration_id not in inventory_by_id:
            continue
        integration = inventory_by_id[integration_id]
        provider = provider_by_key.get(binding_key) or str(integration.get("provider") or "")
        result[binding_key] = {
            "integration_id": integration_id,
            "provider": provider,
            "display_name": str(integration.get("display_name") or provider),
            "config": integration.get("config") if isinstance(integration.get("config"), dict) else {},
            "selection_source": "auto_single_connection",
        }
    return result


def _apply_selected_connection_bindings(metadata: dict, selected_bindings: dict) -> dict:
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
            "source": "agent_builder",
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


def _selected_provider_routes(payload: dict, preview: dict, inventory: list[dict] | None = None) -> dict:
    raw = payload.get("selected_provider_routes")
    if not isinstance(raw, dict):
        raw = payload.get("selected_routes")
    if not isinstance(raw, dict):
        raw = {}
    inventory = inventory if isinstance(inventory, list) else []
    allowed = _allowed_provider_routes_by_binding(preview)
    external_accounts_by_provider = _external_accounts_by_provider(inventory)
    result = {}
    for key, value in raw.items():
        binding_key = str(key or "").strip()
        route_payload = value if isinstance(value, dict) else {"provider": value}
        route_provider = str(route_payload.get("provider") or route_payload.get("route_provider") or "").strip()
        if not binding_key or not route_provider:
            continue
        allowed_routes = allowed.get(binding_key) or {}
        route = allowed_routes.get(route_provider)
        if not route:
            continue
        state = str(route.get("state") or route.get("status") or "").strip()
        action = route.get("provider_action") if isinstance(route.get("provider_action"), dict) else {}
        if state not in {"available", "connected", "manual"} or action.get("available") is False:
            continue
        selected = {
            "binding_key": binding_key,
            "provider": route_provider,
            "route_provider": route_provider,
            "label": str(route.get("label") or route_provider),
            "role": str(route.get("role") or ""),
            "state": state,
            "connect_mode": str(route.get("connect_mode") or ""),
            "primary_cta": str(route.get("primary_cta") or ""),
            "selection_source": str(route_payload.get("selection_source") or "agent_builder_user_choice"),
        }
        external_account_id = str(route_payload.get("external_account_id") or route_payload.get("auth_ref") or "").strip()
        if route_provider == "maton" and not external_account_id:
            maton_accounts = external_accounts_by_provider.get("maton") or []
            if len(maton_accounts) == 1:
                external_account_id = str(maton_accounts[0].get("id") or "").strip()
                selected["display_name"] = str(maton_accounts[0].get("display_name") or "Maton.ai")
        if external_account_id:
            selected["external_account_id"] = external_account_id
            selected["auth_ref"] = external_account_id
        result[binding_key] = selected
    return result


def _external_accounts_by_provider(inventory: list[dict]) -> dict:
    result: dict[str, list[dict]] = {}
    for item in inventory:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        integration_id = str(item.get("id") or "").strip()
        if not provider or not integration_id:
            continue
        if provider == "maton" and str(item.get("inventory_source") or "") != "external_business_account":
            continue
        result.setdefault(provider, []).append(item)
    return result


def _provider_route_selection_errors(selected_provider_routes: dict) -> list[dict]:
    errors = []
    for binding_key, selected in selected_provider_routes.items():
        if not isinstance(selected, dict):
            continue
        route_provider = str(selected.get("route_provider") or selected.get("provider") or "").strip()
        if route_provider == "maton":
            external_account_id = str(selected.get("external_account_id") or selected.get("auth_ref") or "").strip()
            if not external_account_id:
                errors.append(
                    {
                        "key": str(binding_key),
                        "route_provider": "maton",
                        "code": "maton_key_required",
                        "message": "Выберите сохранённый Maton.ai key для этого route.",
                    }
                )
    return errors


def _allowed_provider_routes_by_binding(preview: dict) -> dict:
    result = {}
    candidates = []
    connection_plan = preview.get("connection_plan") if isinstance(preview.get("connection_plan"), dict) else {}
    candidates.extend(connection_plan.get("items") if isinstance(connection_plan.get("items"), list) else [])
    intelligence = preview.get("connector_intelligence") if isinstance(preview.get("connector_intelligence"), dict) else {}
    candidates.extend(intelligence.get("bindings") if isinstance(intelligence.get("bindings"), list) else [])
    readiness = preview.get("connection_readiness") if isinstance(preview.get("connection_readiness"), dict) else {}
    candidates.extend(readiness.get("services") if isinstance(readiness.get("services"), list) else [])
    for item in candidates:
        if not isinstance(item, dict):
            continue
        binding_key = str(item.get("key") or "").strip()
        if not binding_key:
            continue
        routes = item.get("provider_routes") if isinstance(item.get("provider_routes"), list) else []
        recommended = item.get("recommended_route") if isinstance(item.get("recommended_route"), dict) else {}
        if recommended:
            routes = [recommended, *routes]
        for route in routes:
            if not isinstance(route, dict):
                continue
            provider = str(route.get("provider") or "").strip()
            if provider:
                result.setdefault(binding_key, {})[provider] = route
    return result


def _required_provider_route_bindings(preview: dict) -> list[dict]:
    allowed = _allowed_provider_routes_by_binding(preview)
    result = []
    for binding_key, routes in allowed.items():
        usable_routes = []
        for route in routes.values():
            if not isinstance(route, dict):
                continue
            provider = str(route.get("provider") or "").strip()
            state = str(route.get("state") or route.get("status") or "").strip()
            action = route.get("provider_action") if isinstance(route.get("provider_action"), dict) else {}
            if provider and state in {"available", "connected", "manual"} and action.get("available") is not False:
                usable_routes.append(provider)
        if usable_routes:
            result.append(
                {
                    "key": binding_key,
                    "available_routes": sorted(set(usable_routes)),
                }
            )
    return result


def _missing_required_provider_routes(preview: dict, selected_provider_routes: dict) -> list[dict]:
    selected_keys = set(selected_provider_routes.keys()) if isinstance(selected_provider_routes, dict) else set()
    missing = []
    for item in _required_provider_route_bindings(preview):
        binding_key = str(item.get("key") or "").strip()
        if binding_key and binding_key not in selected_keys:
            missing.append(item)
    return missing


def _apply_selected_provider_routes(metadata: dict, selected_provider_routes: dict) -> dict:
    if not selected_provider_routes:
        return metadata
    routes = metadata.get("agent_binding_provider_routes") if isinstance(metadata.get("agent_binding_provider_routes"), dict) else {}
    binding_integrations = metadata.get("agent_binding_integrations") if isinstance(metadata.get("agent_binding_integrations"), dict) else {}
    custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
    action_handlers = metadata.get("connector_action_handlers") if isinstance(metadata.get("connector_action_handlers"), dict) else {}
    provider_by_binding = _provider_by_binding_key(metadata)
    for binding_key, selected in selected_provider_routes.items():
        if not isinstance(selected, dict):
            continue
        route_provider = str(selected.get("route_provider") or selected.get("provider") or "").strip()
        if route_provider not in {"openclaw", "maton", "manual", "native_localos"}:
            continue
        route_payload = {
            "binding_key": str(binding_key),
            "route_provider": route_provider,
            "status": "active",
            "selected_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            "selected_by": "agent_builder",
            "selection_source": str(selected.get("selection_source") or "agent_builder_user_choice"),
            "provider_label": str(selected.get("label") or route_provider),
            "connect_mode": str(selected.get("connect_mode") or ""),
        }
        if route_provider == "openclaw":
            route_payload.update(
                {
                    "integration_id": "openclaw_boundary",
                    "execution_boundary": "localos_policy_envelope",
                    "requires_external_credentials": False,
                }
            )
        elif route_provider == "maton":
            external_account_id = str(selected.get("external_account_id") or selected.get("auth_ref") or "").strip()
            route_payload.update(
                {
                    "integration_id": external_account_id,
                    "external_account_id": external_account_id,
                    "auth_ref": external_account_id,
                    "display_name": str(selected.get("display_name") or "Maton.ai"),
                    "execution_boundary": "localos_policy_envelope",
                    "requires_external_credentials": True,
                }
            )
        elif route_provider == "manual":
            route_payload.update(
                {
                    "integration_id": "manual_fallback",
                    "execution_boundary": "human_operated_fallback",
                    "requires_external_credentials": False,
                    "draft_only_until_human_action": True,
                }
            )
        elif route_provider == "native_localos":
            route_payload.update(
                {
                    "integration_id": "native_localos",
                    "execution_boundary": "localos_native_domain",
                    "requires_external_credentials": False,
                }
            )
        routes[str(binding_key)] = route_payload
        binding_integrations[str(binding_key)] = dict(route_payload)
        custom_process[str(binding_key)] = dict(route_payload)
        action_handlers[str(binding_key)] = _connector_action_handler_payload(str(binding_key), route_payload)
        binding_provider = provider_by_binding.get(str(binding_key)) or ""
        if binding_provider:
            custom_process[binding_provider] = dict(route_payload)
    metadata["agent_binding_provider_routes"] = routes
    metadata["agent_binding_integrations"] = binding_integrations
    metadata["connector_action_handlers"] = action_handlers
    metadata["custom_process"] = custom_process
    return metadata


def _connector_action_handler_payload(binding_key: str, route_payload: dict) -> dict:
    route_provider = str(route_payload.get("route_provider") or "").strip()
    base = {
        "schema": "localos_connector_action_handler_v1",
        "binding_key": binding_key,
        "route_provider": route_provider,
        "status": str(route_payload.get("status") or "active"),
        "execution_boundary": str(route_payload.get("execution_boundary") or "localos_policy_envelope"),
        "approval_required": True,
        "audit_required": True,
        "external_side_effects_allowed_in_preview": False,
    }
    if route_provider == "openclaw":
        base.update(
            {
                "handler": "openclaw_policy_boundary",
                "credential_source": "openclaw_m2m",
                "preflight_resolution": "provider_route_openclaw_boundary",
                "next_step": "safe_preview",
            }
        )
    elif route_provider == "maton":
        base.update(
            {
                "handler": "maton_external_account_bridge",
                "credential_source": "externalbusinessaccounts:maton",
                "external_account_id": str(route_payload.get("external_account_id") or route_payload.get("auth_ref") or ""),
                "preflight_resolution": "provider_route_maton_external_account",
                "next_step": "safe_preview",
            }
        )
    elif route_provider == "manual":
        base.update(
            {
                "handler": "manual_human_fallback",
                "credential_source": "none",
                "preflight_resolution": "provider_route_manual_fallback",
                "next_step": "draft_only_human_action",
            }
        )
    elif route_provider == "native_localos":
        base.update(
            {
                "handler": "localos_native_domain",
                "credential_source": "localos_domain_data",
                "preflight_resolution": "native_localos",
                "next_step": "safe_preview",
            }
        )
    else:
        base.update(
            {
                "handler": "provider_route_unresolved",
                "credential_source": "",
                "preflight_resolution": "",
                "next_step": "resolve_connection",
            }
        )
    return base


def _apply_answer_connection_bindings(metadata: dict, answer_bindings: dict) -> dict:
    if not isinstance(answer_bindings, dict) or not answer_bindings:
        return metadata
    binding_integrations = metadata.get("agent_binding_integrations") if isinstance(metadata.get("agent_binding_integrations"), dict) else {}
    custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
    required_bindings = metadata.get("required_integration_bindings") if isinstance(metadata.get("required_integration_bindings"), list) else []
    provider_by_binding = _provider_by_binding_key(metadata)
    clean_answers = {}
    for binding_key, raw_config in answer_bindings.items():
        if not isinstance(raw_config, dict):
            continue
        clean_key = str(binding_key or "").strip()
        if not clean_key:
            continue
        clean_config = {}
        for key, value in raw_config.items():
            clean_value = str(value or "").strip()
            if clean_value:
                clean_config[str(key)] = clean_value
        if not clean_config:
            continue
        binding_process = custom_process.get(clean_key) if isinstance(custom_process.get(clean_key), dict) else {}
        binding_process.update(clean_config)
        custom_process[clean_key] = binding_process
        binding_payload = binding_integrations.get(clean_key) if isinstance(binding_integrations.get(clean_key), dict) else {}
        provider = provider_by_binding.get(clean_key) or ""
        if provider:
            binding_payload["provider"] = provider
            binding_payload["source"] = "agent_builder_answer"
        binding_payload["answer_config"] = dict(clean_config)
        binding_integrations[clean_key] = binding_payload
        if provider:
            provider_process = custom_process.get(provider) if isinstance(custom_process.get(provider), dict) else {}
            provider_process.update(clean_config)
            custom_process[provider] = provider_process
        for binding in required_bindings:
            if not isinstance(binding, dict):
                continue
            if str(binding.get("key") or "").strip() != clean_key:
                continue
            default_config = binding.get("default_config") if isinstance(binding.get("default_config"), dict) else {}
            merged_config = dict(default_config)
            for config_key, config_value in clean_config.items():
                merged_config[str(config_key)] = config_value
            binding["default_config"] = merged_config
            binding["answer_configured"] = True
        clean_answers[clean_key] = clean_config
    if clean_answers:
        metadata["builder_answer_connection_bindings"] = clean_answers
        metadata["agent_binding_integrations"] = binding_integrations
        metadata["custom_process"] = custom_process
        metadata["required_integration_bindings"] = required_bindings
    return metadata


def _provider_by_binding_key(metadata: dict) -> dict:
    result = {}
    bindings = metadata.get("required_integration_bindings") if isinstance(metadata.get("required_integration_bindings"), list) else []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        binding_key = str(binding.get("key") or "").strip()
        provider = str(binding.get("provider") or "").strip()
        if binding_key and provider:
            result[binding_key] = provider
    return result


def _apply_answer_bindings_to_version_payload(version_payload: dict, answer_bindings: dict) -> dict:
    if not isinstance(version_payload, dict):
        return {}
    if not isinstance(answer_bindings, dict) or not answer_bindings:
        return version_payload
    bindings = version_payload.get("required_integration_bindings") if isinstance(version_payload.get("required_integration_bindings"), list) else []
    for binding in bindings:
        if not isinstance(binding, dict):
            continue
        binding_key = str(binding.get("key") or "").strip()
        answer_config = answer_bindings.get(binding_key)
        if not isinstance(answer_config, dict):
            continue
        default_config = binding.get("default_config") if isinstance(binding.get("default_config"), dict) else {}
        merged_config = dict(default_config)
        for key, value in answer_config.items():
            clean_value = str(value or "").strip()
            if clean_value:
                merged_config[str(key)] = clean_value
        binding["default_config"] = merged_config
        binding["answer_configured"] = True
    return version_payload


def _missing_required_connection_choices(preview: dict, selected_bindings: dict) -> list[dict]:
    summary = preview.get("connection_summary") if isinstance(preview.get("connection_summary"), dict) else {}
    items = summary.get("items") if isinstance(summary.get("items"), list) else []
    missing = []
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        action = str(item.get("action") or "").strip()
        connections = item.get("connections") if isinstance(item.get("connections"), list) else []
        if key and action == "choose_existing" and len(connections) > 1 and key not in selected_bindings:
            missing.append(
                {
                    "key": key,
                    "provider": str(item.get("provider") or ""),
                    "title": str(item.get("title") or item.get("provider") or key),
                    "connection_count": len(connections),
                }
            )
    return missing


def _save_session_state(cursor, session_id: str, state: dict, status: str = "draft", blueprint_id: str = ""):
    cursor.execute(
        """
        UPDATE agent_builder_sessions
        SET status = %s,
            category = %s,
            messages_json = %s::jsonb,
            preview_json = %s::jsonb,
            missing_questions_json = %s::jsonb,
            blueprint_id = COALESCE(NULLIF(%s, ''), blueprint_id),
            updated_at = NOW()
        WHERE id = %s
        """,
        (
            status,
            str(state.get("category") or "custom"),
            json.dumps(state.get("messages") if isinstance(state.get("messages"), list) else [], ensure_ascii=False),
            json.dumps(state.get("preview") if isinstance(state.get("preview"), dict) else {}, ensure_ascii=False),
            json.dumps(state.get("missing_questions") if isinstance(state.get("missing_questions"), list) else [], ensure_ascii=False),
            blueprint_id,
            session_id,
        ),
    )


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
    return dict(cursor.fetchone())


@agent_builder_bp.route("/api/agent-builder/sessions", methods=["POST"])
def create_agent_builder_session():
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    business_id = str(payload.get("business_id") or "").strip()
    message = str(payload.get("message") or payload.get("description") or "").strip()
    if not business_id or not message:
        return _json_error("business_id and message are required", 400, "VALIDATION_ERROR")

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        allowed, access_error = _require_business_access(cursor, business_id, user_data)
        if not allowed:
            return access_error
        session_id = str(uuid.uuid4())
        state = build_agent_builder_state(
            [{"role": "user", "content": message}],
            str(payload.get("category") or ""),
            use_ai=_use_ai_compiler(payload),
            business_id=business_id,
            user_id=_user_id(user_data),
            connected_integrations=_load_builder_connection_inventory(cursor, business_id),
        )
        cursor.execute(
            """
            INSERT INTO agent_builder_sessions (
                id, business_id, created_by_user_id, status, initial_prompt, category,
                messages_json, preview_json, missing_questions_json
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s::jsonb, %s::jsonb, %s::jsonb)
            """,
            (
                session_id,
                business_id,
                _user_id(user_data),
                "draft",
                message,
                state["category"],
                json.dumps(state["messages"], ensure_ascii=False),
                json.dumps(state["preview"], ensure_ascii=False),
                json.dumps(state["missing_questions"], ensure_ascii=False),
            ),
        )
        db.conn.commit()
        session = _load_session(cursor, session_id)
        return jsonify({"success": True, "session": _normalize_session(session)}), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_builder_bp.route("/api/agent-builder/sessions/<session_id>/message", methods=["POST"])
def add_agent_builder_message(session_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}
    message = str(payload.get("message") or "").strip()
    if not message:
        return _json_error("message is required", 400, "VALIDATION_ERROR")

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        session = _load_session(cursor, session_id)
        if not session:
            return _json_error("Session not found", 404, "NOT_FOUND")
        allowed, access_error = _require_business_access(cursor, str(session.get("business_id") or ""), user_data)
        if not allowed:
            return access_error
        messages = append_user_message(parse_json_field(session.get("messages_json"), []), message)
        state = build_agent_builder_state(
            messages,
            str(payload.get("category") or session.get("category") or ""),
            use_ai=_use_ai_compiler(payload),
            business_id=str(session.get("business_id") or ""),
            user_id=_user_id(user_data),
            connected_integrations=_load_builder_connection_inventory(cursor, str(session.get("business_id") or "")),
        )
        _save_session_state(cursor, session_id, state)
        db.conn.commit()
        refreshed = _load_session(cursor, session_id)
        return jsonify({"success": True, "session": _normalize_session(refreshed)})
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


@agent_builder_bp.route("/api/agent-builder/sessions/<session_id>/create-blueprint", methods=["POST"])
def create_blueprint_from_agent_builder_session(session_id: str):
    user_data, error_response = _require_auth()
    if error_response:
        return error_response
    payload = request.get_json(silent=True) or {}

    db = DatabaseManager()
    cursor = db.conn.cursor()
    try:
        session = _load_session(cursor, session_id)
        if not session:
            return _json_error("Session not found", 404, "NOT_FOUND")
        business_id = str(session.get("business_id") or "")
        allowed, access_error = _require_business_access(cursor, business_id, user_data)
        if not allowed:
            return access_error
        preview = parse_json_field(session.get("preview_json"), {})
        feasibility = preview.get("feasibility") if isinstance(preview.get("feasibility"), dict) else {}
        setup_flow = preview.get("setup_flow") if isinstance(preview.get("setup_flow"), dict) else {}
        if feasibility.get("status") == "forbidden":
            return jsonify(
                {
                    "success": False,
                    "error": "Такой агент не может быть создан в рамках политики LocalOS.",
                    "code": "AGENT_REQUEST_FORBIDDEN",
                    "feasibility": feasibility,
                }
            ), 400
        if setup_flow and not bool(setup_flow.get("can_create_draft")):
            missing_questions = parse_json_field(session.get("missing_questions_json"), [])
            return jsonify(
                {
                    "success": False,
                    "error": "Сначала завершите настройку агента.",
                    "code": "AGENT_SETUP_INCOMPLETE",
                    "setup_flow": setup_flow,
                    "feasibility": feasibility,
                    "missing_questions": missing_questions,
                    "connection_summary": preview.get("connection_summary") if isinstance(preview.get("connection_summary"), dict) else {},
                    "connector_intelligence": preview.get("connector_intelligence") if isinstance(preview.get("connector_intelligence"), dict) else {},
                    "next_step": str(setup_flow.get("next_step") or ""),
                    "next_step_title": str(setup_flow.get("next_step_title") or ""),
                }
            ), 400
        if _compiler_plan_requires_confirmation(preview) and not bool(payload.get("accepted_compiler_plan")):
            return jsonify(
                {
                    "success": False,
                    "error": "Сначала подтвердите compiled workflow plan агента.",
                    "code": "AGENT_COMPILER_PLAN_CONFIRMATION_REQUIRED",
                    "compiler_policy_review": preview.get("compiler_policy_review") if isinstance(preview.get("compiler_policy_review"), dict) else {},
                    "setup_flow": setup_flow,
                    "next_step": "accept_compiler_plan",
                    "next_step_title": "Подтвердите план агента",
                }
            ), 400
        connection_inventory = _load_builder_connection_inventory(cursor, business_id)
        selected_bindings = _selected_connection_bindings(payload, preview, connection_inventory)
        selected_provider_routes = _selected_provider_routes(payload, preview, connection_inventory)
        missing_provider_routes = _missing_required_provider_routes(preview, selected_provider_routes)
        provider_route_errors = _provider_route_selection_errors(selected_provider_routes)
        if missing_provider_routes:
            return jsonify(
                {
                    "success": False,
                    "error": "Выберите provider route для обязательных шагов агента.",
                    "code": "AGENT_PROVIDER_ROUTE_REQUIRED",
                    "missing_provider_routes": missing_provider_routes,
                    "connection_readiness": preview.get("connection_readiness") if isinstance(preview.get("connection_readiness"), dict) else {},
                }
            ), 400
        if selected_provider_routes and not bool(payload.get("accepted_provider_routes")):
            return jsonify(
                {
                    "success": False,
                    "error": "Подтвердите выбранные provider routes перед созданием draft.",
                    "code": "AGENT_PROVIDER_ROUTES_CONFIRMATION_REQUIRED",
                    "selected_provider_routes": selected_provider_routes,
                    "connection_readiness": preview.get("connection_readiness") if isinstance(preview.get("connection_readiness"), dict) else {},
                    "next_step": "accept_provider_routes",
                    "next_step_title": "Подтвердите routes агента",
                }
            ), 400
        if provider_route_errors:
            return jsonify(
                {
                    "success": False,
                    "error": "Для выбранного provider route не хватает доступа.",
                    "code": "AGENT_PROVIDER_ROUTE_ACCESS_REQUIRED",
                    "provider_route_errors": provider_route_errors,
                    "connection_readiness": preview.get("connection_readiness") if isinstance(preview.get("connection_readiness"), dict) else {},
                    "next_step": "connect_provider_account",
                    "next_step_title": "Подключите доступ",
                }
            ), 400
        missing_connection_choices = _missing_required_connection_choices(preview, selected_bindings)
        if missing_connection_choices:
            return jsonify(
                {
                    "success": False,
                    "error": "Выберите, какие существующие подключения использовать для агента.",
                    "code": "AGENT_CONNECTION_CHOICE_REQUIRED",
                    "missing_connection_choices": missing_connection_choices,
                    "connection_summary": preview.get("connection_summary") if isinstance(preview.get("connection_summary"), dict) else {},
                }
            ), 400
        planner_context = preview.get("openclaw_planner_context") if isinstance(preview.get("openclaw_planner_context"), dict) else {}
        planner_loop = preview.get("openclaw_planner_loop") if isinstance(preview.get("openclaw_planner_loop"), dict) else {}
        description = str(preview.get("understood_task") or session.get("initial_prompt") or "").strip()
        category = str(preview.get("category") or session.get("category") or "").strip()
        billing = charge_agent_creation_credits(
            cursor,
            business_id=business_id,
            user_id=_user_id(user_data),
            source_id=session_id,
            description=description,
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
        draft = compile_agent_blueprint(
            description,
            category,
            use_ai=_use_ai_compiler(payload),
            business_id=business_id,
            user_id=_user_id(user_data),
            planner_context=planner_context,
        )
        metadata = draft.get("metadata") if isinstance(draft.get("metadata"), dict) else {}
        metadata["builder"] = "dialog_builder_v1"
        metadata["compiler"] = "agent_compiler_v1"
        metadata["builder_session_id"] = session_id
        metadata["agent_builder_preview"] = preview
        metadata["feasibility"] = feasibility
        metadata["openclaw_planner_context"] = planner_context
        metadata["openclaw_planner_loop"] = planner_loop
        metadata["required_connectors"] = preview.get("required_connectors") if isinstance(preview.get("required_connectors"), list) else []
        metadata["builder_setup_flow"] = setup_flow
        metadata["agent_setup"] = preview_to_setup(preview)
        metadata["setup_completed"] = True
        metadata["builder_compiler_plan_accepted"] = bool(payload.get("accepted_compiler_plan"))
        metadata["builder_provider_routes_accepted"] = bool(payload.get("accepted_provider_routes"))
        answer_bindings = preview.get("connection_answer_bindings") if isinstance(preview.get("connection_answer_bindings"), dict) else {}
        metadata = _apply_answer_connection_bindings(metadata, answer_bindings)
        metadata = _apply_selected_connection_bindings(metadata, selected_bindings)
        metadata = _apply_selected_provider_routes(metadata, selected_provider_routes)
        metadata = _apply_answer_connection_bindings(metadata, answer_bindings)
        metadata["builder_selected_connection_bindings"] = selected_bindings
        metadata["builder_selected_provider_routes"] = selected_provider_routes
        metadata["builder_missing_provider_routes"] = missing_provider_routes
        blueprint_id = str(uuid.uuid4())
        metadata["billing"] = billing
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
                str(draft.get("name") or preview.get("agent_name") or "Кастомный агент").strip(),
                str(draft.get("category") or category or "custom").strip().lower(),
                description or None,
                "draft",
                _user_id(user_data),
                json.dumps(metadata, ensure_ascii=False),
            ),
        )
        version_payload = draft.get("version_payload") if isinstance(draft.get("version_payload"), dict) else {}
        version_payload = _apply_answer_bindings_to_version_payload(version_payload, answer_bindings)
        version = _insert_version(cursor, blueprint_id, version_payload, user_data)
        _save_session_state(
            cursor,
            session_id,
            {
                "category": draft.get("category") or category or "custom",
                "messages": parse_json_field(session.get("messages_json"), []),
                "preview": preview,
                "missing_questions": parse_json_field(session.get("missing_questions_json"), []),
            },
            "blueprint_created",
            blueprint_id,
        )
        db.conn.commit()
        cursor.execute(
            """
            SELECT b.*,
                   v.id AS latest_version_id,
                   v.version_number AS latest_version_number,
                   v.goal AS latest_goal
            FROM agent_blueprints b
            LEFT JOIN LATERAL (
                SELECT id, version_number, goal
                FROM agent_blueprint_versions
                WHERE blueprint_id = b.id
                ORDER BY version_number DESC
                LIMIT 1
            ) v ON TRUE
            WHERE b.id = %s
            """,
            (blueprint_id,),
        )
        blueprint = dict(cursor.fetchone())
        refreshed = _load_session(cursor, session_id)
        connection_preflight = build_agent_integration_preflight(
            cursor,
            business_id=business_id,
            metadata=metadata,
            input_payload={},
        )
        post_create_handoff = _build_post_create_handoff(connection_preflight)
        return jsonify(
            {
                "success": True,
                "session": _normalize_session(refreshed),
                "blueprint": blueprint,
                "version": version,
                "billing": billing,
                "connection_preflight": connection_preflight,
                "post_create_handoff": post_create_handoff,
                "next_step": str(post_create_handoff.get("next_step") or "review_and_activate"),
            }
        ), 201
    except Exception:
        db.conn.rollback()
        raise
    finally:
        db.close()


def _build_post_create_handoff(connection_preflight: dict) -> dict:
    missing = connection_preflight.get("missing") if isinstance(connection_preflight.get("missing"), list) else []
    items = connection_preflight.get("items") if isinstance(connection_preflight.get("items"), list) else []
    ready = bool(connection_preflight.get("ready"))
    connection_plan = _build_handoff_connection_plan(items)
    if ready:
        return {
            "schema": "localos_agent_post_create_handoff_v1",
            "status": "ready_for_preview",
            "next_step": "run_preview",
            "workspace_mode": "run",
            "next_binding_key": "",
            "next_binding": {},
            "next_route": {},
            "title": "Draft агента создан",
            "description": "Подключения готовы. Следующий шаг — preview run без внешних действий; после него можно будет активировать агента.",
            "missing_bindings": [],
            "items": items,
            "connection_plan": connection_plan,
        }
    providers = []
    for item in missing:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        if provider and provider not in providers:
            providers.append(provider)
    labels = [provider.replace("_", " ") for provider in providers[:3]]
    next_binding_key = _first_missing_binding_key(missing)
    next_binding = _connection_plan_item_by_key(connection_plan, next_binding_key)
    next_action = str(next_binding.get("action") or "").strip()
    route_required = next_action == "choose_route"
    return {
        "schema": "localos_agent_post_create_handoff_v1",
        "status": "needs_provider_route" if route_required else "needs_connections",
        "next_step": "choose_provider_route" if route_required else "connect_required_integrations",
        "workspace_mode": "connections",
        "next_binding_key": next_binding_key,
        "next_binding": next_binding,
        "next_route": _preferred_handoff_route(next_binding),
        "title": "Draft агента создан. Выберите маршрут" if route_required else "Draft агента создан. Остались подключения",
        "description": (
            f"Выберите, как LocalOS выполнит шаги для: {', '.join(labels) if labels else 'обязательные источники'}, затем запустите preflight и preview run."
            if route_required
            else f"Подключите {', '.join(labels) if labels else 'обязательные источники'}, затем запустите preflight и preview run."
        ),
        "missing_bindings": missing,
        "items": items,
        "connection_plan": connection_plan,
    }


def _first_missing_binding_key(items: list) -> str:
    for item in items:
        if not isinstance(item, dict):
            continue
        key = str(item.get("key") or "").strip()
        if key:
            return key
    return ""


def _build_handoff_connection_plan(items: list) -> dict:
    catalog_by_provider = {
        str(item.get("provider") or "").strip(): item
        for item in integration_provider_catalog()
        if isinstance(item, dict) and str(item.get("provider") or "").strip()
    }
    plan_items = []
    for item in items:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        status = str(item.get("status") or "").strip()
        resolution = str(item.get("resolution") or "").strip()
        catalog_item = catalog_by_provider.get(provider, {})
        action = _handoff_connection_action(status, resolution, catalog_item)
        provider_routes = connector_provider_routes(provider, str(item.get("capability") or ""))
        route_state = "connected" if action in {"ready", "native_ready"} else best_provider_route_state(provider_routes)
        recommended_route = _recommended_handoff_route(provider_routes, action, provider)
        plan_items.append(
            {
                "key": str(item.get("key") or provider or ""),
                "provider": provider,
                "title": str(catalog_item.get("title") or provider.replace("_", " ") or "подключение"),
                "capability": str(item.get("capability") or ""),
                "trigger": str(item.get("trigger") or ""),
                "direction": str(item.get("direction") or ""),
                "binding_status": status,
                "action": action,
                "primary_label": _handoff_connection_label(action),
                "explanation": _handoff_connection_explanation(provider, action, item),
                "route_state": route_state,
                "route_summary": _handoff_connection_route_summary(provider, action, route_state, item),
                "provider_routes": provider_routes,
                "recommended_route": recommended_route,
                "recommended_route_reason": _recommended_handoff_route_reason(recommended_route, action, provider),
                "missing_config": item.get("missing_config") if isinstance(item.get("missing_config"), list) else [],
                "approval_required": bool(item.get("required", True)),
                "existing_integrations": [],
                "attached_integrations": [],
                "provider_paths": _handoff_provider_paths(catalog_item),
            }
        )
    missing_count = len([item for item in plan_items if item.get("action") not in {"ready", "native_ready"}])
    return {
        "schema": "localos_agent_connection_plan_v1",
        "status": "ready" if missing_count == 0 else "needs_action",
        "missing_count": missing_count,
        "items": plan_items,
    }


def _handoff_connection_action(status: str, resolution: str, catalog_item: dict) -> str:
    if resolution in {"provider_route_required", "agent_integration_needs_provider_route", "builder_answer_needs_provider_route"}:
        return "choose_route"
    if status == "ready":
        return "native_ready" if resolution == "native_localos" else "ready"
    if str(catalog_item.get("status") or "").strip() == "planned":
        return "planned_provider"
    return "connect_required"


def _handoff_connection_label(action: str) -> str:
    labels = {
        "ready": "Готово",
        "native_ready": "Готово в LocalOS",
        "choose_route": "Выберите маршрут выполнения",
        "connect_required": "Подключите сервис",
        "planned_provider": "Будет доступно позже",
    }
    return labels.get(action, "Проверьте подключение")


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
        action = str(item.get("action") or "").strip()
        if action not in {"ready", "native_ready"}:
            return item
    return {}


def _preferred_handoff_route(plan_item: dict) -> dict:
    routes = plan_item.get("provider_routes") if isinstance(plan_item.get("provider_routes"), list) else []
    recommended_route = plan_item.get("recommended_route") if isinstance(plan_item.get("recommended_route"), dict) else {}
    if recommended_route:
        return recommended_route
    for state in ["available", "manual", "planned", "connected"]:
        for route in routes:
            if isinstance(route, dict) and str(route.get("state") or route.get("status") or "") == state:
                return route
    return routes[0] if routes and isinstance(routes[0], dict) else {}


def _recommended_handoff_route(routes: list, action: str, provider: str) -> dict:
    if not routes:
        return {}
    provider_key = str(provider or "").strip()
    action_key = str(action or "").strip()
    preferred = ["openclaw", "maton", "native_localos", "manual", "composio"]
    if provider_key in {"localos_finance", "business_profile"} or action_key == "native_ready":
        preferred = ["native_localos", "openclaw", "manual", "maton", "composio"]
    for candidate in preferred:
        for route in routes:
            if not isinstance(route, dict):
                continue
            state = str(route.get("state") or route.get("status") or "")
            if str(route.get("provider") or "") == candidate and state in {"available", "connected", "manual"}:
                return route
    for state in ["available", "manual", "planned", "connected"]:
        for route in routes:
            if isinstance(route, dict) and str(route.get("state") or route.get("status") or "") == state:
                return route
    return routes[0] if routes and isinstance(routes[0], dict) else {}


def _recommended_handoff_route_reason(route: dict, action: str, provider: str) -> str:
    route_provider = str(route.get("provider") or "").strip()
    if route_provider == "openclaw":
        return "Рекомендуем OpenClaw: он даёт planner/execution boundary, а LocalOS держит policy, billing, audit и approvals."
    if route_provider == "maton":
        return "Рекомендуем Maton, если нужен сохранённый API key для connector bridge внутри LocalOS policy."
    if route_provider == "native_localos":
        return "Рекомендуем нативный маршрут LocalOS для доменных данных и действий, которые уже живут внутри продукта."
    if route_provider == "manual":
        return "Ручной fallback подходит для draft-only режима: LocalOS подготовит результат, внешний шаг выполнит человек."
    if route_provider == "composio":
        return "Composio пока planned route: можно показать будущий OAuth path, но не активировать агента через него."
    return ""


def _handoff_connection_explanation(provider: str, action: str, item: dict) -> str:
    if action in {"ready", "native_ready"}:
        return "Подключение готово для preflight и активации."
    if action == "choose_route":
        return "Выберите route выполнения: существующий доступ, OpenClaw boundary, Maton key или ручной fallback."
    if action == "planned_provider":
        return "Этот provider есть в roadmap, но пока недоступен для активации агента."
    missing_config = item.get("missing_config") if isinstance(item.get("missing_config"), list) else []
    if missing_config:
        return f"Заполните: {', '.join([str(value) for value in missing_config])}."
    return f"Подключите {provider.replace('_', ' ')}, чтобы агент можно было активировать."


def _handoff_connection_route_summary(provider: str, action: str, route_state: str, item: dict) -> str:
    if action in {"ready", "native_ready"}:
        return "Provider route готов, можно переходить к safe preview."
    title = provider.replace("_", " ") or "подключение"
    if action == "choose_route":
        return f"{title}: выберите route выполнения перед safe preview."
    missing_config = item.get("missing_config") if isinstance(item.get("missing_config"), list) else []
    if missing_config:
        return f"{title}: заполните настройки {', '.join([str(value) for value in missing_config])}."
    if route_state == "available":
        return f"{title}: есть разрешённый provider route, подключите его для preflight."
    if route_state == "manual":
        return f"{title}: доступен ручной fallback, агент останется под контролем человека."
    if route_state == "planned":
        return f"{title}: provider route запланирован, но пока не активирует агента."
    return f"{title}: нет готового provider route внутри LocalOS policy envelope."


def _handoff_provider_paths(catalog_item: dict) -> list:
    providers = catalog_item.get("providers") if isinstance(catalog_item.get("providers"), list) else []
    result = []
    for item in providers:
        if not isinstance(item, dict):
            continue
        provider = str(item.get("provider") or "").strip()
        if not provider:
            continue
        result.append(
            {
                "provider": provider,
                "label": str(item.get("label") or provider),
                "status": str(item.get("status") or "unknown"),
            }
        )
    return result
