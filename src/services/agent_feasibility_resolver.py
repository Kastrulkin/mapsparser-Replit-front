from __future__ import annotations

from typing import Any, Dict, List

from services.agent_provider_registry import CAPABILITY_PROVIDER_MAP, INTEGRATION_PROVIDER_CATALOG
from services.openclaw_capability_catalog import get_openclaw_capability_catalog, openclaw_actions_for_capability


NATIVE_CONNECTORS = {"localos_finance", "localos_communications", "business_profile"}
FORBIDDEN_TERMS = [
    "роскосмос",
    "rocosmos",
    "roscosmos",
    "чужим компьютер",
    "чужие компьютер",
    "закрытую систему",
    "private system",
    "credential",
    "парол",
    "unauthorized",
]


def resolve_agent_feasibility(
    description: str = "",
    required_capabilities: List[str] | None = None,
    required_bindings: List[Dict[str, Any]] | None = None,
    connected_integrations: List[Dict[str, Any]] | None = None,
    openclaw_catalog: Dict[str, Any] | None = None,
    subscription: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    capabilities = _clean_list(required_capabilities or [])
    bindings = [dict(item) for item in (required_bindings or []) if isinstance(item, dict)]
    integrations = [dict(item) for item in (connected_integrations or []) if isinstance(item, dict)]
    catalog = openclaw_catalog or get_openclaw_capability_catalog()
    subscription_result = _subscription_result(subscription or {})
    forbidden = _forbidden_items(description)
    unsupported = _unsupported_capabilities(capabilities, catalog)
    binding_items = [_binding_item(binding, integrations) for binding in bindings]
    missing = [item for item in binding_items if item.get("status") == "missing"]
    choices = [item for item in binding_items if item.get("status") == "needs_choice"]
    ready = [item for item in binding_items if item.get("status") == "ready"]
    capability_items = [_capability_item(capability, catalog) for capability in capabilities]

    status = "ready"
    next_action = "Agent can be compiled and activated after validation."
    if forbidden:
        status = "forbidden"
        next_action = "Reject the request and explain the LocalOS policy boundary."
    elif unsupported:
        status = "unsupported"
        next_action = "Explain that no approved OpenClaw/LocalOS provider path exists."
    elif subscription_result.get("status") != "ready":
        status = str(subscription_result.get("status") or "needs_payment")
        next_action = str(subscription_result.get("next_action") or "Resolve subscription or credit limits.")
    elif choices:
        status = "needs_choice"
        next_action = "Ask the user which existing connection to use."
    elif missing:
        status = "needs_connection"
        next_action = "Ask the user to connect the missing services before activation."

    return {
        "schema": "localos_agent_feasibility_v1",
        "status": status,
        "ready": status == "ready",
        "next_action": next_action,
        "capabilities": capability_items,
        "bindings": binding_items,
        "ready_bindings": ready,
        "missing_connections": missing,
        "connection_choices": choices,
        "unsupported": unsupported,
        "forbidden": forbidden,
        "subscription": subscription_result,
        "catalog_source": str(catalog.get("source") or ""),
    }


def _clean_list(values: List[str]) -> List[str]:
    result: List[str] = []
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in result:
            result.append(clean)
    return result


def _forbidden_items(description: str) -> List[Dict[str, str]]:
    lowered = str(description or "").lower()
    result = []
    for term in FORBIDDEN_TERMS:
        if term in lowered:
            result.append(
                {
                    "term": term,
                    "reason": "No approved LocalOS/OpenClaw provider path for unsafe or unauthorized external system access.",
                }
            )
    return result[:3]


def _unsupported_capabilities(capabilities: List[str], catalog: Dict[str, Any]) -> List[Dict[str, str]]:
    result = []
    for capability in capabilities:
        if capability in CAPABILITY_PROVIDER_MAP:
            continue
        if openclaw_actions_for_capability(catalog, capability):
            continue
        result.append(
            {
                "capability": capability,
                "reason": "Capability is not mapped to an approved LocalOS provider or OpenClaw action.",
            }
        )
    return result


def _capability_item(capability: str, catalog: Dict[str, Any]) -> Dict[str, Any]:
    openclaw_actions = openclaw_actions_for_capability(catalog, capability)
    provider_candidates = [dict(item) for item in CAPABILITY_PROVIDER_MAP.get(capability, [])]
    return {
        "capability": capability,
        "status": "supported" if provider_candidates or openclaw_actions else "unsupported",
        "provider_candidates": provider_candidates,
        "openclaw_actions": openclaw_actions,
    }


def _binding_item(binding: Dict[str, Any], integrations: List[Dict[str, Any]]) -> Dict[str, Any]:
    provider = str(binding.get("provider") or "").strip()
    key = str(binding.get("key") or provider or "binding")
    required_config = [str(value) for value in binding.get("required_config", []) if str(value or "").strip()]
    if provider in NATIVE_CONNECTORS:
        return _base_binding_item(binding, key, provider, "ready", [], [], "native_localos")
    matching = [
        integration
        for integration in integrations
        if str(integration.get("provider") or "").strip() == provider
        and str(integration.get("status") or "active").strip() in {"active", "connected", "ready"}
    ]
    ready_integrations = [
        integration
        for integration in matching
        if not _missing_config(required_config, _integration_config(integration))
    ]
    if len(ready_integrations) > 1:
        return _base_binding_item(binding, key, provider, "needs_choice", [], ready_integrations, "multiple_connections")
    if len(ready_integrations) == 1:
        return _base_binding_item(binding, key, provider, "ready", [], ready_integrations, "agent_integration")
    missing_config = required_config
    if matching:
        missing_config = _missing_config(required_config, _integration_config(matching[0]))
    return _base_binding_item(binding, key, provider, "missing", missing_config, matching, "missing_connection")


def _base_binding_item(
    binding: Dict[str, Any],
    key: str,
    provider: str,
    status: str,
    missing_config: List[str],
    integrations: List[Dict[str, Any]],
    resolution: str,
) -> Dict[str, Any]:
    catalog_item = INTEGRATION_PROVIDER_CATALOG.get(provider, {})
    return {
        "key": key,
        "provider": provider,
        "provider_title": str(catalog_item.get("title") or provider),
        "capability": str(binding.get("capability") or ""),
        "direction": str(binding.get("direction") or ""),
        "status": status,
        "resolution": resolution,
        "required_config": [str(value) for value in binding.get("required_config", []) if str(value or "").strip()],
        "missing_config": missing_config,
        "connection_count": len(integrations),
        "connections": [_connection_summary(item) for item in integrations],
    }


def _integration_config(integration: Dict[str, Any]) -> Dict[str, Any]:
    config = integration.get("config")
    if isinstance(config, dict):
        return config
    config_json = integration.get("config_json")
    if isinstance(config_json, dict):
        return config_json
    return {}


def _missing_config(required_config: List[str], config: Dict[str, Any]) -> List[str]:
    return [key for key in required_config if not str(config.get(key) or "").strip()]


def _connection_summary(integration: Dict[str, Any]) -> Dict[str, str]:
    return {
        "id": str(integration.get("id") or ""),
        "display_name": str(integration.get("display_name") or integration.get("provider") or ""),
        "provider": str(integration.get("provider") or ""),
    }


def _subscription_result(subscription: Dict[str, Any]) -> Dict[str, Any]:
    if not subscription:
        return {"status": "ready", "next_action": ""}
    if subscription.get("blocked"):
        return {"status": "needs_payment", "next_action": "Subscription is blocked."}
    credits = subscription.get("credits_available")
    estimated = subscription.get("estimated_credits")
    if isinstance(credits, (int, float)) and isinstance(estimated, (int, float)) and credits < estimated:
        return {"status": "needs_payment", "next_action": "Not enough credits for this agent."}
    return {"status": "ready", "next_action": ""}
