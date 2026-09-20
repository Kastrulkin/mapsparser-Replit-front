"""Legacy runner admission against canonical and resolved-payload policy."""

import pytest

from services import agent_blueprint_runner
from services.agent_blueprint_runner import AgentBlueprintRunner
from services.agent_capability_handlers import CANONICAL_CAPABILITIES, LEGACY_CAPABILITY_ALIASES
from core.action_policy import evaluate_risk_policy
from tests.agent_blueprint_fakes import FakeCursor


class RecordingOrchestrator:
    def __init__(self):
        self.calls = []

    def execute(self, envelope, user_data, *, allow_execute_when_approved=False):
        self.calls.append((envelope, allow_execute_when_approved))
        return {"success": True, "status": "completed", "result": {"status": "prepared"}}


@pytest.fixture
def runtime(monkeypatch):
    cursor = FakeCursor()
    orchestrator = RecordingOrchestrator()
    domain_calls = []

    def record_domain_execution(*args, **kwargs):
        domain_calls.append(kwargs)
        return {"executed": 0, "items": [], "localos_writes_performed": False}

    monkeypatch.setattr(agent_blueprint_runner, "execute_approved_domain_requests", record_domain_execution)
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1", "business_id": "biz1", "metadata_json": {},
    }
    cursor.tables["agent_runs"]["run1"] = {
        "id": "run1", "blueprint_id": "bp1", "blueprint_version_id": "ver1",
        "business_id": "biz1", "status": "running", "input_json": {}, "output_json": {},
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1", "blueprint_id": "bp1", "steps_json": [],
        "capability_allowlist_json": [], "inputs_schema_json": {"properties": {}},
    }
    return cursor, orchestrator, domain_calls, AgentBlueprintRunner(cursor, orchestrator)


def configure(runtime, capability, payload=None, **step_options):
    cursor, _, _, _ = runtime
    step = {
        "key": "sensitive_step", "type": "capability", "capability": capability,
        "payload": payload or {}, **step_options,
    }
    version = cursor.tables["agent_blueprint_versions"]["ver1"]
    version["steps_json"] = [step]
    version["capability_allowlist_json"] = [capability]
    return step


def execute(runtime, step):
    cursor, _, _, runner = runtime
    return runner._execute_capability_step(
        cursor.tables["agent_runs"]["run1"], cursor.tables["agent_blueprint_versions"]["ver1"],
        step, 0, {"user_id": "user1"},
    )


REQUIRED_CAPABILITIES = [
    "finance.daily.apply_operator", "finance.transaction.apply_operator",
    "finance.sales_import.apply_operator", "finance.transaction.create", "work.policy.apply",
    "appointments.create_request", "appointments.update", "appointments.cancel",
    "finance.manual_entry", "finance.create_transaction", "finance.transaction.create_request",
    "sheets.append_row",
]


@pytest.mark.parametrize("capability", REQUIRED_CAPABILITIES)
def test_canonical_policy_cannot_be_disabled_by_legacy_step(runtime, capability):
    cursor, orchestrator, domain_calls, _ = runtime
    step = configure(runtime, capability, requires_approval=False)

    completed = execute(runtime, step)

    assert orchestrator.calls == [], "Missing approval must stop before the trusted orchestrator boundary"
    assert domain_calls == []
    assert completed is False
    assert cursor.tables["agent_runs"]["run1"]["status"] == "failed"
    assert next(iter(cursor.tables["agent_run_steps"].values()))["output_json"]["error"] == "approval_required"


@pytest.mark.parametrize(("capability", "payload"), [
    ("news.generate", {"publish": True}),
    ("reviews.reply", {"publish": True}),
    ("reviews.reply.draft", {"publish": True}),
    ("services.optimize", {"bulk": True}),
    ("services.optimize", {"source": "file"}),
    ("sales.ingest", {"source": "ocr"}),
    ("sales.ingest", {"transactions": [{"amount": 50000}]}),
    ("sales.ingest", {"transactions": [{"amount": 1}] * 20}),
])
def test_payload_risk_is_evaluated_after_public_input_resolution(runtime, capability, payload):
    cursor, orchestrator, domain_calls, _ = runtime
    step = configure(runtime, capability)
    cursor.tables["agent_blueprint_versions"]["ver1"]["inputs_schema_json"] = {
        "properties": {key: {} for key in payload},
    }
    cursor.tables["agent_runs"]["run1"]["input_json"] = payload

    completed = execute(runtime, step)

    assert orchestrator.calls == []
    assert domain_calls == []
    assert completed is False


@pytest.mark.parametrize("capability", ["appointments.read", "news.generate", "services.optimize", "reviews.reply.draft"])
def test_safe_step_does_not_grant_approval_override_or_approved_domain_execution(runtime, capability):
    _, orchestrator, domain_calls, _ = runtime
    step = configure(runtime, capability)

    assert execute(runtime, step) is True

    assert len(orchestrator.calls) == 1
    assert orchestrator.calls[0][1] is False
    assert domain_calls == []


@pytest.mark.parametrize(("run_id", "approval_type", "status"), [
    ("another-run", "finance_import", "approved"),
    ("run1", "shortlist", "approved"),
    ("run1", "finance_import", "pending"),
    ("run1", "finance_import", "rejected"),
])
def test_wrong_run_type_or_unapproved_decision_does_not_authorize_write(runtime, run_id, approval_type, status):
    cursor, orchestrator, domain_calls, _ = runtime
    step = configure(runtime, "finance.daily.apply_operator", required_approval_type="finance_import")
    cursor.tables["agent_approvals"]["decision1"] = {
        "id": "decision1", "run_id": run_id, "approval_type": approval_type, "status": status,
    }

    assert execute(runtime, step) is False
    assert orchestrator.calls == []
    assert domain_calls == []


def test_matching_required_approval_retains_controlled_execution(runtime):
    cursor, orchestrator, domain_calls, _ = runtime
    step = configure(runtime, "finance.daily.apply_operator", required_approval_type="finance_import")
    cursor.tables["agent_approvals"]["decision1"] = {
        "id": "decision1", "run_id": "run1", "approval_type": "finance_import", "status": "approved",
    }

    assert execute(runtime, step) is True
    assert len(orchestrator.calls) == 1
    assert orchestrator.calls[0][1] is True
    assert len(domain_calls) == 1


def test_actual_legacy_start_run_cannot_bypass_finance_approval(runtime):
    cursor, orchestrator, domain_calls, runner = runtime
    configure(runtime, "finance.daily.apply_operator")
    cursor.tables["agent_runs"].clear()

    result = runner.start_run("ver1", {}, {"user_id": "user1"})

    assert orchestrator.calls == []
    assert domain_calls == []
    assert result["run"]["status"] == "failed"


def test_safe_proposal_cannot_enter_approved_domain_executor_without_a_decision(runtime):
    _, _, domain_calls, _ = runtime
    step = configure(runtime, "services.optimize")

    assert execute(runtime, step) is True
    assert domain_calls == [], "Preparing a proposal is not approval to apply it"


def test_undeclared_approval_type_cannot_reuse_an_unrelated_prior_decision(runtime):
    cursor, orchestrator, domain_calls, _ = runtime
    step = configure(runtime, "finance.daily.apply_operator")
    cursor.tables["agent_approvals"]["decision1"] = {
        "id": "decision1", "run_id": "run1", "approval_type": "shortlist", "status": "approved",
    }

    assert execute(runtime, step) is False
    assert orchestrator.calls == []
    assert domain_calls == []


@pytest.mark.parametrize(("alias", "canonical"), list(LEGACY_CAPABILITY_ALIASES.items()))
def test_core_action_policy_cannot_be_weakened_by_a_legacy_alias(alias, canonical):
    assert evaluate_risk_policy(alias, {}, {})["requires_human"] == evaluate_risk_policy(canonical, {}, {})["requires_human"]


@pytest.mark.parametrize("capability", [name for name, metadata in CANONICAL_CAPABILITIES.items() if metadata["approval_required"]])
def test_core_action_policy_enforces_required_registry_capabilities(capability):
    assert evaluate_risk_policy(capability, {}, {})["requires_human"] is True


@pytest.mark.parametrize("capability", ["sheets.append_row", "google_sheets.append_row", "google_sheets.update_cells"])
def test_sheet_preview_has_no_approval_or_execution_effects(runtime, capability):
    cursor, orchestrator, domain_calls, _ = runtime
    step = configure(runtime, capability)
    cursor.tables["agent_runs"]["run1"]["input_json"] = {"preview_mode": True}

    assert execute(runtime, step) is True
    assert orchestrator.calls == []
    assert domain_calls == []
    assert next(iter(cursor.tables["agent_run_steps"].values()))["output_json"]["status"] == "preview_only"


@pytest.mark.parametrize("capability", ["finance.transaction.create", "finance.manual_entry", "finance.create_transaction"])
def test_approved_finance_aliases_remain_request_only_until_separate_apply(runtime, capability):
    cursor, _, domain_calls, _ = runtime
    step = configure(runtime, capability, required_approval_type="finance_transaction_import")
    cursor.tables["agent_approvals"]["decision1"] = {
        "id": "decision1", "run_id": "run1", "approval_type": "finance_transaction_import", "status": "approved",
    }

    assert execute(runtime, step) is True
    assert len(domain_calls) == 1
    assert domain_calls[0]["apply_finance"] is False


def test_runtime_contract_reports_resolved_payload_approval_requirement(runtime):
    cursor, _, _, _ = runtime
    step = configure(runtime, "news.generate", required_approval_type="news_publication")
    cursor.tables["agent_blueprint_versions"]["ver1"]["inputs_schema_json"] = {"properties": {"publish": {}}}
    cursor.tables["agent_runs"]["run1"]["input_json"] = {"publish": True}
    cursor.tables["agent_approvals"]["decision1"] = {
        "id": "decision1", "run_id": "run1", "approval_type": "news_publication", "status": "approved",
    }

    assert execute(runtime, step) is True
    output = next(iter(cursor.tables["agent_run_steps"].values()))["output_json"]
    assert output["production_action_contract"]["approval_policy"]["required"] is True
