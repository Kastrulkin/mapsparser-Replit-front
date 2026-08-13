from typing import Any, Dict


REQUIRED_FIXTURES = (
    "valid_input",
    "empty_input",
    "malformed_input",
    "missing_connection",
    "expired_oauth",
    "transient_provider_failure",
    "duplicate_idempotency_key",
    "worker_restart",
    "limit_exceeded",
)

MIN_PREVIEW_RUNS = 10
MIN_PRODUCTION_RUNS = 5
MIN_PILOT_BUSINESSES = 3
MIN_ACCURACY_SCORE = 0.90
MIN_CANARY_DAYS = 7


def evaluate_template_certification(template: Dict[str, Any], evidence: Dict[str, Any]) -> Dict[str, Any]:
    fixtures = evidence.get("fixtures") if isinstance(evidence.get("fixtures"), list) else []
    preview_runs = evidence.get("preview_runs") if isinstance(evidence.get("preview_runs"), list) else []
    production_runs = evidence.get("production_runs") if isinstance(evidence.get("production_runs"), list) else []
    pilot_feedback = evidence.get("pilot_feedback") if isinstance(evidence.get("pilot_feedback"), list) else []
    security = evidence.get("security") if isinstance(evidence.get("security"), dict) else {}
    version_pins = evidence.get("version_pins") if isinstance(evidence.get("version_pins"), dict) else {}

    fixture_status = {
        str(item.get("key") or ""): str(item.get("status") or "")
        for item in fixtures
        if isinstance(item, dict)
    }
    fixtures_passed = all(fixture_status.get(key) == "passed" for key in REQUIRED_FIXTURES)
    technical_passed = bool(
        template.get("certification_gates", {}).get("schema", {}).get("passed")
        and template.get("certification_gates", {}).get("security", {}).get("passed")
        and version_pins.get("prompt_version")
        and version_pins.get("approval_policy_hash")
    )
    security_passed = all(
        security.get(key) is True
        for key in ("prompt_injection_blocked", "approval_bypass_blocked", "sensitive_data_leak_blocked")
    )
    safe_preview_runs = [
        item
        for item in preview_runs
        if isinstance(item, dict)
        and item.get("status") == "completed"
        and item.get("provider_write_performed") is not True
        and item.get("external_dispatch_performed") is not True
        and item.get("duplicate_side_effect") is not True
    ]
    successful_production_runs = [
        item for item in production_runs if isinstance(item, dict) and item.get("status") == "completed"
    ]
    execution_passed = bool(
        fixtures_passed
        and len(safe_preview_runs) >= MIN_PREVIEW_RUNS
        and len(successful_production_runs) >= MIN_PRODUCTION_RUNS
        and evidence.get("support_export_passed") is True
        and evidence.get("rollback_test_passed") is True
    )
    golden_score = _score(evidence.get("golden_score"))
    production_accuracy = _ratio(
        len([item for item in successful_production_runs if item.get("result_correct") is True]),
        len(successful_production_runs),
    )
    useful_businesses = {
        str(item.get("business_id") or "")
        for item in pilot_feedback
        if isinstance(item, dict) and item.get("useful") is True and str(item.get("business_id") or "")
    }
    accuracy_passed = bool(
        golden_score >= MIN_ACCURACY_SCORE
        and production_accuracy >= MIN_ACCURACY_SCORE
        and len(useful_businesses) >= MIN_PILOT_BUSINESSES
    )
    production_passed = bool(
        execution_passed
        and accuracy_passed
        and _integer(evidence.get("canary_days")) >= MIN_CANARY_DAYS
        and evidence.get("canary_incident_free") is True
    )
    gates = {
        "technical": _gate(technical_passed, "Versioned DSL, policy validation, and immutable version pins"),
        "fixtures": _gate(fixtures_passed, f"{sum(fixture_status.get(key) == 'passed' for key in REQUIRED_FIXTURES)}/{len(REQUIRED_FIXTURES)} required fixtures"),
        "security": _gate(security_passed, "Prompt injection, approval bypass, and data-leak checks"),
        "execution": _gate(execution_passed, f"{len(safe_preview_runs)}/{MIN_PREVIEW_RUNS} preview; {len(successful_production_runs)}/{MIN_PRODUCTION_RUNS} production runs"),
        "accuracy": _gate(accuracy_passed, f"golden={golden_score:.2f}; production={production_accuracy:.2f}; pilots={len(useful_businesses)}/{MIN_PILOT_BUSINESSES}"),
        "production": _gate(production_passed, f"canary={_integer(evidence.get('canary_days'))}/{MIN_CANARY_DAYS} days"),
    }
    blockers = [key for key, gate in gates.items() if not gate["passed"]]
    return {
        "schema": "localos_agent_template_certification_v1",
        "template_key": str(template.get("key") or ""),
        "template_version": str(template.get("version") or ""),
        "status": "certified" if not blockers else "beta",
        "certified": not blockers,
        "gates": gates,
        "blockers": blockers,
        "counts": {
            "fixtures_passed": sum(fixture_status.get(key) == "passed" for key in REQUIRED_FIXTURES),
            "safe_preview_runs": len(safe_preview_runs),
            "successful_production_runs": len(successful_production_runs),
            "useful_pilot_businesses": len(useful_businesses),
        },
    }


def empty_certification_evidence() -> Dict[str, Any]:
    return {
        "fixtures": [{"key": key, "status": "pending"} for key in REQUIRED_FIXTURES],
        "preview_runs": [],
        "production_runs": [],
        "pilot_feedback": [],
        "security": {},
        "version_pins": {},
        "golden_score": 0.0,
        "support_export_passed": False,
        "rollback_test_passed": False,
        "canary_days": 0,
        "canary_incident_free": False,
    }


def _gate(passed: bool, evidence: str) -> Dict[str, Any]:
    return {"passed": bool(passed), "evidence": evidence}


def _score(value: Any) -> float:
    try:
        parsed = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(parsed, 1.0))


def _ratio(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _integer(value: Any) -> int:
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return 0
