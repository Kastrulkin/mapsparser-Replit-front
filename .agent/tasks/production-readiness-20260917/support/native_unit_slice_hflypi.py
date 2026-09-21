#!/usr/bin/env python3
"""Run a named, reviewed hfLYPi pure-unit slice after explicit review.

The launcher has no Testcontainers mode, connectable database URL, provider
credential or Docker command. Named profiles supply a guard-denied metadata-only
URI for Flask engine construction. It reuses process/result helpers from the reviewed
single-node launcher.  The default frozen guard receives its mandatory local
identity environment and still rejects Testcontainers startup.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import platform
import re
import runpy
import shutil
import sys
import time


SUPPORT = Path(__file__).resolve().parent
BASE = Path("/private/tmp/localos-readiness-20260921.hfLYPi")
SOURCE = BASE / "source"
NATIVE = BASE / "native"
EVIDENCE = NATIVE / "evidence"
VENV = NATIVE / "venv/bin/python"
INSTALLED_GUARD = SOURCE / "src/sitecustomize.py"
DEFAULT_GUARD_SHA256 = "07d3e2dc19cbb0f9e542a6d0835ea17b5efcc5713391c152a833e6efefd61150"
PROFILES = {
    "card-growth-v1": {
        "modules": {"tests/test_card_growth_copy_contract.py": 200},
        "prefix": "native-unit-card-growth", "timeout": 90,
    },
    "policy-content-v1": {
        "modules": {
            "tests/test_founder_outreach_campaigns.py": 174,
            "tests/test_legacy_agent_approval_policy.py": 69,
            "tests/test_content_plan_generation.py": 67,
            "tests/test_agent_template_validation_fixtures.py": 54,
        },
        "prefix": "native-unit-policy-content", "timeout": 120,
    },
    "agent-social-pure-v1": {
        "modules": {
            "tests/test_social_post_service.py": 162,
            "tests/test_agent_blueprint_api_generic_runs.py": 56,
            "tests/test_agent_blueprint_compiler.py": 54,
            "tests/test_agent_blueprint_capabilities.py": 49,
            "tests/test_agent_blueprint_runtime_connections.py": 47,
            "tests/test_agent_blueprint_builder_sessions.py": 32,
            "tests/test_agent_blueprint_async_contracts.py": 30,
            "tests/test_agent_draft_approval_identity.py": 25,
            "tests/test_agent_blueprint_reviews_outreach.py": 18,
            "tests/test_agent_blueprint_contracts_migrations.py": 15,
            "tests/test_agent_blueprint_builder_scenarios.py": 15,
            "tests/test_agent_blueprint_runtime_policy.py": 13,
            "tests/test_agent_blueprint_fake_approval_order.py": 8,
        },
        "prefix": "native-unit-agent-social", "timeout": 180,
    },
    "governed-operations-pure-v2": {
        "modules": {
            "tests/test_contact_intelligence.py": 61,
            "tests/test_author_template_authorization.py": 51,
            "tests/test_web_tracking.py": 47,
            "tests/test_google_oauth_current_access.py": 42,
            "tests/test_outreach_safety_learning.py": 39,
            "tests/test_manual_campaign_dispatch_identity.py": 35,
            "tests/test_llm_routing.py": 34,
            "tests/test_worker_services_quality.py": 31,
            "tests/test_legacy_webhook_auth_security.py": 30,
            "tests/test_social_publish_provider_outcomes.py": 28,
            "tests/test_outreach_experiments.py": 28,
            "tests/test_outreach_personalization_ai.py": 26,
            "tests/test_lead_journey_service.py": 25,
            "tests/test_content_plan_site_ssrf.py": 25,
            "tests/test_social_posts_api.py": 24,
            "tests/test_outreach_template_service.py": 24,
            "tests/test_creator_offer_distribution.py": 24,
            "tests/test_legacy_news_generation_readiness.py": 23,
            "tests/test_auth_email_case_insensitive.py": 20,
            "tests/test_content_voice_write_access.py": 19,
            "tests/test_operator_credit_reservation.py": 15,
            "tests/test_checkout_payment_providers.py": 15,
            "tests/test_chat_domain_subscription.py": 15,
            "tests/test_remaining_api_error_redaction.py": 15,
            "tests/test_network_member_access.py": 14,
            "tests/test_outreach_campaign_resume_sender_scope.py": 13,
            "tests/test_social_media_delivery_ssrf.py": 13,
            "tests/test_media_upload_signature_security.py": 13,
            "tests/test_agent_api_security.py": 12,
            "tests/test_approval_boundaries_audit.py": 10,
            "tests/test_subscription_capabilities.py": 9,
            "tests/test_security_headers.py": 9,
            "tests/test_telegram_control_scope.py": 9,
            "tests/test_outreach_reply_sync_failure_scope.py": 8,
            "tests/test_outreach_mixed_scope_budget.py": 8,
            "tests/test_action_orchestrator_callback_ssrf.py": 7,
            "tests/test_password_reset_sessions.py": 7,
        },
        "prefix": "native-unit-governed-operations", "timeout": 180,
    },
}
MIN_START = 5 * 1024**3
METADATA_ONLY_DATABASE_URL = "postgresql+psycopg2://metadata_only@127.0.0.1:1/localos_metadata_only"


def profile_environment(profile_name: str, environment: dict[str, str]) -> dict[str, str]:
    if "DATABASE_URL" in environment:
        raise RuntimeError("pure-unit environment must not inherit a database URL")
    result = dict(environment)
    if profile_name in {"agent-social-pure-v1", "governed-operations-pure-v2"}:
        # Flask's migration metadata extension needs a URI, not a connection.
        # Port 1 remains denied by the unchanged psycopg/socket guard.
        result["DATABASE_URL"] = METADATA_ONLY_DATABASE_URL
    return result


def valid_attempt(value: str) -> str:
    if not re.fullmatch(r"v[1-9][0-9]*", value):
        raise argparse.ArgumentTypeError("attempt must be v followed by a positive integer")
    return value


def require_module_counts(callback: dict[str, object], modules: dict[str, int]) -> dict[str, int]:
    nodes = callback.get("nodeids")
    if not isinstance(nodes, list) or not all(isinstance(node, str) for node in nodes):
        raise RuntimeError("unit slice node inventory is missing")
    observed = {module: sum(node.startswith(module + "::") for node in nodes) for module in modules}
    if observed != modules or sum(observed.values()) != len(nodes):
        raise RuntimeError("unit slice per-module counts differ from the reviewed inventory")
    return observed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--attempt", required=True, type=valid_attempt)
    parser.add_argument("--profile", choices=tuple(PROFILES), default="card-growth-v1")
    values = parser.parse_args()
    selected = PROFILES[values.profile]
    modules = selected["modules"]
    profile = {"targets": list(modules), "count": sum(modules.values())}
    timeout = selected["timeout"]
    destination = EVIDENCE / f"{selected['prefix']}-{values.attempt}.json"
    output: dict[str, object] = {
        "attempt": values.attempt,
        "profile": values.profile,
        "targets": profile["targets"],
        "expected_count": profile["count"],
        "expected_module_counts": modules,
        "phase": "preflight",
    }
    guard_helpers = None
    shared = None
    started = time.monotonic()
    try:
        if platform.machine() != "arm64":
            raise RuntimeError("native unit slice requires arm64 parent")
        if destination.exists() or destination.is_symlink():
            raise RuntimeError("attempt evidence path already exists")
        if shutil.disk_usage(BASE).free < MIN_START:
            raise RuntimeError("native unit slice requires 5 GiB free")
        guard_helpers = runpy.run_path(str(SUPPORT / "native_guard_checks_hflypi.py"))
        shared = runpy.run_path(str(SUPPORT / "native_tc_one_hflypi.py"))
        if shared["digest"](INSTALLED_GUARD) != DEFAULT_GUARD_SHA256:
            raise RuntimeError("installed default guard identity differs")
        output["installed_guard_sha256_before"] = DEFAULT_GUARD_SHA256
        output["frozen_blobs_before"] = guard_helpers["verify_frozen_source"]()
        if output["frozen_blobs_before"] != 5720:
            raise RuntimeError("unexpected frozen blob count")
        environment = guard_helpers["environment"](DEFAULT_GUARD_SHA256)
        environment.pop("LOCALOS_HFLYPI_PROBE_DSN", None)
        environment = profile_environment(values.profile, environment)
        environment["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
        output["environment_keys"] = sorted(environment)
        output["launcher_sha256"] = shared["digest"](Path(__file__))
        output["shared_helpers_sha256"] = shared["digest"](SUPPORT / "native_tc_one_hflypi.py")
        output["guard_helpers_sha256"] = shared["digest"](SUPPORT / "native_guard_checks_hflypi.py")
        output["phase"] = "test"
        capture = shared["result"](
            ["/usr/bin/arch", "-arm64", str(VENV), "-B", "-c", shared["plugin_source"](profile["targets"])],
            environment,
            timeout,
            started + timeout,
        )
        output["test"] = capture
        output["callbacks"] = shared["parse_test"](capture, profile)
        output["observed_module_counts"] = require_module_counts(output["callbacks"], modules)
        output["phase"] = "passed"
    except BaseException:
        error = sys.exception()
        output["phase"] = "failed"
        output["error"] = f"{type(error).__name__}: {error}"
    finally:
        try:
            if guard_helpers is None or shared is None:
                raise RuntimeError("post-verification helpers were not loaded")
            output["installed_guard_sha256_after"] = shared["digest"](INSTALLED_GUARD)
            output["frozen_blobs_after"] = guard_helpers["verify_frozen_source"]()
            if output["installed_guard_sha256_after"] != DEFAULT_GUARD_SHA256:
                raise RuntimeError("installed default guard changed during unit slice")
            if output["frozen_blobs_after"] != 5720:
                raise RuntimeError("frozen source changed during unit slice")
        except BaseException:
            error = sys.exception()
            output["phase"] = "failed"
            output["postverify_error"] = f"{type(error).__name__}: {error}"
        output["duration_seconds"] = round(time.monotonic() - started, 3)
        output["free_bytes_after"] = shutil.disk_usage(BASE).free
        if not destination.exists() and not destination.is_symlink():
            writer = shared["write_exclusive"] if shared is not None else None
            if callable(writer):
                writer(destination, output)
            else:
                raise RuntimeError("could not write exclusive unit-slice evidence")
    return 0 if output.get("phase") == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
