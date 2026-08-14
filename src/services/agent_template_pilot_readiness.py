from collections import Counter
from typing import Any, Dict, Iterable, List


def build_agent_template_pilot_readiness(rows: Iterable[Dict[str, Any]], template_keys: Iterable[str]) -> Dict[str, Any]:
    normalized_rows = [dict(row) for row in rows if isinstance(row, dict)]
    templates = []
    for template_key in template_keys:
        template_rows = [row for row in normalized_rows if str(row.get("template_key") or "") == template_key]
        previews = [row for row in template_rows if _input(row).get("preview_mode") is True]
        production = [row for row in template_rows if _input(row).get("preview_mode") is not True]
        safe_previews = [row for row in previews if _preview_is_safe(row)]
        completed_production = [row for row in production if str(row.get("status") or "") == "completed"]
        useful_businesses = {
            str(row.get("business_id") or "")
            for row in completed_production
            if str(row.get("evaluation_rating") or "") == "useful" and str(row.get("business_id") or "")
        }
        idempotency_counts = Counter(
            (
                str(row.get("business_id") or ""),
                str(row.get("blueprint_id") or ""),
                str(row.get("idempotency_key") or ""),
            )
            for row in template_rows
            if str(row.get("idempotency_key") or "")
        )
        duplicate_keys = sorted(
            f"{business_id}:{blueprint_id}:{key}"
            for (business_id, blueprint_id, key), count in idempotency_counts.items()
            if count > 1
        )
        scheduled_days = {
            str(row.get("completed_utc_date") or "")
            for row in completed_production
            if str(row.get("trigger") or "").startswith("schedule.") and str(row.get("completed_utc_date") or "")
        }
        preview_violations = [str(row.get("run_id") or "") for row in previews if _preview_has_side_effect(row)]
        failed_previews = [row for row in previews if str(row.get("status") or "") != "completed"]
        resolved_failed_previews = [
            row
            for row in failed_previews
            if _failed_preview_has_later_safe_retry(row, previews)
        ]
        resolved_failed_ids = [str(row.get("run_id") or "") for row in resolved_failed_previews]
        unresolved_failed_ids = [
            str(row.get("run_id") or "")
            for row in failed_previews
            if row not in resolved_failed_previews
        ]
        templates.append(
            {
                "template_key": template_key,
                "preview_runs": len(previews),
                "safe_preview_runs": len(safe_previews),
                "production_runs": len(production),
                "successful_production_runs": len(completed_production),
                "useful_pilot_businesses": len(useful_businesses),
                "useful_pilot_business_ids": sorted(useful_businesses),
                "scheduled_days": len(scheduled_days),
                "preview_violation_run_ids": preview_violations,
                "failed_preview_run_ids": [str(row.get("run_id") or "") for row in failed_previews],
                "resolved_failed_preview_run_ids": resolved_failed_ids,
                "unresolved_failed_preview_run_ids": unresolved_failed_ids,
                "duplicate_idempotency_keys": duplicate_keys,
                "run_ids": [str(row.get("run_id") or "") for row in template_rows if str(row.get("run_id") or "")],
                "ready_for_manual_accuracy_review": len(completed_production) >= 5,
                "meets_collection_minimums": bool(
                    len(safe_previews) >= 10
                    and len(completed_production) >= 5
                    and len(useful_businesses) >= 3
                    and not preview_violations
                    and not unresolved_failed_ids
                    and not duplicate_keys
                ),
            }
        )
    return {
        "schema": "localos_agent_template_pilot_readiness_v1",
        "read_only": True,
        "templates": templates,
        "preview_violations": sum(len(item["preview_violation_run_ids"]) for item in templates),
        "failed_previews": sum(len(item["failed_preview_run_ids"]) for item in templates),
        "resolved_failed_previews": sum(len(item["resolved_failed_preview_run_ids"]) for item in templates),
        "unresolved_failed_previews": sum(len(item["unresolved_failed_preview_run_ids"]) for item in templates),
        "duplicate_idempotency_keys": sum(len(item["duplicate_idempotency_keys"]) for item in templates),
    }


def _input(row: Dict[str, Any]) -> Dict[str, Any]:
    value = row.get("input_json")
    return value if isinstance(value, dict) else {}


def _output(row: Dict[str, Any]) -> Dict[str, Any]:
    value = row.get("output_json")
    return value if isinstance(value, dict) else {}


def _preview_is_safe(row: Dict[str, Any]) -> bool:
    if str(row.get("status") or "") != "completed":
        return False
    return not _preview_has_side_effect(row)


def _preview_has_side_effect(row: Dict[str, Any]) -> bool:
    return _contains_true_side_effect(_output(row))


def _contains_true_side_effect(value: Any) -> bool:
    side_effect_keys = {
        "provider_write_performed",
        "external_write_performed",
        "external_dispatch_performed",
        "duplicate_side_effect",
    }
    if isinstance(value, dict):
        return any(
            (key in side_effect_keys and item is True) or _contains_true_side_effect(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_true_side_effect(item) for item in value)
    return False


def _failed_preview_has_later_safe_retry(failed: Dict[str, Any], previews: List[Dict[str, Any]]) -> bool:
    failed_index = next((index for index, row in enumerate(previews) if row is failed), -1)
    if failed_index < 0:
        return False
    business_id = str(failed.get("business_id") or "")
    return any(
        str(row.get("business_id") or "") == business_id and _preview_is_safe(row)
        for row in previews[failed_index + 1 :]
    )
