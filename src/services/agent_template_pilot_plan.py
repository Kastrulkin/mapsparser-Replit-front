from typing import Any, Dict, Iterable, List


PREVIEW_RUNS_PER_TEMPLATE = 10
PRODUCTION_RUNS_PER_TEMPLATE = 5
MAX_CREDITS_PER_PRODUCTION_RUN = 2
BUFFER_CREDITS_PER_BUSINESS = 4
REQUIRED_PILOT_BUSINESSES = 3
REQUIRED_FIRST_WAVE_TEMPLATES = 6


def build_agent_template_pilot_plan(
    template_keys: Iterable[str],
    businesses: Iterable[Dict[str, Any]],
) -> Dict[str, Any]:
    templates = _unique_non_empty(template_keys, "template_key")
    if len(templates) != REQUIRED_FIRST_WAVE_TEMPLATES:
        raise ValueError(f"exactly_{REQUIRED_FIRST_WAVE_TEMPLATES}_first_wave_templates_required")
    business_rows = list(businesses)
    if len(business_rows) != REQUIRED_PILOT_BUSINESSES:
        raise ValueError(f"exactly_{REQUIRED_PILOT_BUSINESSES}_pilot_businesses_required")
    cohort = _normalize_businesses(business_rows)

    template_plans: List[Dict[str, Any]] = []
    business_totals = {
        business["business_key"]: {
            **business,
            "preview_runs": 0,
            "production_runs": 0,
            "base_credit_limit": 0,
            "buffer_credit_limit": BUFFER_CREDITS_PER_BUSINESS,
            "credit_limit": BUFFER_CREDITS_PER_BUSINESS,
        }
        for business in cohort
    }

    for template_index, template_key in enumerate(templates):
        preview_counts = _rotate((4, 3, 3), template_index)
        production_counts = _rotate((2, 2, 1), template_index)
        allocations = []
        for business_index, business in enumerate(cohort):
            preview_runs = preview_counts[business_index]
            production_runs = production_counts[business_index]
            max_credits = production_runs * MAX_CREDITS_PER_PRODUCTION_RUN
            totals = business_totals[business["business_key"]]
            totals["preview_runs"] += preview_runs
            totals["production_runs"] += production_runs
            totals["base_credit_limit"] += max_credits
            totals["credit_limit"] += max_credits
            allocations.append(
                {
                    "business_key": business["business_key"],
                    "business_id": business["business_id"],
                    "business_name": business["business_name"],
                    "preview_runs": preview_runs,
                    "production_runs": production_runs,
                    "max_credits": max_credits,
                    "genuine_feedback_required": True,
                }
            )
        template_plans.append(
            {
                "template_key": template_key,
                "preview_runs": sum(item["preview_runs"] for item in allocations),
                "production_runs": sum(item["production_runs"] for item in allocations),
                "max_credits": sum(item["max_credits"] for item in allocations),
                "allocations": allocations,
            }
        )

    totals = list(business_totals.values())
    missing_business_ids = [
        item["business_key"] for item in totals if not item["business_id"]
    ]
    funding_groups, missing_funding_data = _build_funding_groups(totals)
    top_up_required = sum(item["top_up_required"] for item in funding_groups)
    if missing_business_ids:
        status = "awaiting_business_ids"
    elif missing_funding_data:
        status = "awaiting_funding_data"
    elif top_up_required:
        status = "funding_required"
    else:
        status = "ready_for_authorization"
    return {
        "schema": "localos_agent_template_pilot_plan_v1",
        "read_only": True,
        "execution_authorized": False,
        "status": status,
        "required_authorization": (
            "Explicit approval is required before cohort changes, credit top-ups, "
            "production runs, or any external action."
        ),
        "limits": {
            "preview_runs_per_template": PREVIEW_RUNS_PER_TEMPLATE,
            "production_runs_per_template": PRODUCTION_RUNS_PER_TEMPLATE,
            "max_credits_per_production_run": MAX_CREDITS_PER_PRODUCTION_RUN,
            "buffer_credits_per_business": BUFFER_CREDITS_PER_BUSINESS,
        },
        "templates": template_plans,
        "businesses": totals,
        "funding_groups": funding_groups,
        "missing_business_ids": missing_business_ids,
        "missing_funding_data": missing_funding_data,
        "totals": {
            "templates": len(template_plans),
            "preview_runs": sum(item["preview_runs"] for item in template_plans),
            "production_runs": sum(item["production_runs"] for item in template_plans),
            "base_credit_limit": sum(item["base_credit_limit"] for item in totals),
            "buffer_credit_limit": sum(item["buffer_credit_limit"] for item in totals),
            "credit_limit": sum(item["credit_limit"] for item in totals),
            "top_up_required": top_up_required,
        },
    }


def _normalize_businesses(businesses: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    normalized = []
    seen = set()
    for business in businesses:
        if not isinstance(business, dict):
            raise ValueError("pilot_business_must_be_an_object")
        business_key = str(business.get("business_key") or "").strip()
        business_name = str(business.get("business_name") or "").strip()
        business_id = str(business.get("business_id") or "").strip()
        owner_id = str(business.get("owner_id") or "").strip()
        available_credits = _optional_nonnegative_int(business.get("available_credits"))
        if not business_key or not business_name:
            raise ValueError("pilot_business_key_and_name_required")
        if business_key in seen:
            raise ValueError("duplicate_pilot_business_key")
        seen.add(business_key)
        normalized.append(
            {
                "business_key": business_key,
                "business_id": business_id,
                "business_name": business_name,
                "owner_id": owner_id,
                "available_credits": available_credits,
            }
        )
    return normalized


def _build_funding_groups(
    businesses: Iterable[Dict[str, Any]],
) -> tuple[List[Dict[str, Any]], List[str]]:
    groups: Dict[str, Dict[str, Any]] = {}
    missing = []
    for business in businesses:
        business_key = business["business_key"]
        owner_id = business.get("owner_id")
        available_credits = business.get("available_credits")
        if not owner_id or available_credits is None:
            missing.append(business_key)
            continue
        group = groups.setdefault(
            owner_id,
            {
                "owner_id": owner_id,
                "business_keys": [],
                "available_credits": available_credits,
                "planned_credit_limit": 0,
            },
        )
        if group["available_credits"] != available_credits:
            raise ValueError("inconsistent_owner_available_credits")
        group["business_keys"].append(business_key)
        group["planned_credit_limit"] += business["credit_limit"]
    normalized = []
    for group in groups.values():
        top_up = max(group["planned_credit_limit"] - group["available_credits"], 0)
        normalized.append(
            {
                **group,
                "top_up_required": top_up,
                "status": "ready" if top_up == 0 else "top_up_required",
            }
        )
    return normalized, missing


def _optional_nonnegative_int(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError("available_credits_must_be_a_nonnegative_integer")
    if parsed < 0:
        raise ValueError("available_credits_must_be_a_nonnegative_integer")
    return parsed


def _unique_non_empty(values: Iterable[str], label: str) -> List[str]:
    normalized = []
    seen = set()
    for value in values:
        item = str(value or "").strip()
        if not item:
            raise ValueError(f"{label}_required")
        if item in seen:
            raise ValueError(f"duplicate_{label}")
        seen.add(item)
        normalized.append(item)
    if not normalized:
        raise ValueError(f"at_least_one_{label}_required")
    return normalized


def _rotate(values: tuple[int, ...], offset: int) -> tuple[int, ...]:
    normalized_offset = offset % len(values)
    return values[normalized_offset:] + values[:normalized_offset]
