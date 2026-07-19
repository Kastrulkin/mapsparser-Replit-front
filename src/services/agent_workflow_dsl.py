from __future__ import annotations

from typing import Any, Dict, List

from services.agent_openclaw_workflow_refs import provider_action_matches_capability


COMPILED_WORKFLOW_DSL_SCHEMA = {
    "schema": "localos_agent_workflow_dsl_v1",
    "required_fields": [
        "goal",
        "trigger",
        "steps",
        "capability_allowlist",
        "approval_policy",
        "required_integration_bindings",
        "limits",
        "output_schema",
    ],
    "step_types": ["artifact", "capability", "approval"],
    "side_effect_capability_fields": ["requires_approval", "required_approval_type"],
}


WRITE_CAPABILITY_MARKERS = [
    ".create",
    ".send",
    ".publish",
    ".settle",
    ".reserve",
    "append_row",
    "send_",
]

SAFE_INTERNAL_DRAFT_CAPABILITIES = {"content_plan.item.create_draft"}


def build_workflow_dsl_document(version_payload: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    compiled_process = metadata.get("compiled_process") if isinstance(metadata.get("compiled_process"), dict) else {}
    snapshot_dsl = _snapshot_dsl(metadata)
    required_bindings = (
        version_payload.get("required_integration_bindings")
        if isinstance(version_payload.get("required_integration_bindings"), list)
        else metadata.get("required_integration_bindings")
        if isinstance(metadata.get("required_integration_bindings"), list)
        else snapshot_dsl.get("required_integration_bindings")
        if isinstance(snapshot_dsl.get("required_integration_bindings"), list)
        else []
    )
    return {
        "schema": COMPILED_WORKFLOW_DSL_SCHEMA["schema"],
        "compiled_process_schema": str(compiled_process.get("schema") or "compiled_agent_workflow_v1"),
        "goal": str(version_payload.get("goal") or "").strip(),
        "trigger": str(version_payload.get("trigger") or snapshot_dsl.get("trigger") or "manual.run").strip() or "manual.run",
        "mode": str(version_payload.get("mode") or snapshot_dsl.get("mode") or "draft").strip() or "draft",
        "inputs_schema": (
            version_payload.get("inputs_schema")
            if isinstance(version_payload.get("inputs_schema"), dict)
            else snapshot_dsl.get("inputs_schema")
            if isinstance(snapshot_dsl.get("inputs_schema"), dict)
            else {}
        ),
        "steps": version_payload.get("steps") if isinstance(version_payload.get("steps"), list) else [],
        "capability_allowlist": _clean_string_list(version_payload.get("capability_allowlist")),
        "approval_policy": version_payload.get("approval_policy") if isinstance(version_payload.get("approval_policy"), dict) else {},
        "required_integration_bindings": required_bindings,
        "limits": (
            version_payload.get("limits")
            if isinstance(version_payload.get("limits"), dict)
            else snapshot_dsl.get("limits")
            if isinstance(snapshot_dsl.get("limits"), dict)
            else {}
        ),
        "output_schema": version_payload.get("output_schema") if isinstance(version_payload.get("output_schema"), dict) else {},
        "runtime": {
            "truth": str(compiled_process.get("runtime_truth") or "agent_blueprint_versions.steps_json"),
            "llm_required": bool((metadata.get("compiler_contract") or {}).get("runtime_llm_required")) if isinstance(metadata.get("compiler_contract"), dict) else False,
        },
    }


def validate_workflow_dsl_document(document: Dict[str, Any]) -> Dict[str, Any]:
    errors: List[Dict[str, str]] = []
    warnings: List[Dict[str, str]] = []
    if document.get("schema") != COMPILED_WORKFLOW_DSL_SCHEMA["schema"]:
        errors.append(_issue("schema", "DSL schema is missing or unsupported."))
    for field in COMPILED_WORKFLOW_DSL_SCHEMA["required_fields"]:
        if not _present(document.get(field)):
            errors.append(_issue(field, "Required workflow field is missing."))

    steps = document.get("steps") if isinstance(document.get("steps"), list) else []
    capability_allowlist = set(_clean_string_list(document.get("capability_allowlist")))
    approval_policy = document.get("approval_policy") if isinstance(document.get("approval_policy"), dict) else {}
    required_bindings = document.get("required_integration_bindings") if isinstance(document.get("required_integration_bindings"), list) else []

    step_keys: set[str] = set()
    approval_types: set[str] = set()
    capabilities_in_steps: set[str] = set()
    for index, step in enumerate(steps):
        if not isinstance(step, dict):
            errors.append(_issue(f"steps[{index}]", "Step must be an object."))
            continue
        key = str(step.get("key") or "").strip()
        step_type = str(step.get("type") or "").strip()
        if not key:
            errors.append(_issue(f"steps[{index}].key", "Step key is required."))
        elif key in step_keys:
            errors.append(_issue(f"steps[{index}].key", "Step key must be unique."))
        else:
            step_keys.add(key)
        if step_type not in COMPILED_WORKFLOW_DSL_SCHEMA["step_types"]:
            errors.append(_issue(f"steps[{index}].type", "Step type is not allowed by DSL."))
        if step_type == "approval":
            approval_type = str(step.get("approval_type") or "").strip()
            if not approval_type:
                errors.append(_issue(f"steps[{index}].approval_type", "Approval step must declare approval_type."))
            else:
                approval_types.add(approval_type)
        if step_type == "capability":
            capability = str(step.get("capability") or "").strip()
            if not capability:
                errors.append(_issue(f"steps[{index}].capability", "Capability step must declare capability."))
                continue
            capabilities_in_steps.add(capability)
            if capability not in capability_allowlist:
                errors.append(_issue(f"steps[{index}].capability", "Capability is not present in capability_allowlist."))
            provider_action_ref = str(step.get("provider_action_ref") or "").strip()
            if provider_action_ref:
                provider = str(step.get("provider") or "").strip()
                if provider and provider != "openclaw":
                    errors.append(_issue(f"steps[{index}].provider", "provider_action_ref is supported only for OpenClaw actions in v1."))
                if not provider_action_matches_capability(provider_action_ref, capability):
                    errors.append(_issue(f"steps[{index}].provider_action_ref", "OpenClaw action ref does not match step capability."))
            if _looks_like_write_capability(capability) and capability not in SAFE_INTERNAL_DRAFT_CAPABILITIES:
                if step.get("requires_approval") is not True:
                    errors.append(_issue(f"steps[{index}].requires_approval", "Write capability must require approval."))
                required_approval_type = str(step.get("required_approval_type") or "").strip()
                if not required_approval_type:
                    errors.append(_issue(f"steps[{index}].required_approval_type", "Write capability must name approval gate."))
                elif required_approval_type not in approval_types and required_approval_type not in approval_policy:
                    errors.append(_issue(f"steps[{index}].required_approval_type", "Approval gate is not declared in workflow."))

    if _goal_requires_internal_summary(str(document.get("goal") or "")):
        for index, step in enumerate(steps):
            if not isinstance(step, dict) or str(step.get("artifact_type") or "").strip() != "agent_output_draft":
                continue
            payload = step.get("payload") if isinstance(step.get("payload"), dict) else {}
            category = str(payload.get("category") or "").strip().lower()
            output_format = str(payload.get("format") or "").strip().lower()
            if category == "reviews" or "reply_draft" in output_format:
                errors.append(
                    _issue(
                        f"steps[{index}].payload.format",
                        "Internal business summary cannot use the review-reply output renderer.",
                    )
                )

    for capability in capability_allowlist:
        if capability and capability not in capabilities_in_steps:
            warnings.append(_issue("capability_allowlist", f"Capability {capability} is allowed but not used by a step."))

    for index, binding in enumerate(required_bindings):
        if not isinstance(binding, dict):
            errors.append(_issue(f"required_integration_bindings[{index}]", "Binding must be an object."))
            continue
        if not str(binding.get("key") or "").strip():
            errors.append(_issue(f"required_integration_bindings[{index}].key", "Binding key is required."))
        if not str(binding.get("provider") or "").strip():
            errors.append(_issue(f"required_integration_bindings[{index}].provider", "Binding provider is required."))
        binding_capability = str(binding.get("capability") or "").strip()
        if binding_capability and binding_capability not in capability_allowlist:
            errors.append(_issue(f"required_integration_bindings[{index}].capability", "Binding capability is not allowed by workflow."))

    limits = document.get("limits") if isinstance(document.get("limits"), dict) else {}
    if _contains_write_capability(capability_allowlist):
        if limits.get("autonomous_external_write_allowed") is True or limits.get("autonomous_localos_write_allowed") is True:
            errors.append(_issue("limits", "Compiled workflow cannot enable autonomous writes in v1."))

    return {
        "status": "valid" if not errors else "invalid",
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "schema": COMPILED_WORKFLOW_DSL_SCHEMA["schema"],
    }


def _present(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        return bool(value.strip())
    if isinstance(value, (list, dict)):
        return True
    return True


def _snapshot_dsl(metadata: Dict[str, Any]) -> Dict[str, Any]:
    candidate = metadata.get("compiled_artifact_candidate") if isinstance(metadata.get("compiled_artifact_candidate"), dict) else {}
    dsl = candidate.get("dsl") if isinstance(candidate.get("dsl"), dict) else {}
    return dsl


def _clean_string_list(value: Any) -> List[str]:
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        cleaned = str(item or "").strip()
        if cleaned:
            result.append(cleaned)
    return result


def _looks_like_write_capability(capability: str) -> bool:
    return any(marker in capability for marker in WRITE_CAPABILITY_MARKERS)


def _contains_write_capability(capabilities: set[str]) -> bool:
    return any(
        _looks_like_write_capability(capability) and capability not in SAFE_INTERNAL_DRAFT_CAPABILITIES
        for capability in capabilities
    )


def _goal_requires_internal_summary(goal: str) -> bool:
    lowered = goal.lower()
    summary_markers = [
        "внутренняя сводка",
        "внутреннюю сводку",
        "краткая сводка",
        "краткую сводку",
        "сводка бизнеса",
        "сводка профиля",
    ]
    reply_markers = ["ответ на отзыв", "ответы на отзывы", "черновик ответа", "черновики ответов"]
    return any(marker in lowered for marker in summary_markers) and not any(marker in lowered for marker in reply_markers)


def _issue(field: str, message: str) -> Dict[str, str]:
    return {"field": field, "message": message}
