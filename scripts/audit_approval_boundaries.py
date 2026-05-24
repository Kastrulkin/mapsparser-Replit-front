#!/usr/bin/env python3
from pathlib import Path
import ast


ROOT = Path(__file__).resolve().parents[1]

BLUEPRINT_FILES = [
    "src/api/agent_blueprints_api.py",
    "src/services/agent_blueprint_runner.py",
    "src/services/agent_blueprint_orchestrator.py",
    "src/services/outreach_send_capability.py",
]

OPERATOR_GENERATION_FILES = [
    "src/services/operator_manual_review.py",
    "src/services/operator_review_reply_bulk.py",
    "src/services/operator_services_optimization.py",
    "src/services/operator_social_post_generation.py",
    "src/services/operator_news_generation.py",
]

OPERATOR_BOUNDARY_FILES = [
    "src/api/operator_api.py",
    "src/services/operator_paid_action_adapter.py",
    "src/services/operator_paid_executor.py",
    "src/services/operator_fresh_reviews.py",
    "src/services/operator_map_refresh.py",
    "src/services/operator_manual_publish.py",
    *OPERATOR_GENERATION_FILES,
]

BLUEPRINT_DISALLOWED_CALLS = {
    "dispatch_due_outreach_queue",
    "send_telegram_bot_message",
    "send_whatsapp_waba_message",
    "send_whatsapp_message",
    "send_telegram_message",
    "requests.post",
    "requests.get",
    "urllib.request.urlopen",
}

OPERATOR_DISALLOWED_EXTERNAL_WRITES = {
    "send_telegram_bot_message",
    "send_whatsapp_waba_message",
    "send_whatsapp_message",
    "send_telegram_message",
    "dispatch_due_outreach_queue",
}


def read_text(path_text):
    return (ROOT / path_text).read_text(encoding="utf-8")


def call_name(node):
    func = node.func
    parts = []
    while isinstance(func, ast.Attribute):
        parts.append(func.attr)
        func = func.value
    if isinstance(func, ast.Name):
        parts.append(func.id)
    if not parts:
        return ""
    return ".".join(reversed(parts))


def collect_calls(path_text):
    tree = ast.parse(read_text(path_text), filename=path_text)
    calls = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            calls.append((node.lineno, call_name(node)))
    return calls


def require_markers(path_text, markers, findings):
    text = read_text(path_text)
    for marker in markers:
        if marker not in text:
            findings.append(f"{path_text}: missing marker {marker}")


def reject_calls(path_text, disallowed, findings):
    for line_no, name in collect_calls(path_text):
        if name in disallowed:
            findings.append(f"{path_text}:{line_no}: disallowed boundary call {name}")


def audit_blueprint_boundaries(findings):
    for path_text in BLUEPRINT_FILES:
        reject_calls(path_text, BLUEPRINT_DISALLOWED_CALLS, findings)

    require_markers(
        "src/services/agent_blueprint_runner.py",
        [
            "self.orchestrator.execute(",
            "allow_execute_when_approved=True",
            "_capability_requires_approval",
            "_has_required_approval",
            "DANGEROUS_CAPABILITY_WORDS",
            "required_approval_type",
            '"billing": {"source": "agent_blueprint"}',
            '"approval": {"source": "agent_blueprint"',
        ],
        findings,
    )
    require_markers(
        "src/services/agent_blueprint_orchestrator.py",
        [
            "ActionOrchestrator(",
            "OUTREACH_SEND_BATCH_CAPABILITY: handle_outreach_send_batch",
        ],
        findings,
    )
    require_markers(
        "src/services/outreach_send_capability.py",
        [
            "external_dispatch_performed",
            "queued_not_dispatched",
            "dispatcher_required",
            "dispatch_due_outreach_queue",
        ],
        findings,
    )


def audit_operator_boundaries(findings):
    for path_text in OPERATOR_BOUNDARY_FILES:
        reject_calls(path_text, OPERATOR_DISALLOWED_EXTERNAL_WRITES, findings)

    for path_text in OPERATOR_GENERATION_FILES:
        require_markers(
            path_text,
            [
                "build_paid_action_preflight",
                "reserve_paid_action_credits",
                "finalize_reserved_action_credits",
                '"external_writes_performed": False',
            ],
            findings,
        )

    require_markers(
        "src/services/operator_paid_action_adapter.py",
        [
            '"provider_call_allowed": False',
            '"external_call_performed": False',
            '"external_writes_performed": False',
            '"parsequeue_jobs_created": False',
            '"ai_generation_performed": False',
        ],
        findings,
    )
    require_markers(
        "src/services/operator_paid_executor.py",
        [
            "EXECUTION_ENABLED",
            "reserve_paid_action_credits",
            "finalize_reserved_action_credits",
            '"external_calls_performed": False',
            '"external_writes_performed": False',
        ],
        findings,
    )
    require_markers(
        "src/services/operator_manual_publish.py",
        [
            '"manual_publication_only": True',
            '"external_writes_performed": False',
            "LocalOS не публиковал ответ во внешние карты",
        ],
        findings,
    )
    require_markers(
        "src/services/operator_services_optimization.py",
        [
            "apply_service_optimization_suggestions",
            "explicit_confirmation: bool = False",
            "explicit_confirmation_required",
            '"manual_approval_received": True',
            '"credit_charged": False',
            '"charged_credits": 0',
            "UPDATE userservices",
        ],
        findings,
    )
    require_markers(
        "src/api/operator_api.py",
        [
            '"/services/optimize/apply"',
            "explicit_confirmation=bool(payload.get(\"confirm_apply\"))",
            '"explicit_confirmation": bool(payload.get("confirm_apply"))',
        ],
        findings,
    )


def audit_dispatcher_opt_in(findings):
    require_markers(
        "src/worker.py",
        [
            '_env_bool("OUTREACH_DISPATCH_ENABLED", False)',
        ],
        findings,
    )
    require_markers(
        "docker-compose.yml",
        [
            "OUTREACH_DISPATCH_ENABLED: ${OUTREACH_DISPATCH_ENABLED:-false}",
        ],
        findings,
    )


def audit_blueprint_smoke_contract(findings):
    require_markers(
        "scripts/smoke_agent_blueprint_outreach_api.py",
        [
            '"new"',
            '"unprocessed"',
            "source_artifact",
            "queued_not_dispatched",
            "dispatcher_started",
            "fixture_cleaned",
            "assert_no_dispatch",
            "cleanup_fixture",
        ],
        findings,
    )


def main():
    findings = []
    audit_blueprint_boundaries(findings)
    audit_operator_boundaries(findings)
    audit_dispatcher_opt_in(findings)
    audit_blueprint_smoke_contract(findings)
    if findings:
        for finding in findings:
            print(finding)
        raise SystemExit(1)
    print("OK: Blueprint/Operator approval, billing, manual-publication, and dispatcher boundaries are guarded")


if __name__ == "__main__":
    main()
