#!/usr/bin/env python3
"""Pure parser controls for ``native_unit_slice_hflypi.py``; no pytest run."""

from __future__ import annotations

import json
from pathlib import Path
import runpy


SUPPORT = Path(__file__).resolve().parent
def payload(modules: dict[str, int], skipped: int = 0) -> dict[str, object]:
    nodeids = [f"{module}::synthetic_{index}" for module, count in modules.items() for index in range(count)]
    total = sum(modules.values())
    state = {
        "collected": total, "passed": total - skipped, "failed": 0,
        "skipped": skipped, "xfailed": 0, "setup_failed": 0,
        "call_failed": 0, "pytest_exitstatus": 0, "pytest_return": 0,
        "nodeids": nodeids,
        "subtests_passed": 0, "subtests_failed": 0, "subtests_skipped": 0, "subtests_xfailed": 0,
    }
    return {"exit_code": 0, "timed_out": False, "stdout": "HFLYPI_TC_ONE_RESULT=" + json.dumps(state)}


def rejected(action) -> None:
    try:
        action()
    except RuntimeError:
        return
    raise AssertionError("invalid pure-unit result accepted")


def main() -> int:
    helper = runpy.run_path(str(SUPPORT / "native_tc_one_hflypi.py"))
    unit = runpy.run_path(str(SUPPORT / "native_unit_slice_hflypi.py"))
    profiles = unit["PROFILES"]
    base_environment = {"PYTEST_DISABLE_PLUGIN_AUTOLOAD": "1"}
    configured = unit["profile_environment"]("agent-social-pure-v1", base_environment)
    assert configured["DATABASE_URL"] == "postgresql+psycopg2://metadata_only@127.0.0.1:1/localos_metadata_only"
    assert "DATABASE_URL" not in base_environment
    for old_profile in ("card-growth-v1", "policy-content-v1"):
        assert unit["profile_environment"](old_profile, base_environment) == base_environment
    rejected(lambda: unit["profile_environment"]("agent-social-pure-v1", {"DATABASE_URL": "unreviewed"}))
    assert set(profiles) == {"card-growth-v1", "policy-content-v1", "agent-social-pure-v1", "governed-operations-pure-v2"}
    assert unit["profile_environment"]("governed-operations-pure-v2", base_environment) == configured
    rejected(lambda: unit["profile_environment"]("governed-operations-pure-v2", {"DATABASE_URL": "unreviewed"}))
    assert profiles["governed-operations-pure-v2"]["modules"] == {
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
    }
    assert sum(profiles["governed-operations-pure-v2"]["modules"].values()) == 828
    assert "tests/test_operator_service_creation.py" not in profiles["governed-operations-pure-v2"]["modules"]
    old_modules = {
        module for name, selected in profiles.items()
        if name != "governed-operations-pure-v2" for module in selected["modules"]
    }
    assert old_modules.isdisjoint(profiles["governed-operations-pure-v2"]["modules"])
    assert profiles["card-growth-v1"]["modules"] == {"tests/test_card_growth_copy_contract.py": 200}
    assert profiles["policy-content-v1"]["modules"] == {
        "tests/test_founder_outreach_campaigns.py": 174,
        "tests/test_legacy_agent_approval_policy.py": 69,
        "tests/test_content_plan_generation.py": 67,
        "tests/test_agent_template_validation_fixtures.py": 54,
    }
    assert profiles["agent-social-pure-v1"]["modules"] == {
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
    }
    for selected in profiles.values():
        modules = selected["modules"]
        profile = {"targets": list(modules), "count": sum(modules.values())}
        positive = helper["parse_test"](payload(modules), profile)
        assert unit["require_module_counts"](positive, modules) == modules
        rejected(lambda: helper["parse_test"](payload(modules, 1), profile))
        rejected(lambda: unit["require_module_counts"]({"nodeids": []}, modules))
        changed_nodes = list(positive["nodeids"])
        changed_nodes[0] = "tests/test_foreign.py::synthetic_other"
        rejected(lambda: unit["require_module_counts"]({"nodeids": changed_nodes}, modules))
        if len(modules) > 1:
            changed_nodes[0] = list(modules)[1] + "::synthetic_extra"
            rejected(lambda: unit["require_module_counts"]({"nodeids": changed_nodes}, modules))
        compile(helper["plugin_source"](profile["targets"]), "<reviewed-unit-runner>", "exec")
    print("native unit profiles: exact 200/364/524/828-node inventories and negative gates passed; operator28 requires separate real-PG run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
