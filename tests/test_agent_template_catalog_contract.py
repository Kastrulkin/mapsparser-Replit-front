import pytest


BETA_TEMPLATE_KEYS = (
    "daily_owner_digest",
    "negative_review_reply",
    "service_seo_cleanup",
    "card_posts_from_signals",
    "tomorrow_bookings_check",
    "google_sheets_business_result",
)

REQUIRED_MANIFEST_FIELDS = {
    "key",
    "version",
    "name",
    "business_result",
    "vertical",
    "trigger",
    "inputs_schema",
    "workflow_dsl",
    "required_connections",
    "approval_policy",
    "limits",
    "output_schema",
    "risk_level",
    "certification_status",
    "fixtures",
    "golden_results",
}


def test_catalog_is_read_only_and_contains_ten_versioned_manifests():
    from services.agent_template_catalog import build_agent_template_catalog

    first = build_agent_template_catalog()
    second = build_agent_template_catalog()

    assert len(first) == 10
    assert first == second
    assert len({(item["key"], item["version"]) for item in first}) == 10
    assert all(REQUIRED_MANIFEST_FIELDS <= set(item) for item in first)
    assert {item["key"] for item in first if item["certification_status"] == "beta"} == set(BETA_TEMPLATE_KEYS)


@pytest.mark.parametrize("template_key", BETA_TEMPLATE_KEYS)
def test_beta_template_is_a_safe_versioned_dsl_not_a_blueprint(template_key):
    from services.agent_template_catalog import get_agent_template
    from services.agent_workflow_dsl import validate_workflow_dsl_document

    template = get_agent_template(template_key)
    workflow = template["workflow_dsl"]

    assert template["version"] == "1.0.0"
    assert validate_workflow_dsl_document(workflow)["valid"] is True
    assert workflow["runtime"]["planner_required"] is False
    assert workflow["limits"]["autonomous_external_write_allowed"] is False
    assert workflow["limits"]["autonomous_localos_write_allowed"] is False
    assert len([step for step in workflow["steps"] if step.get("bounded_model_call") is True]) == 1
    assert all("send" not in str(capability) and "publish" not in str(capability) for capability in workflow["capability_allowlist"])
    assert len(template["golden_results"]) >= 1
    assert all(case.get("key") and case.get("input_fixture") and case.get("expected") for case in template["golden_results"])
