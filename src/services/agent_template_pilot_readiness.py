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
        preview_violations = [str(row.get("run_id") or "") for row in previews if not _preview_is_safe(row)]
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
                "duplicate_idempotency_keys": duplicate_keys,
                "run_ids": [str(row.get("run_id") or "") for row in template_rows if str(row.get("run_id") or "")],
                "ready_for_manual_accuracy_review": len(completed_production) >= 5,
                "meets_collection_minimums": bool(
                    len(safe_previews) >= 10
                    and len(completed_production) >= 5
                    and len(useful_businesses) >= 3
                    and not preview_violations
                    and not duplicate_keys
                ),
            }
        )
    return {
        "schema": "localos_agent_template_pilot_readiness_v1",
        "read_only": True,
        "templates": templates,
        "preview_violations": sum(len(item["preview_violation_run_ids"]) for item in templates),
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
    output = _output(row)
    return bool(
        output.get("provider_write_performed") is not True
        and output.get("external_dispatch_performed") is not True
        and output.get("duplicate_side_effect") is not True
    )
