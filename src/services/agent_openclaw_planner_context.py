from __future__ import annotations

from typing import Any, Dict, List


FORBIDDEN_ACTION_CLASSES = [
    "credential_extraction",
    "unauthorized_external_system_access",
    "cross_business_data_access",
    "autonomous_external_publish",
    "autonomous_external_send",
    "autonomous_payment",
    "destructive_action_without_approval",
    "subscription_or_billing_bypass",
]


APPROVAL_REQUIRED_ACTION_CLASSES = [
    "external_send",
    "external_publish",
    "external_write",
    "payment",
    "destructive_change",
    "mass_operation",
]


def build_openclaw_planner_context(
    *,
    description: str,
    category: str,
    preview: Dict[str, Any],
    business_id: str = "",
    user_id: str = "",
) -> Dict[str, Any]:
    feasibility = preview.get("feasibility") if isinstance(preview.get("feasibility"), dict) else {}
    return {
        "schema": "localos_openclaw_planner_context_v1",
        "purpose": "clarify_and_propose_workflow_inside_localos_policy_envelope",
        "task": str(description or "").strip(),
        "category": str(category or "custom").strip() or "custom",
        "business_scope": {
            "business_id": str(business_id or "").strip(),
            "user_id": str(user_id or "").strip(),
            "tenant_boundary": "single_business",
            "cross_business_access_allowed": False,
        },
        "allowed_capabilities": _clean_list(preview.get("capability_allowlist")),
        "required_bindings": _bindings(preview),
        "connection_answer_bindings": preview.get("connection_answer_bindings") if isinstance(preview.get("connection_answer_bindings"), dict) else {},
        "connection_state": _connection_state(feasibility),
        "forbidden_action_classes": list(FORBIDDEN_ACTION_CLASSES),
        "approval_required_action_classes": list(APPROVAL_REQUIRED_ACTION_CLASSES),
        "billing": {
            "meter_creation": True,
            "meter_runtime_model_calls": True,
            "meter_provider_actions": True,
            "cost_preview": preview.get("cost_preview") if isinstance(preview.get("cost_preview"), dict) else {},
        },
        "output_contract": {
            "format": "json_only",
            "allowed_result": "workflow_draft_or_clarifying_questions",
            "must_not_execute_user_task": True,
            "must_not_call_tools_directly": True,
            "compiled_workflow_owner": "localos",
        },
        "feasibility_status": str(feasibility.get("status") or "unknown"),
        "next_action": str(feasibility.get("next_action") or ""),
    }


def _bindings(preview: Dict[str, Any]) -> List[Dict[str, Any]]:
    raw_bindings = preview.get("required_integration_bindings")
    if not isinstance(raw_bindings, list):
        return []
    result = []
    for item in raw_bindings:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "key": str(item.get("key") or ""),
                "provider": str(item.get("provider") or ""),
                "capability": str(item.get("capability") or ""),
                "direction": str(item.get("direction") or ""),
                "required_config": _clean_list(item.get("required_config")),
            }
        )
    return result


def _connection_state(feasibility: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "ready_bindings": _binding_state_list(feasibility.get("ready_bindings")),
        "missing_connections": _binding_state_list(feasibility.get("missing_connections")),
        "connection_choices": _binding_state_list(feasibility.get("connection_choices")),
        "unsupported": _unsupported_list(feasibility.get("unsupported")),
        "forbidden": _unsupported_list(feasibility.get("forbidden")),
    }


def _binding_state_list(values: Any) -> List[Dict[str, Any]]:
    if not isinstance(values, list):
        return []
    result = []
    for item in values:
        if not isinstance(item, dict):
            continue
        result.append(
            {
                "key": str(item.get("key") or ""),
                "provider": str(item.get("provider") or ""),
                "provider_title": str(item.get("provider_title") or item.get("provider") or ""),
                "status": str(item.get("status") or ""),
                "connection_count": item.get("connection_count") if isinstance(item.get("connection_count"), int) else 0,
                "missing_config": _clean_list(item.get("missing_config")),
            }
        )
    return result


def _unsupported_list(values: Any) -> List[Dict[str, str]]:
    if not isinstance(values, list):
        return []
    result = []
    for item in values:
        if not isinstance(item, dict):
            continue
        result.append({str(key): str(value) for key, value in item.items()})
    return result


def _clean_list(values: Any) -> List[str]:
    if not isinstance(values, list):
        return []
    result = []
    for value in values:
        clean = str(value or "").strip()
        if clean and clean not in result:
            result.append(clean)
    return result
