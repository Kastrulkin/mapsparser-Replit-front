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


def test_catalog_exposes_map_templates_only_for_the_selected_pilot_business(monkeypatch):
    from importlib.machinery import ModuleSpec
    from types import ModuleType, SimpleNamespace
    import sys

    from flask import Flask

    from api import agent_blueprints_api as routes
    module_name = 'services.map_card_agents'
    policy = ModuleType(module_name)
    policy.__spec__ = ModuleSpec(module_name, loader=None)
    policy.TEMPLATE_KEYS = ('maps_initial_setup', 'maps_card_check')
    policy.pilot_allowed = lambda business_id: business_id == 'pilot'
    monkeypatch.setitem(sys.modules, module_name, policy)
    monkeypatch.setattr(routes, 'build_agent_template_catalog', lambda: [
        {'key': key, 'certification_status': 'beta'}
        for key in (*policy.TEMPLATE_KEYS, 'daily_owner_digest')
    ])
    monkeypatch.setattr(routes, '_require_auth', lambda: ({'user_id': 'owner'}, None))
    connection = SimpleNamespace(cursor=lambda: object())
    monkeypatch.setattr(routes, 'DatabaseManager', lambda: SimpleNamespace(conn=connection, close=lambda: None))

    def check_access(cursor, business_id, user_data):
        if business_id == 'private':
            return False, routes._json_error('Forbidden', 403, 'FORBIDDEN')
        return True, None

    monkeypatch.setattr(routes, '_require_business_access', check_access)
    app = Flask(__name__)
    app.register_blueprint(routes.agent_blueprints_bp)
    client = app.test_client()

    def catalog_keys(business_id):
        params = {'business_id': business_id} if business_id else {}
        response = client.get('/api/agent-templates', query_string=params)
        assert response.status_code == 200
        return {template['key'] for template in response.json['templates']}

    assert catalog_keys('pilot') == catalog_keys(None)
    assert catalog_keys('new-business') == catalog_keys('pilot') - set(policy.TEMPLATE_KEYS)
    assert client.get('/api/agent-templates?business_id=private').status_code == 403


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
