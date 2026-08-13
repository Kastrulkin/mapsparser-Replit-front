from copy import deepcopy

import pytest

from tests.test_agent_template_catalog_contract import BETA_TEMPLATE_KEYS


class EmptyCursor:
    def execute(self, query, params=None):
        return None

    def fetchall(self):
        return []


@pytest.mark.parametrize("template_key", BETA_TEMPLATE_KEYS)
def test_valid_input_fixture(template_key):
    from services.agent_template_catalog import get_agent_template
    from services.agent_workflow_dsl import validate_workflow_dsl_document

    template = get_agent_template(template_key)

    assert validate_workflow_dsl_document(template["workflow_dsl"])["valid"] is True
    assert template["certification_gates"]["schema"]["passed"] is True


@pytest.mark.parametrize("template_key", BETA_TEMPLATE_KEYS)
def test_empty_input_fixture_uses_safe_preview_without_provider(template_key, monkeypatch):
    from services import agent_blueprint_workspace
    from services.agent_template_catalog import get_agent_template

    model_step = next(
        step for step in get_agent_template(template_key)["workflow_dsl"]["steps"] if step.get("bounded_model_call") is True
    )
    monkeypatch.setattr(
        agent_blueprint_workspace,
        "_load_workspace",
        lambda cursor, run: {
            "run_input": {"preview_mode": True, "external_side_effects_allowed": False},
            "internal_sources": [],
            "metadata": {},
        },
    )
    monkeypatch.setattr(
        agent_blueprint_workspace,
        "run_llm_task",
        lambda request: (_ for _ in ()).throw(AssertionError("preview cannot call a model provider")),
    )

    result = agent_blueprint_workspace.build_bounded_model_artifact_payload(
        EmptyCursor(),
        {"id": "preview-run", "business_id": "business-1"},
        model_step,
    )

    assert result["bounded_model"]["status"] == "preview_fixture"
    assert result["bounded_model"]["provider_called"] is False
    assert result["external_dispatch_performed"] is False


@pytest.mark.parametrize("template_key", BETA_TEMPLATE_KEYS)
def test_malformed_input_fixture_is_rejected_before_version_save(template_key):
    from services.agent_template_catalog import get_agent_template
    from services.agent_workflow_graph import validate_workflow_graph, workflow_dsl_to_graph

    graph = workflow_dsl_to_graph(get_agent_template(template_key)["workflow_dsl"])
    malformed = deepcopy(graph)
    malformed["nodes"][0]["kind"] = "arbitrary_python"
    malformed["edges"].append({"id": "dangling", "source": malformed["nodes"][0]["id"], "target": "missing"})

    validation = validate_workflow_graph(malformed)

    assert validation["valid"] is False
    assert {item["code"] for item in validation["errors"]} >= {"unknown_node_kind", "dangling_edge"}


@pytest.mark.parametrize("template_key", BETA_TEMPLATE_KEYS)
def test_missing_connection_fixture_has_explicit_preflight_result(template_key):
    from services.agent_integration_preflight import build_agent_integration_preflight
    from services.agent_template_catalog import build_agent_from_template

    draft = build_agent_from_template(template_key)["draft"]
    metadata = deepcopy(draft["metadata"])
    metadata["required_integration_bindings"] = deepcopy(draft["version_payload"]["required_integration_bindings"])

    preflight = build_agent_integration_preflight(EmptyCursor(), business_id="business-1", metadata=metadata)

    if metadata["required_integration_bindings"]:
        assert preflight["ready"] is False
        assert preflight["next_action"] == "connect_required_integrations"
    else:
        assert preflight == {
            "status": "ready",
            "ready": True,
            "items": [],
            "missing": [],
            "missing_count": 0,
            "next_action": "",
        }


@pytest.mark.parametrize("template_key", BETA_TEMPLATE_KEYS)
def test_expired_oauth_fixture_never_falls_through_as_ready(template_key):
    from services.agent_integration_preflight import build_agent_integration_preflight
    from services.agent_template_catalog import build_agent_from_template

    draft = build_agent_from_template(template_key)["draft"]
    bindings = deepcopy(draft["version_payload"]["required_integration_bindings"])
    if not bindings:
        assert all(str(capability).startswith("google_sheets.") is False for capability in draft["version_payload"]["capability_allowlist"])
        return

    class ExpiredOAuthCursor:
        def __init__(self):
            self.read_count = 0

        def execute(self, query, params=None):
            return None

        def fetchall(self):
            self.read_count += 1
            if self.read_count == 1:
                return [
                    {
                        "id": "sheets-1",
                        "business_id": "business-1",
                        "provider": "google_sheets",
                        "status": "active",
                        "auth_ref": "oauth-1",
                        "auth_account_id": None,
                        "auth_is_active": False,
                        "config_json": {"spreadsheet_id": "sheet-1", "sheet_name": "Sheet1"},
                    }
                ]
            return []

    metadata = deepcopy(draft["metadata"])
    metadata["required_integration_bindings"] = bindings
    preflight = build_agent_integration_preflight(ExpiredOAuthCursor(), business_id="business-1", metadata=metadata)

    assert preflight["ready"] is False
    assert preflight["items"][0]["resolution"] == "google_sheets_auth_reconnect_required"


@pytest.mark.parametrize("template_key", BETA_TEMPLATE_KEYS)
def test_transient_provider_failure_fixture_falls_back_to_manual_review(template_key, monkeypatch):
    from services import agent_blueprint_workspace
    from services.agent_template_catalog import get_agent_template
    from services.llm.contracts import LLMTaskResult

    model_step = next(
        step for step in get_agent_template(template_key)["workflow_dsl"]["steps"] if step.get("bounded_model_call") is True
    )
    monkeypatch.setattr(
        agent_blueprint_workspace,
        "_load_workspace",
        lambda cursor, run: {"run_input": {}, "internal_sources": [], "metadata": {}},
    )
    monkeypatch.setattr(
        agent_blueprint_workspace,
        "run_llm_task",
        lambda request: LLMTaskResult(status="failed", fallback_reason="temporary_provider_failure"),
    )

    result = agent_blueprint_workspace.build_bounded_model_artifact_payload(
        EmptyCursor(),
        {"id": "production-run", "business_id": "business-1"},
        model_step,
    )

    assert result["review_required"] is True
    assert result["result"]["items"] == []
    assert result["bounded_model"]["fallback_reason"] == "temporary_provider_failure"
    assert result["external_dispatch_performed"] is False


@pytest.mark.parametrize("template_key", BETA_TEMPLATE_KEYS)
def test_duplicate_idempotency_key_fixture_is_required_by_every_template(template_key):
    from services.agent_template_catalog import get_agent_template

    template = get_agent_template(template_key)

    assert template["limits"]["duplicate_policy"] == "idempotency_key_required"
    assert template["workflow_dsl"]["limits"]["duplicate_policy"] == "idempotency_key_required"


@pytest.mark.parametrize("template_key", BETA_TEMPLATE_KEYS)
def test_worker_restart_fixture_has_no_runtime_planner_or_ephemeral_graph_state(template_key):
    from services.agent_template_catalog import get_agent_template

    workflow = get_agent_template(template_key)["workflow_dsl"]

    assert workflow["runtime"]["planner_required"] is False
    assert workflow["runtime"]["truth"] == "agent_blueprint_versions.steps_json"
    assert all("position" not in step for step in workflow["steps"])
    assert len({step["key"] for step in workflow["steps"]}) == len(workflow["steps"])


@pytest.mark.parametrize("template_key", BETA_TEMPLATE_KEYS)
def test_limit_exceeded_fixture_is_rejected_by_registered_editor(template_key):
    from services.agent_template_catalog import get_agent_template
    from services.agent_visual_editor_registry import validate_visual_editor_settings

    template = get_agent_template(template_key)

    assert 1 <= template["limits"]["max_items_per_run"] <= 500
    assert template["limits"]["max_model_calls_per_run"] == 1
    assert validate_visual_editor_settings({"limits": {"max_items_per_run": 501}})["valid"] is False
    assert validate_visual_editor_settings({"limits": {"max_model_calls_per_run": 2}})["valid"] is False
