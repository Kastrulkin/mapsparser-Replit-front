from __future__ import annotations

import json
from typing import Any, Dict, List


NATIVE_READY_PROVIDERS = {"localos_finance", "business_profile"}
ROUTE_REQUIRED_PROVIDERS = {"google_sheets", "telegram", "maton"}
GOOGLE_SHEETS_EXTERNAL_ACCOUNT_SOURCES = {"google_sheets", "google_business"}


def parse_json_field(value: Any, fallback: Any) -> Any:
    if value is None:
        return fallback
    if isinstance(value, (dict, list)):
        return value
    if isinstance(value, str):
        try:
            return json.loads(value)
        except Exception:
            return fallback
    return fallback


def build_agent_integration_preflight(
    cursor: Any,
    *,
    business_id: str,
    metadata: Dict[str, Any],
    input_payload: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    required = metadata.get("required_integration_bindings") if isinstance(metadata.get("required_integration_bindings"), list) else []
    input_payload = input_payload if isinstance(input_payload, dict) else {}
    integrations = _load_agent_integrations(cursor, business_id)
    by_provider: Dict[str, List[Dict[str, Any]]] = {}
    for integration in integrations:
        provider = str(integration.get("provider") or "").strip()
        if provider:
            by_provider.setdefault(provider, []).append(integration)
    items = []
    for binding in required:
        if not isinstance(binding, dict):
            continue
        items.append(_binding_preflight_item(binding, by_provider, input_payload, metadata))
    missing = [item for item in items if item.get("status") != "ready" and item.get("required")]
    return {
        "status": "ready" if not missing else "blocked",
        "ready": not missing,
        "items": items,
        "missing": missing,
        "missing_count": len(missing),
        "next_action": "" if not missing else "connect_required_integrations",
    }


def _binding_preflight_item(
    binding: Dict[str, Any],
    by_provider: Dict[str, List[Dict[str, Any]]],
    input_payload: Dict[str, Any],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    provider = str(binding.get("provider") or "").strip()
    required_config = [str(item) for item in (binding.get("required_config") if isinstance(binding.get("required_config"), list) else [])]
    integrations = by_provider.get(provider) or []
    active_integrations = [item for item in integrations if str(item.get("status") or "") == "active"]
    input_resolution = _input_resolution(provider, required_config, input_payload)
    if input_resolution.get("ready"):
        return _base_item(binding, "ready", "input_payload", "", [], str(input_resolution.get("summary") or ""))
    if provider in NATIVE_READY_PROVIDERS:
        return _base_item(binding, "ready", "native_localos", "", [], "LocalOS native domain is available.")
    default_config = binding.get("default_config") if isinstance(binding.get("default_config"), dict) else {}
    metadata_config = _metadata_binding_config(metadata, provider, str(binding.get("key") or ""))
    if metadata_config:
        route_provider = str(metadata_config.get("route_provider") or "").strip()
        route_status = str(metadata_config.get("status") or "active").strip()
        if route_provider == "openclaw" and route_status == "active":
            return _base_item(
                binding,
                "ready",
                "provider_route_openclaw_boundary",
                str(metadata_config.get("integration_id") or "openclaw_boundary"),
                [],
                "OpenClaw boundary is selected for this binding inside the LocalOS policy envelope.",
            )
        if route_provider == "maton" and route_status == "active":
            external_account_id = str(metadata_config.get("external_account_id") or metadata_config.get("auth_ref") or "").strip()
            if external_account_id:
                return _base_item(
                    binding,
                    "ready",
                    "provider_route_maton_external_account",
                    str(metadata_config.get("integration_id") or external_account_id),
                    [],
                "Maton.ai key is selected for the provider bridge on this binding.",
                )
            return _base_item(
                binding,
                "needs_config",
                "provider_route_maton_missing_key",
                "",
                ["external_account_id"],
                "Maton.ai route is selected, but no saved Maton key is bound.",
            )
        if route_provider == "manual" and route_status == "active":
            return _base_item(
                binding,
                "ready",
                "provider_route_manual_fallback",
                str(metadata_config.get("integration_id") or "manual_fallback"),
                [],
                "Manual fallback is selected: LocalOS will prepare draft artifacts and require a human-operated external action.",
            )
        selected_integration = _selected_active_integration(metadata_config, active_integrations)
        reconnect_integration = _google_sheets_reconnect_integration(
            provider,
            metadata_config,
            active_integrations,
        )
        if reconnect_integration:
            return _base_item(
                binding,
                "needs_connection",
                "google_sheets_auth_reconnect_required",
                str(reconnect_integration.get("id") or metadata_config.get("integration_id") or ""),
                [],
                "Сохранённый Google-доступ больше не работает. Переподключите Google Таблицы и повторите запуск.",
            )
        selected_config = parse_json_field(selected_integration.get("config_json"), {})
        selected_config = selected_config if isinstance(selected_config, dict) else {}
        resolved_config = _merge_default_config(default_config, selected_config)
        resolved_config = _merge_default_config(resolved_config, metadata_config)
        missing_metadata_config = [key for key in required_config if not str(resolved_config.get(key) or "").strip()]
        if provider in ROUTE_REQUIRED_PROVIDERS and not route_provider and not missing_metadata_config:
            if provider == "google_sheets" and _has_native_auth_ref(metadata_config, active_integrations):
                return _base_item(
                    binding,
                    "ready",
                    "agent_integration_native_provider",
                    str(metadata_config.get("integration_id") or ""),
                    [],
                    "Google Sheets credential and sheet target are connected for native LocalOS read.",
                )
            return _base_item(
                binding,
                "needs_connection",
                "provider_route_required",
                str(metadata_config.get("integration_id") or ""),
                [],
                "Resource or credential is selected; choose the execution route before preview or activation.",
            )
        if not missing_metadata_config:
            return _base_item(
                binding,
                "ready",
                "blueprint_metadata",
                str(resolved_config.get("integration_id") or ""),
                [],
                "Blueprint metadata contains the required connection config.",
            )
        return _base_item(
            binding,
            "needs_config",
            "blueprint_metadata_missing_config",
            str(metadata_config.get("integration_id") or ""),
            missing_metadata_config,
            _missing_config_summary(provider, missing_metadata_config),
        )
    answer_config = _metadata_answer_config(metadata, provider, str(binding.get("key") or ""))
    if answer_config:
        resolved_answer_config = _merge_default_config(default_config, answer_config)
        missing_answer_config = [key for key in required_config if not str(resolved_answer_config.get(key) or "").strip()]
        if missing_answer_config:
            return _base_item(
                binding,
                "needs_config",
                "builder_answer_missing_config",
                "",
                missing_answer_config,
                _missing_config_summary(provider, missing_answer_config),
            )
        return _base_item(
            binding,
            "needs_connection",
            "builder_answer_needs_provider_route",
            "",
            [],
            "User supplied the resource target in the builder dialog; choose or connect a provider route before preview.",
        )
    for integration in active_integrations:
        config = parse_json_field(integration.get("config_json"), {})
        config = config if isinstance(config, dict) else {}
        resolved_config = _merge_default_config(default_config, config)
        missing_config = [key for key in required_config if not str(resolved_config.get(key) or "").strip()]
        if not missing_config:
            if provider in ROUTE_REQUIRED_PROVIDERS:
                if provider == "google_sheets" and _integration_auth_is_ready(integration):
                    return _base_item(
                        binding,
                        "ready",
                        "agent_integration_native_provider",
                        str(integration.get("id") or ""),
                        [],
                        "Google Sheets credential and sheet target are connected for native LocalOS read.",
                    )
                if provider == "google_sheets" and str(integration.get("auth_ref") or "").strip():
                    return _base_item(
                        binding,
                        "needs_connection",
                        "google_sheets_auth_reconnect_required",
                        str(integration.get("id") or ""),
                        [],
                        "Сохранённый Google-доступ больше не работает. Переподключите Google Таблицы и повторите запуск.",
                    )
                return _base_item(
                    binding,
                    "needs_connection",
                    "agent_integration_needs_provider_route",
                    str(integration.get("id") or ""),
                    [],
                    "Connection exists; choose the execution route before preview or activation.",
                )
            return _base_item(
                binding,
                "ready",
                "agent_integration",
                str(integration.get("id") or ""),
                [],
                str(integration.get("display_name") or integration.get("provider") or provider),
            )
    if active_integrations:
        selected_integration = active_integrations[0]
        config = parse_json_field(selected_integration.get("config_json"), {})
        config = config if isinstance(config, dict) else {}
        resolved_config = _merge_default_config(default_config, config)
        missing_config = [key for key in required_config if not str(resolved_config.get(key) or "").strip()]
        return _base_item(
            binding,
            "needs_config",
            "agent_integration_missing_config",
            str(selected_integration.get("id") or ""),
            missing_config,
            _missing_config_summary(provider, missing_config),
        )
    missing_config = required_config
    return _base_item(binding, "needs_connection", "missing_integration", "", missing_config, "")


def _has_native_auth_ref(metadata_config: Dict[str, Any], active_integrations: List[Dict[str, Any]]) -> bool:
    integration_id = str(metadata_config.get("integration_id") or "").strip()
    has_any_auth_ref = False
    for integration in active_integrations:
        if _integration_auth_is_ready(integration):
            has_any_auth_ref = True
        if integration_id and str(integration.get("id") or "").strip() != integration_id:
            continue
        if _integration_auth_is_ready(integration):
            return True
    if integration_id:
        return has_any_auth_ref
    return False


def _integration_auth_is_ready(integration: Dict[str, Any]) -> bool:
    if not str(integration.get("auth_ref") or "").strip():
        return False
    auth_was_checked = "auth_account_id" in integration
    if not auth_was_checked:
        return True
    return (
        bool(str(integration.get("auth_account_id") or "").strip())
        and integration.get("auth_is_active") is True
    )


def _google_sheets_reconnect_integration(
    provider: str,
    metadata_config: Dict[str, Any],
    active_integrations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    if provider != "google_sheets":
        return {}
    integration_id = str(metadata_config.get("integration_id") or "").strip()
    for integration in active_integrations:
        if integration_id and str(integration.get("id") or "").strip() != integration_id:
            continue
        if (
            str(integration.get("auth_ref") or "").strip()
            and "auth_account_id" in integration
            and not _integration_auth_is_ready(integration)
        ):
            return integration
    return {}


def _selected_active_integration(
    metadata_config: Dict[str, Any],
    active_integrations: List[Dict[str, Any]],
) -> Dict[str, Any]:
    integration_id = str(metadata_config.get("integration_id") or "").strip()
    if not integration_id:
        return {}
    for integration in active_integrations:
        if str(integration.get("id") or "").strip() == integration_id:
            return integration
    return {}


def _merge_default_config(default_config: Dict[str, Any], selected_config: Dict[str, Any]) -> Dict[str, Any]:
    resolved = dict(default_config)
    for key, value in selected_config.items():
        resolved[str(key)] = value
    return resolved


def _base_item(
    binding: Dict[str, Any],
    status: str,
    resolution: str,
    integration_id: str,
    missing_config: List[str],
    summary: str,
) -> Dict[str, Any]:
    policy = _policy_explanation(binding, status, resolution, missing_config)
    return {
        "key": str(binding.get("key") or ""),
        "provider": str(binding.get("provider") or ""),
        "direction": str(binding.get("direction") or ""),
        "capability": str(binding.get("capability") or ""),
        "trigger": str(binding.get("trigger") or ""),
        "required": bool(binding.get("required", True)),
        "status": status,
        "resolution": resolution,
        "integration_id": integration_id,
        "missing_config": missing_config,
        "summary": summary,
        "execution_boundary": policy["execution_boundary"],
        "autonomy_level": policy["autonomy_level"],
        "credential_state": policy["credential_state"],
        "approval_state": policy["approval_state"],
        "policy_summary": policy["policy_summary"],
        "next_action_label": policy["next_action_label"],
    }


def _policy_explanation(
    binding: Dict[str, Any],
    status: str,
    resolution: str,
    missing_config: List[str],
) -> Dict[str, str]:
    provider = str(binding.get("provider") or "provider").strip()
    capability = str(binding.get("capability") or "").strip()
    approval_required = binding.get("approval_required", True) is not False
    write_like = _capability_is_write_like(capability)
    if resolution == "provider_route_openclaw_boundary":
        return {
            "execution_boundary": "openclaw_inside_localos_policy",
            "autonomy_level": "supervised",
            "credential_state": "localos_managed_boundary",
            "approval_state": "approval_required" if approval_required or write_like else "preflight_only",
            "policy_summary": "OpenClaw выполнит маршрут внутри лимитов, аудита и approval gate LocalOS.",
            "next_action_label": "Запустить safe preview",
        }
    if resolution == "provider_route_maton_external_account":
        return {
            "execution_boundary": "maton_bridge_inside_localos_policy",
            "autonomy_level": "supervised",
            "credential_state": "external_account_bound",
            "approval_state": "approval_required" if approval_required or write_like else "preflight_only",
            "policy_summary": "Maton key выбран как provider bridge; LocalOS оставляет policy, billing и audit у себя.",
            "next_action_label": "Запустить safe preview",
        }
    if resolution == "provider_route_manual_fallback":
        return {
            "execution_boundary": "human_operated_fallback",
            "autonomy_level": "draft_only",
            "credential_state": "no_external_credentials",
            "approval_state": "human_action_required",
            "policy_summary": "LocalOS подготовит черновик или handoff, но внешнее действие выполнит человек.",
            "next_action_label": "Проверить черновик",
        }
    if resolution == "native_localos":
        return {
            "execution_boundary": "localos_native_domain",
            "autonomy_level": "supervised",
            "credential_state": "localos_native",
            "approval_state": "approval_required" if approval_required or write_like else "preflight_only",
            "policy_summary": "Домен LocalOS доступен нативно; запись остаётся за limits и approval gate.",
            "next_action_label": "Запустить safe preview",
        }
    if status == "ready":
        return {
            "execution_boundary": "connected_provider",
            "autonomy_level": "supervised",
            "credential_state": "connected",
            "approval_state": "approval_required" if approval_required or write_like else "preflight_only",
            "policy_summary": f"{provider} подключён; runtime пройдёт через preflight, audit и approval policy.",
            "next_action_label": "Запустить safe preview",
        }
    if status == "needs_config":
        return {
            "execution_boundary": "blocked_until_configured",
            "autonomy_level": "not_runnable",
            "credential_state": "missing_config",
            "approval_state": "blocked",
            "policy_summary": f"{provider} найден, но не хватает настроек: {', '.join(missing_config)}.",
            "next_action_label": "Заполнить настройки",
        }
    if resolution == "google_sheets_auth_reconnect_required":
        return {
            "execution_boundary": "blocked_until_connected",
            "autonomy_level": "not_runnable",
            "credential_state": "reconnect_required",
            "approval_state": "blocked",
            "policy_summary": "Google-доступ больше не работает. До переподключения LocalOS не читает таблицу и ничего не запускает.",
            "next_action_label": "Переподключить Google-доступ",
        }
    if resolution in {"provider_route_required", "agent_integration_needs_provider_route", "builder_answer_needs_provider_route"}:
        return {
            "execution_boundary": "blocked_until_route_selected",
            "autonomy_level": "not_runnable",
            "credential_state": "route_not_selected",
            "approval_state": "blocked",
            "policy_summary": f"{provider} найден, но LocalOS ещё не знает, выполнять шаг через OpenClaw, Maton, LocalOS или ручной fallback.",
            "next_action_label": "Выбрать маршрут выполнения",
        }
    return {
        "execution_boundary": "blocked_until_connected",
        "autonomy_level": "not_runnable",
        "credential_state": "missing_connection",
        "approval_state": "blocked",
        "policy_summary": f"{provider} нужен агенту, но пока не подключён и не выбран provider route.",
        "next_action_label": "Подключить сервис",
    }


def _capability_is_write_like(capability: str) -> bool:
    markers = [".create", ".send", ".publish", ".settle", ".reserve", "append_row", "send_"]
    return any(marker in capability for marker in markers)


def _input_resolution(provider: str, required_config: List[str], input_payload: Dict[str, Any]) -> Dict[str, Any]:
    if provider == "google_sheets" and isinstance(input_payload.get("rows"), list) and input_payload.get("rows"):
        return {"ready": True, "summary": "Inline rows supplied for this run."}
    if provider == "telegram" and (input_payload.get("message_text") or input_payload.get("chat_id")):
        return {"ready": True, "summary": "Telegram trigger payload supplied for this run."}
    if not required_config:
        return {"ready": False}
    if provider != "google_sheets":
        return {"ready": False}
    has_required = all(str(input_payload.get(key) or "").strip() for key in required_config)
    if has_required and str(input_payload.get("integration_id") or "").strip():
        return {"ready": True, "summary": "Run input supplies Google Sheets binding config."}
    return {"ready": False}


def _metadata_binding_config(metadata: Dict[str, Any], provider: str, binding_key: str) -> Dict[str, Any]:
    custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
    binding_integrations = (
        metadata.get("agent_binding_integrations")
        if isinstance(metadata.get("agent_binding_integrations"), dict)
        else {}
    )
    provider_routes = (
        metadata.get("agent_binding_provider_routes")
        if isinstance(metadata.get("agent_binding_provider_routes"), dict)
        else {}
    )
    route_config = provider_routes.get(binding_key) if isinstance(provider_routes.get(binding_key), dict) else {}
    candidates = [
        custom_process.get(provider),
        custom_process.get(binding_key),
    ]
    if provider == "google_sheets":
        candidates.extend([custom_process.get("google_sheets_read"), custom_process.get("google_sheets_append")])
    candidates.append(binding_integrations.get(binding_key))
    for candidate in candidates:
        if isinstance(candidate, dict):
            has_connection_anchor = _metadata_candidate_has_connection_anchor(candidate)
            if not has_connection_anchor:
                continue
            candidate_with_route = dict(candidate)
            for key, value in route_config.items():
                candidate_with_route[str(key)] = value
            answer_config = candidate.get("answer_config") if isinstance(candidate.get("answer_config"), dict) else {}
            if answer_config:
                merged = dict(candidate_with_route)
                for key, value in answer_config.items():
                    if not str(merged.get(str(key)) or "").strip():
                        merged[str(key)] = value
                return merged
            return candidate_with_route
    if route_config:
        return dict(route_config)
    return {}


def resolve_agent_binding_runtime_config(metadata: Dict[str, Any], provider: str, binding_key: str) -> Dict[str, Any]:
    binding_integrations = (
        metadata.get("agent_binding_integrations")
        if isinstance(metadata.get("agent_binding_integrations"), dict)
        else {}
    )
    custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
    candidates = [
        custom_process.get(binding_key),
        custom_process.get(provider),
    ]
    if provider == "google_sheets":
        candidates.extend([custom_process.get("google_sheets_read"), custom_process.get("google_sheets_append")])
    candidates.append(binding_integrations.get(binding_key))
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        resolved: Dict[str, Any] = {}
        for source in (
            candidate.get("answer_config") if isinstance(candidate.get("answer_config"), dict) else {},
            candidate,
        ):
            if not isinstance(source, dict):
                continue
            for key, value in source.items():
                clean_key = str(key or "").strip()
                if not clean_key or clean_key == "answer_config":
                    continue
                if value in ("", None, [], {}):
                    continue
                resolved.setdefault(clean_key, value)
        if resolved:
            return resolved
    return {}


def _metadata_candidate_has_connection_anchor(candidate: Dict[str, Any]) -> bool:
    for key in ["integration_id", "route_provider", "external_account_id", "auth_ref"]:
        if str(candidate.get(key) or "").strip():
            return True
    return False


def _metadata_answer_config(metadata: Dict[str, Any], provider: str, binding_key: str) -> Dict[str, Any]:
    binding_integrations = (
        metadata.get("agent_binding_integrations")
        if isinstance(metadata.get("agent_binding_integrations"), dict)
        else {}
    )
    custom_process = metadata.get("custom_process") if isinstance(metadata.get("custom_process"), dict) else {}
    candidates = [
        binding_integrations.get(binding_key),
        custom_process.get(binding_key),
        custom_process.get(provider),
    ]
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        answer_config = candidate.get("answer_config") if isinstance(candidate.get("answer_config"), dict) else {}
        if answer_config:
            return answer_config
        if not _metadata_candidate_has_connection_anchor(candidate):
            clean_candidate = {
                str(key): value
                for key, value in candidate.items()
                if str(value or "").strip()
            }
            if clean_candidate:
                return clean_candidate
    return {}


def _missing_config_summary(provider: str, missing_config: List[str]) -> str:
    if not missing_config:
        return "Connection was found, but LocalOS could not verify the required config."
    provider_label = provider or "connection"
    return f"{provider_label} connection is selected, but missing required config: {', '.join(missing_config)}."


def _load_agent_integrations(cursor: Any, business_id: str) -> List[Dict[str, Any]]:
    if not business_id:
        return []
    integrations: List[Dict[str, Any]] = []
    try:
        cursor.execute(
            """
            SELECT integration.id, integration.business_id, integration.provider,
                   integration.status, integration.display_name, integration.auth_ref,
                   integration.config_json, integration.limits_json,
                   integration.connected_by_user_id, integration.created_at, integration.updated_at,
                   account.id AS auth_account_id,
                   account.is_active AS auth_is_active,
                   account.last_error AS auth_last_error
            FROM agent_integrations integration
            LEFT JOIN externalbusinessaccounts account
              ON account.id = integration.auth_ref
             AND account.business_id = integration.business_id
            WHERE integration.business_id = %s
            ORDER BY integration.updated_at DESC, integration.created_at DESC
            LIMIT 100
            """,
            (business_id,),
        )
        integrations = [dict(row) for row in (cursor.fetchall() or [])]
    except Exception:
        integrations = []
    return integrations + _load_google_sheets_oauth_integrations(cursor, business_id, integrations)


def _load_google_sheets_oauth_integrations(
    cursor: Any,
    business_id: str,
    existing_integrations: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    existing_google_auth_refs = {
        str(item.get("auth_ref") or "").strip()
        for item in existing_integrations
        if str(item.get("provider") or "").strip() == "google_sheets" and str(item.get("auth_ref") or "").strip()
    }
    try:
        cursor.execute(
            """
            SELECT id, business_id, source, display_name
            FROM externalbusinessaccounts
            WHERE business_id = %s
              AND is_active = TRUE
              AND source IN ('google_sheets', 'google_business')
            ORDER BY updated_at DESC
            LIMIT 10
            """,
            (business_id,),
        )
        rows = cursor.fetchall() or []
    except Exception:
        return []
    result: List[Dict[str, Any]] = []
    for row in rows:
        item = dict(row)
        account_id = str(item.get("id") or "").strip()
        if not account_id or account_id in existing_google_auth_refs:
            continue
        source = str(item.get("source") or "").strip()
        if source not in GOOGLE_SHEETS_EXTERNAL_ACCOUNT_SOURCES:
            continue
        result.append(
            {
                "id": account_id,
                "business_id": str(item.get("business_id") or business_id),
                "provider": "google_sheets",
                "status": "active",
                "display_name": str(item.get("display_name") or "Google-доступ"),
                "auth_ref": account_id,
                "config_json": "{}",
                "limits_json": "{}",
                "inventory_source": "external_business_account",
            }
        )
    return result
