from __future__ import annotations

from typing import Any, Dict, List


def build_agent_metrics_summary(
    blueprint: Dict[str, Any],
    versions: List[Dict[str, Any]],
    active_version: Dict[str, Any] | None,
    runs: List[Dict[str, Any]],
    approval_queue: List[Dict[str, Any]],
    metadata: Dict[str, Any],
) -> Dict[str, Any]:
    status_counts: Dict[str, int] = {}
    for run in runs:
        status = str(run.get("status") or "unknown").strip() or "unknown"
        status_counts[status] = status_counts.get(status, 0) + 1

    compiled_validation = metadata.get("compiled_validation") if isinstance(metadata.get("compiled_validation"), dict) else {}
    candidate = metadata.get("compiled_artifact_candidate") if isinstance(metadata.get("compiled_artifact_candidate"), dict) else {}
    validation = candidate.get("validation") if isinstance(candidate.get("validation"), dict) else compiled_validation

    return {
        "schema": "agent_metrics_summary_v1",
        "blueprint_id": str(blueprint.get("id") or ""),
        "status": str(blueprint.get("status") or "draft"),
        "compiled": {
            "candidate_status": str(candidate.get("status") or ""),
            "validation_status": str(validation.get("status") or ""),
            "validation_valid": bool(validation.get("valid")) if validation else False,
            "error_count": len(validation.get("errors") or []) if isinstance(validation.get("errors"), list) else 0,
            "warning_count": len(validation.get("warnings") or []) if isinstance(validation.get("warnings"), list) else 0,
            "runtime_llm_required": bool(candidate.get("runtime_llm_required")) if candidate else False,
        },
        "versions": {
            "total": len(versions),
            "active_version_id": str((active_version or {}).get("id") or ""),
            "active_version_number": _safe_int((active_version or {}).get("version_number")),
        },
        "runs": {
            "loaded": len(runs),
            "by_status": status_counts,
            "last_run": _last_run_summary(runs),
        },
        "approvals": {
            "pending": len(approval_queue),
            "waiting_reasons": _approval_reasons(approval_queue),
        },
        "cost_tokens": _aggregate_cost_tokens_from_runs(runs, metadata),
        "setup": {
            "required_bindings": len(metadata.get("required_integration_bindings") or []) if isinstance(metadata.get("required_integration_bindings"), list) else 0,
            "learning_events": len(metadata.get("learning_events") or []) if isinstance(metadata.get("learning_events"), list) else 0,
        },
    }


def _last_run_summary(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not runs:
        return {}
    run = runs[0]
    return {
        "id": str(run.get("id") or ""),
        "status": str(run.get("status") or ""),
        "started_at": run.get("started_at"),
        "completed_at": run.get("completed_at"),
        "error_text": str(run.get("error_text") or ""),
    }


def _approval_reasons(approval_queue: List[Dict[str, Any]]) -> List[str]:
    reasons = []
    for approval in approval_queue[:5]:
        reason = str(approval.get("reason") or approval.get("approval_type") or "").strip()
        if reason:
            reasons.append(reason)
    return reasons


def _aggregate_cost_tokens_from_runs(runs: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Dict[str, Any]:
    totals = {
        "reserved_tokens": 0,
        "settled_tokens": 0,
        "released_tokens": 0,
        "inflight_reserved_tokens": 0,
        "total_cost": 0.0,
        "agent_creation_charged": _safe_int(((metadata.get("billing") or {}) if isinstance(metadata.get("billing"), dict) else {}).get("credits_charged")),
    }
    for run in runs:
        output = run.get("output_json") if isinstance(run.get("output_json"), dict) else {}
        observability = output.get("observability") if isinstance(output.get("observability"), dict) else {}
        cost_tokens = observability.get("cost_tokens") if isinstance(observability.get("cost_tokens"), dict) else {}
        totals["reserved_tokens"] += _safe_int(cost_tokens.get("reserved_tokens"))
        totals["settled_tokens"] += _safe_int(cost_tokens.get("settled_tokens"))
        totals["released_tokens"] += _safe_int(cost_tokens.get("released_tokens"))
        totals["inflight_reserved_tokens"] += _safe_int(cost_tokens.get("inflight_reserved_tokens"))
        totals["total_cost"] += _safe_float(cost_tokens.get("total_cost"))
    totals["total_cost"] = round(totals["total_cost"], 6)
    return totals


def _safe_int(value: Any) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0


def _safe_float(value: Any) -> float:
    try:
        return float(value or 0.0)
    except Exception:
        return 0.0
