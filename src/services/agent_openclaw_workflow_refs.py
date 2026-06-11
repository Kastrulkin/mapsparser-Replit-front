from __future__ import annotations

from typing import Any, Dict, List

from services.openclaw_capability_catalog import get_openclaw_capability_catalog, openclaw_actions_for_capability


def annotate_steps_with_openclaw_action_refs(
    steps: List[Dict[str, Any]],
    catalog: Dict[str, Any] | None = None,
) -> List[Dict[str, Any]]:
    openclaw_catalog = catalog or get_openclaw_capability_catalog()
    result: List[Dict[str, Any]] = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        annotated = dict(step)
        capability = str(annotated.get("capability") or "").strip()
        if annotated.get("type") == "capability" and capability and not annotated.get("provider_action_ref"):
            action = _preferred_openclaw_action(openclaw_catalog, capability)
            if action:
                annotated["provider"] = "openclaw"
                annotated["provider_action_ref"] = str(action.get("openclaw_action_ref") or "")
                annotated["provider_policy"] = "localos_envelope"
                annotated["provider_risk_class"] = str(action.get("risk_class") or "")
                annotated["provider_approval_class"] = str(action.get("approval_class") or "none")
        result.append(annotated)
    return result


def provider_action_matches_capability(provider_action_ref: str, capability: str, catalog: Dict[str, Any] | None = None) -> bool:
    action_ref = str(provider_action_ref or "").strip()
    capability_key = str(capability or "").strip()
    if not action_ref or not capability_key:
        return False
    for action in openclaw_actions_for_capability(catalog or get_openclaw_capability_catalog(), capability_key):
        if str(action.get("openclaw_action_ref") or "").strip() == action_ref:
            return True
    return False


def _preferred_openclaw_action(catalog: Dict[str, Any], capability: str) -> Dict[str, Any]:
    actions = [
        action
        for action in openclaw_actions_for_capability(catalog, capability)
        if str(action.get("status") or "available") == "available"
    ]
    if not actions:
        return {}
    no_side_effect = [action for action in actions if str(action.get("side_effect") or "") == "none"]
    if no_side_effect:
        return dict(no_side_effect[0])
    return dict(actions[0])
