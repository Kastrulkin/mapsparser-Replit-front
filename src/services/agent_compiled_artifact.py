from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

from services.agent_workflow_dsl import build_workflow_dsl_document, validate_workflow_dsl_document


def build_compiled_artifact_candidate(version_payload: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    dsl_document = build_workflow_dsl_document(version_payload, metadata)
    validation = validate_workflow_dsl_document(dsl_document)
    return {
        "schema": "localos_compiled_artifact_candidate_v1",
        "status": "validation_passed" if validation.get("valid") else "validation_failed",
        "created_at": datetime.now(timezone.utc).isoformat(),
        "runtime_truth": dsl_document["runtime"]["truth"],
        "runtime_llm_required": dsl_document["runtime"]["llm_required"],
        "dsl": dsl_document,
        "validation": validation,
        "activation_gate": {
            "requires_validation_passed": True,
            "requires_integration_preflight_ready": True,
            "requires_manual_approval_for_writes": True,
        },
    }


def validate_compiled_artifact_candidate(version_payload: Dict[str, Any], metadata: Dict[str, Any]) -> Dict[str, Any]:
    candidate = build_compiled_artifact_candidate(version_payload, metadata)
    validation = candidate.get("validation") if isinstance(candidate.get("validation"), dict) else {}
    return {
        "ready": bool(validation.get("valid")) and candidate.get("runtime_llm_required") is False,
        "candidate": candidate,
        "validation": validation,
    }
