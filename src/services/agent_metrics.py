from __future__ import annotations

from typing import Any, Dict, List

from services.agent_builder_billing import build_agent_billing_estimate_items


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

    cost_tokens = _aggregate_cost_tokens_from_runs(runs, metadata)
    billing_breakdown = _build_billing_breakdown(runs, metadata, cost_tokens)
    unified_billing_ledger = _build_unified_billing_ledger(runs, metadata)
    cost_tokens["breakdown"] = billing_breakdown["items"]
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
        "cost_tokens": cost_tokens,
        "billing_breakdown": billing_breakdown,
        "unified_billing_ledger": unified_billing_ledger,
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
        "agent_creation_charged": _safe_int(
            ((metadata.get("billing") or {}) if isinstance(metadata.get("billing"), dict) else {}).get("credits_charged")
            or ((metadata.get("billing") or {}) if isinstance(metadata.get("billing"), dict) else {}).get("actual_credits")
        ),
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


def _build_billing_breakdown(runs: List[Dict[str, Any]], metadata: Dict[str, Any], totals: Dict[str, Any]) -> Dict[str, Any]:
    billing = metadata.get("billing") if isinstance(metadata.get("billing"), dict) else {}
    creation_charged = _safe_int(billing.get("credits_charged") or billing.get("actual_credits"))
    creation_estimated = _safe_int(billing.get("estimated_credits"))
    preview_runs = 0
    production_runs = 0
    external_actions = 0
    external_entries = 0
    external_settled_tokens = 0
    external_total_cost = 0.0
    for run in runs:
        input_json = run.get("input_json") if isinstance(run.get("input_json"), dict) else {}
        if bool(input_json.get("preview_mode")):
            preview_runs += 1
        else:
            production_runs += 1
        output = run.get("output_json") if isinstance(run.get("output_json"), dict) else {}
        observability = output.get("observability") if isinstance(output.get("observability"), dict) else {}
        ledger = observability.get("billing_ledger") if isinstance(observability.get("billing_ledger"), dict) else {}
        actions = ledger.get("actions") if isinstance(ledger.get("actions"), list) else []
        entries = ledger.get("entries") if isinstance(ledger.get("entries"), list) else []
        external_actions += len(actions)
        external_entries += len(entries)
        for item in actions:
            if not isinstance(item, dict):
                continue
            summary = item.get("billing_summary") if isinstance(item.get("billing_summary"), dict) else {}
            external_settled_tokens += _safe_int(summary.get("settled_tokens"))
            external_total_cost += _safe_float(summary.get("total_cost"))
        for item in entries:
            if not isinstance(item, dict):
                continue
            external_settled_tokens += _safe_int(item.get("tokens_out"))
            external_total_cost += _safe_float(item.get("cost"))
    items = [
        {
            "key": "agent_creation",
            "label": "Создание агента",
            "count": 1 if creation_charged or creation_estimated else 0,
            "estimated_credits": creation_estimated,
            "charged_credits": creation_charged,
            "status": "charged" if creation_charged else "estimate" if creation_estimated else "not_used",
        },
        {
            "key": "preview_run",
            "label": "Preview run",
            "count": preview_runs,
            "settled_tokens": 0,
            "status": "metered_after_run",
        },
        {
            "key": "production_run",
            "label": "Production run",
            "count": production_runs,
            "settled_tokens": _safe_int(totals.get("settled_tokens")),
            "total_cost": _safe_float(totals.get("total_cost")),
            "status": "metered_after_run",
        },
        {
            "key": "external_action",
            "label": "Внешние действия",
            "count": external_actions,
            "ledger_entries": external_entries,
            "settled_tokens": external_settled_tokens,
            "total_cost": round(external_total_cost, 6),
            "status": "approval_and_ledger_required",
        },
        {
            "key": "operator_chat",
            "label": "Чат оператора",
            "count": 0,
            "estimated_credits": 1,
            "status": "available_when_used",
        },
    ]
    return {
        "schema": "localos_agent_billing_breakdown_v1",
        "total_items": len(items),
        "items": items,
    }


def _build_unified_billing_ledger(runs: List[Dict[str, Any]], metadata: Dict[str, Any]) -> Dict[str, Any]:
    estimate_items = build_agent_billing_estimate_items()
    estimate_by_key = {str(item.get("key") or ""): item for item in estimate_items}
    billing = metadata.get("billing") if isinstance(metadata.get("billing"), dict) else {}
    preview_actual = _run_phase_totals(runs, preview=True)
    production_actual = _run_phase_totals(runs, preview=False)
    external_actual = _external_action_totals(runs)
    rows = [
        _ledger_row(
            estimate_by_key.get("agent_creation", {}),
            actual_credits=_safe_int(billing.get("credits_charged") or billing.get("actual_credits")),
            estimated_credits=_safe_int(billing.get("estimated_credits")) or None,
            status="charged" if _safe_int(billing.get("credits_charged") or billing.get("actual_credits")) else "estimate",
            source="agent_blueprint.metadata.billing",
            fact_ref=str(billing.get("reservation_id") or billing.get("idempotency_key") or ""),
        ),
        _ledger_row(
            estimate_by_key.get("preview_run", {}),
            count=preview_actual["count"],
            actual_tokens=preview_actual["settled_tokens"],
            actual_cost=preview_actual["total_cost"],
            status="settled" if preview_actual["settled_tokens"] or preview_actual["count"] else "estimate",
            source="agent_runs.preview.observability",
        ),
        _ledger_row(
            estimate_by_key.get("production_run", {}),
            count=production_actual["count"],
            actual_tokens=production_actual["settled_tokens"],
            actual_cost=production_actual["total_cost"],
            status="settled" if production_actual["settled_tokens"] or production_actual["count"] else "estimate",
            source="agent_runs.production.observability",
        ),
        _ledger_row(
            estimate_by_key.get("external_action", {}),
            count=external_actual["count"],
            actual_tokens=external_actual["settled_tokens"],
            actual_cost=external_actual["total_cost"],
            status="settled" if external_actual["settled_tokens"] or external_actual["count"] else "approval_required",
            source="action_orchestrator.billing_ledger",
        ),
        _ledger_row(
            estimate_by_key.get("operator_chat", {}),
            actual_credits=_safe_int(billing.get("operator_chat_credits_charged")),
            status="charged" if _safe_int(billing.get("operator_chat_credits_charged")) else "estimate",
            source="operator_chat.credit_reservation",
        ),
    ]
    actual_credits = sum(_safe_int(item.get("actual_credits")) for item in rows)
    actual_tokens = sum(_safe_int(item.get("actual_tokens")) for item in rows)
    actual_cost = round(sum(_safe_float(item.get("actual_cost")) for item in rows), 6)
    estimated_credits = sum(_safe_int(item.get("estimated_credits")) for item in rows)
    estimated_tokens = sum(_safe_int(item.get("estimated_tokens")) for item in rows)
    return {
        "schema": "localos_agent_unified_billing_ledger_v1",
        "summary": {
            "estimated_credits": estimated_credits,
            "estimated_tokens": estimated_tokens,
            "actual_credits": actual_credits,
            "actual_tokens": actual_tokens,
            "actual_cost": actual_cost,
            "has_actuals": bool(actual_credits or actual_tokens or actual_cost),
        },
        "items": rows,
    }


def _ledger_row(
    estimate: Dict[str, Any],
    *,
    count: int = 0,
    actual_credits: int = 0,
    actual_tokens: int = 0,
    actual_cost: float = 0.0,
    estimated_credits: int | None = None,
    status: str = "estimate",
    source: str = "",
    fact_ref: str = "",
) -> Dict[str, Any]:
    key = str(estimate.get("key") or "")
    return {
        "key": key,
        "label": str(estimate.get("label") or key),
        "phase": str(estimate.get("phase") or key),
        "count": count,
        "estimated_credits": _safe_int(estimate.get("estimated_credits") if estimated_credits is None else estimated_credits),
        "estimated_tokens": _safe_int(estimate.get("estimated_tokens")),
        "actual_credits": actual_credits,
        "actual_tokens": actual_tokens,
        "actual_cost": round(actual_cost, 6),
        "status": status,
        "billing_mode": str(estimate.get("billing_mode") or ""),
        "source": source,
        "fact_ref": fact_ref,
    }


def _run_phase_totals(runs: List[Dict[str, Any]], *, preview: bool) -> Dict[str, Any]:
    count = 0
    settled_tokens = 0
    total_cost = 0.0
    for run in runs:
        input_json = run.get("input_json") if isinstance(run.get("input_json"), dict) else {}
        if bool(input_json.get("preview_mode")) != preview:
            continue
        count += 1
        output = run.get("output_json") if isinstance(run.get("output_json"), dict) else {}
        observability = output.get("observability") if isinstance(output.get("observability"), dict) else {}
        cost_tokens = observability.get("cost_tokens") if isinstance(observability.get("cost_tokens"), dict) else {}
        billing_ledger = observability.get("billing_ledger") if isinstance(observability.get("billing_ledger"), dict) else {}
        billing_summary = billing_ledger.get("summary") if isinstance(billing_ledger.get("summary"), dict) else {}
        settled_tokens += max(_safe_int(cost_tokens.get("settled_tokens")) - _safe_int(billing_summary.get("settled_tokens")), 0)
        total_cost += max(_safe_float(cost_tokens.get("total_cost")) - _safe_float(billing_summary.get("total_cost")), 0.0)
    return {"count": count, "settled_tokens": settled_tokens, "total_cost": round(total_cost, 6)}


def _external_action_totals(runs: List[Dict[str, Any]]) -> Dict[str, Any]:
    count = 0
    settled_tokens = 0
    total_cost = 0.0
    for run in runs:
        output = run.get("output_json") if isinstance(run.get("output_json"), dict) else {}
        observability = output.get("observability") if isinstance(output.get("observability"), dict) else {}
        billing_ledger = observability.get("billing_ledger") if isinstance(observability.get("billing_ledger"), dict) else {}
        actions = billing_ledger.get("actions") if isinstance(billing_ledger.get("actions"), list) else []
        count += len(actions)
        for item in actions:
            if not isinstance(item, dict):
                continue
            settled_tokens += _safe_int(item.get("settled_tokens"))
            total_cost += _safe_float(item.get("total_cost"))
    return {"count": count, "settled_tokens": settled_tokens, "total_cost": round(total_cost, 6)}


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
