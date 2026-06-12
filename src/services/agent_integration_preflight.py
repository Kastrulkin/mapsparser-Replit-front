from __future__ import annotations

import json
from typing import Any, Dict, List


NATIVE_READY_PROVIDERS = {"localos_finance"}


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
                    "Maton.ai key is selected as the provider bridge for this binding.",
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
        resolved_config = _merge_default_config(default_config, metadata_config)
        missing_metadata_config = [key for key in required_config if not str(resolved_config.get(key) or "").strip()]
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
    for integration in active_integrations:
        config = parse_json_field(integration.get("config_json"), {})
        config = config if isinstance(config, dict) else {}
        resolved_config = _merge_default_config(default_config, config)
        missing_config = [key for key in required_config if not str(resolved_config.get(key) or "").strip()]
        if not missing_config:
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
    }


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
    candidates = [
        custom_process.get(provider),
        custom_process.get(binding_key),
    ]
    if provider == "google_sheets":
        candidates.extend([custom_process.get("google_sheets_read"), custom_process.get("google_sheets_append")])
    candidates.append(binding_integrations.get(binding_key))
    for candidate in candidates:
        if isinstance(candidate, dict):
            return candidate
    return {}


def _missing_config_summary(provider: str, missing_config: List[str]) -> str:
    if not missing_config:
        return "Connection was found, but LocalOS could not verify the required config."
    provider_label = provider or "connection"
    return f"{provider_label} connection is selected, but missing required config: {', '.join(missing_config)}."


def _load_agent_integrations(cursor: Any, business_id: str) -> List[Dict[str, Any]]:
    if not business_id:
        return []
    try:
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
        return [dict(row) for row in (cursor.fetchall() or [])]
    except Exception:
        return []
