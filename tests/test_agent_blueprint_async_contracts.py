import json
from datetime import datetime, timezone
from pathlib import Path

from tests.agent_blueprint_fakes import *  # noqa: F403
from tests.source_contract_helpers import read_agent_blueprints_frontend_source


def test_agent_run_contract_hides_service_fields_and_requires_content_plan_date():
    from services.agent_run_contract import effective_agent_input_schema, validate_agent_run_input

    schema = {
        "type": "object",
        "properties": {
            "request": {"type": "string"},
            "business_id": {"type": "string"},
            "integration_id": {"type": "string"},
            "spreadsheet_id": {"type": "string"},
            "sheet_name": {"type": "string"},
        },
    }
    steps = [{"type": "capability", "capability": "content_plan.item.create_draft"}]
    public_schema = effective_agent_input_schema(schema, steps)

    assert "business_id" not in public_schema["properties"]
    assert "integration_id" not in public_schema["properties"]
    assert "spreadsheet_id" not in public_schema["properties"]
    assert "sheet_name" not in public_schema["properties"]
    assert public_schema["properties"]["scheduled_for"]["format"] == "date"
    assert "scheduled_for" in public_schema["required"]

    invalid = validate_agent_run_input(schema, {"request": "Поездка"}, steps)
    assert invalid["valid"] is False
    assert invalid["errors"][0]["field"] == "scheduled_for"

    valid = validate_agent_run_input(
        schema,
        {"request": "Поездка", "scheduled_for": "2099-07-27", "business_id": "other"},
        steps,
    )
    assert valid["valid"] is True
    assert valid["input"] == {"request": "Поездка", "scheduled_for": "2099-07-27"}


def test_agent_capability_catalog_marks_beta_runtime_contracts():
    from services.agent_capability_handlers import build_capability_catalog, capability_runtime_contract

    catalog = build_capability_catalog()["capabilities"]
    assert catalog["google_sheets.read_rows"]["runtime_status"] == "production_read"
    assert catalog["content_plan.item.create_draft"]["beta_enabled"] is True
    assert catalog["communications.send_reminder"]["runtime_status"] == "request_only"
    assert catalog["communications.send_reminder"]["beta_enabled"] is False
    assert capability_runtime_contract("unknown.capability")["runtime_status"] == "planned_gap"


def test_execution_contract_exposes_saved_steps_and_separates_candidate_from_active(monkeypatch):
    from api import agent_blueprints_api

    monkeypatch.setattr(
        agent_blueprints_api,
        "_activation_preview_run_status",
        lambda cursor, blueprint_id, version_id: {"ready": version_id == "candidate", "status": "completed"},
    )
    blueprint = {
        "id": "bp1",
        "description": "Прочитать таблицу и подготовить результат",
        "metadata_json": {"execution_mode": "manual", "custom_process": {"trigger": "manual.run"}},
    }
    active = {
        "id": "active",
        "version_number": 1,
        "goal": "Прочитать таблицу",
        "inputs_schema_json": {"type": "object", "properties": {"date": {"type": "string", "format": "date"}}},
        "steps_json": [{"key": "read", "type": "capability", "capability": "google_sheets.read_rows"}],
        "capability_allowlist_json": ["google_sheets.read_rows"],
        "approval_policy_json": {},
        "output_schema_json": {"draft_text": {"type": "string"}},
    }
    candidate = {**active, "id": "candidate", "version_number": 2, "goal": "Прочитать таблицу и сохранить черновик"}

    contract = agent_blueprints_api._build_execution_contract(object(), blueprint, candidate, active)

    assert contract["original_request"] == blueprint["description"]
    assert contract["has_unpublished_changes"] is True
    assert contract["candidate"]["validation"]["tested"] is True
    assert contract["active"]["steps"][0]["title"] == "Прочитать строки Google Таблицы"
    assert contract["active"]["inputs_schema"]["properties"]["date"]["format"] == "date"


def test_preview_candidate_resolution_does_not_fall_back_to_active_version(monkeypatch):
    from api import agent_blueprints_api

    candidate = {"id": "candidate", "version_number": 2}
    monkeypatch.setattr(agent_blueprints_api, "_load_latest_blueprint_version", lambda cursor, blueprint_id: candidate)
    monkeypatch.setattr(
        agent_blueprints_api,
        "_resolve_active_version",
        lambda cursor, blueprint: {"id": "active", "version_number": 1},
    )

    resolved = agent_blueprints_api._resolve_candidate_version(object(), {"id": "bp1", "status": "active"})

    assert resolved == candidate


def test_run_progress_uses_saved_version_steps_and_actual_step_statuses():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    class Cursor:
        def execute(self, query, params=None):
            self.row = {"steps_json": [{"key": "read"}, {"key": "draft"}, {"key": "save"}]}

        def fetchone(self):
            return self.row

    runner = object.__new__(AgentBlueprintRunner)
    runner.cursor = Cursor()
    progress = runner._run_progress(
        {"status": "running", "blueprint_version_id": "v1"},
        [
            {"step_key": "read", "status": "completed"},
            {"step_key": "draft", "status": "running"},
        ],
    )

    assert progress == {
        "state": "running",
        "total_steps": 3,
        "completed_steps": 1,
        "current_step_index": 1,
        "current_step_key": "draft",
        "current_step_status": "running",
        "percent": 33,
    }


def test_agent_async_run_flag_is_scoped_to_beta_businesses(monkeypatch):
    from services.agent_run_queue import async_agent_runs_enabled

    monkeypatch.setenv("AGENT_ASYNC_RUNS_ENABLED", "true")
    monkeypatch.setenv("AGENT_BETA_BUSINESS_IDS", "biz1,biz2")
    assert async_agent_runs_enabled("biz1") is True
    assert async_agent_runs_enabled("biz3") is False

    monkeypatch.setenv("AGENT_ASYNC_RUNS_ENABLED", "false")
    assert async_agent_runs_enabled("biz1") is False


def test_agent_run_queue_reuses_existing_idempotency_key(monkeypatch):
    from services import agent_run_queue

    class Cursor:
        def __init__(self):
            self.result = None

        def execute(self, query, params=None):
            normalized = " ".join(query.split()).lower()
            if normalized.startswith("select pg_advisory_xact_lock"):
                self.result = None
            elif "where business_id = %s and blueprint_id = %s and idempotency_key = %s" in normalized:
                self.result = {"id": "run-existing"}
            else:
                raise AssertionError(f"Unexpected SQL: {query}")

        def fetchone(self):
            result = self.result
            self.result = None
            return result

    class Runner:
        def __init__(self, cursor):
            self.cursor = cursor

        def load_run(self, run_id, user_data=None):
            return {"id": run_id, "status": "queued"}

    monkeypatch.setattr(agent_run_queue, "build_agent_integration_preflight", lambda *args, **kwargs: {"ready": True})
    monkeypatch.setattr(agent_run_queue, "AgentBlueprintRunner", Runner)

    result = agent_run_queue.enqueue_agent_run(
        Cursor(),
        blueprint={"id": "bp1", "business_id": "biz1", "metadata_json": {}},
        version={"id": "version1"},
        input_payload={"preview_mode": True},
        user_data={"user_id": "user1"},
        idempotency_key="same-click",
    )
    assert result["success"] is True
    assert result["reused"] is True
    assert result["run"]["id"] == "run-existing"


def test_unified_run_billing_counts_internal_artifact_tokens_once():
    from services.agent_blueprint_runner import AgentBlueprintRunner

    ledger = AgentBlueprintRunner(cursor=None)._build_run_unified_billing_ledger(
        {"input_json": {"preview_mode": False}},
        {
            "summary": {"settled_tokens": 180, "total_cost": 0.02},
            "actions": [
                {
                    "settled_tokens": 180,
                    "total_cost": 0.02,
                }
            ],
        },
        [
            {
                "artifact_type": "agent_output_draft",
                "payload_json": {
                    "llm_usage": {
                        "prompt_tokens": 800,
                        "completion_tokens": 450,
                        "total_tokens": 1250,
                    }
                },
            },
            {
                "artifact_type": "agent_final_result",
                "payload_json": {},
            },
        ],
    )

    by_key = {item["key"]: item for item in ledger["items"]}
    assert by_key["production_run"]["actual_tokens"] == 1250
    assert by_key["external_action"]["actual_tokens"] == 180
    assert ledger["summary"]["actual_tokens"] == 1430


def test_superseding_waiting_run_releases_billing_reservation(monkeypatch):
    from services import agent_blueprint_runner

    released = []

    class Cursor:
        def __init__(self):
            self.results = []

        def execute(self, query, params=None):
            normalized = " ".join(query.split()).lower()
            if normalized.startswith("update agent_approvals"):
                self.results = []
                return
            if normalized.startswith("update agent_runs"):
                self.results = [{
                    "id": "old-run",
                    "business_id": "biz1",
                    "created_by_user_id": "user1",
                    "billing_reservation_id": "reservation-1",
                }]
                return
            raise AssertionError(f"Unexpected SQL: {query}")

        def fetchall(self):
            return self.results

    def finalize(cursor, *, run, actual_tokens):
        released.append({"run": run, "actual_tokens": actual_tokens})
        return {"status": "released"}

    monkeypatch.setattr(agent_blueprint_runner, "finalize_agent_run_credits", finalize)
    runner = object.__new__(agent_blueprint_runner.AgentBlueprintRunner)
    runner.cursor = Cursor()

    runner._supersede_pending_runs("bp1")

    assert released == [{
        "run": {
            "id": "old-run",
            "business_id": "biz1",
            "created_by_user_id": "user1",
            "billing_reservation_id": "reservation-1",
            "status": "superseded",
        },
        "actual_tokens": 0,
    }]


def test_agent_async_runtime_contract_is_wired_end_to_end():
    from pathlib import Path

    api_source = Path("src/api/agent_blueprints_api.py").read_text(encoding="utf-8")
    worker_source = Path("src/worker.py").read_text(encoding="utf-8")
    queue_source = Path("src/services/agent_run_queue.py").read_text(encoding="utf-8")
    frontend_source = read_agent_blueprints_frontend_source()
    migration_source = Path("alembic_migrations/versions/20260710_add_agent_run_queue.py").read_text(encoding="utf-8")

    assert "enqueue_agent_run" in api_source
    assert "AGENT_RUN_ALREADY_IN_PROGRESS" in api_source
    assert "_process_agent_run_queue_if_due" in worker_source
    assert "FOR UPDATE SKIP LOCKED" in queue_source
    assert "idempotency_key: window.crypto.randomUUID()" in frontend_source
    assert "getPreviewVersionId(targetBlueprint, blueprintDetails)" in frontend_source
    assert "['open_result', 'view_history', 'approve'].includes(selectedEmployeeAction.kind)" in frontend_source
    assert "selectedEmployeeAction.targetMode === 'results'" not in frontend_source
    assert "waitForAgentRun" in frontend_source
    assert "execution_contract" in frontend_source
    assert "EmployeeAgentScenarioPanel" in frontend_source
    assert "const working = contract?.candidate || contract?.active;" in frontend_source
    assert "Обновить по цели" in frontend_source
    assert "Рабочая версия не включена" in frontend_source
    assert "2xl:grid-cols-[minmax(0,1.2fr)_minmax(20rem,0.8fr)]" in frontend_source
    assert "if (state === 'ready_for_test')" in frontend_source
    assert "Запустите безопасную проверку новой версии" in frontend_source
    assert "serverCompletedSteps" in frontend_source
    assert "billing_reservation_id" in migration_source


def test_agent_today_summary_is_computed_server_side(monkeypatch):
    from api import agent_blueprints_api

    class Cursor:
        def __init__(self):
            self.result = None

        def execute(self, query, params=None):
            normalized = " ".join(query.split()).lower()
            if "from information_schema.columns" in normalized:
                self.result = {"has_timezone": True}
            elif normalized.startswith("select timezone from businesses"):
                self.result = {"timezone": "Europe/Tallinn"}
            elif "count(distinct r.id) filter" in normalized:
                self.result = {
                    "completed_runs": 3,
                    "prepared_results": 2,
                    "pending_approvals": 1,
                    "failed_runs": 0,
                }
            else:
                raise AssertionError(f"Unexpected SQL: {query}")

        def fetchone(self):
            return self.result

    summary = agent_blueprints_api._agent_today_summary(Cursor(), "biz1")
    assert summary["completed_runs"] == 3
    assert summary["prepared_results"] == 2
    assert summary["pending_approvals"] == 1
    assert summary["timezone"] == "Europe/Tallinn"


def test_agent_today_summary_supports_businesses_without_timezone_column():
    from api import agent_blueprints_api

    class Cursor:
        def execute(self, query, params=None):
            normalized = " ".join(query.split()).lower()
            if "from information_schema.columns" in normalized:
                self.result = {"has_timezone": False}
            elif "count(distinct r.id) filter" in normalized:
                self.result = {
                    "completed_runs": 1,
                    "prepared_results": 1,
                    "pending_approvals": 0,
                    "failed_runs": 0,
                }
            else:
                raise AssertionError(f"Unexpected SQL: {query}")

        def fetchone(self):
            return self.result

    summary = agent_blueprints_api._agent_today_summary(Cursor(), "biz1")
    assert summary["completed_runs"] == 1
    assert summary["timezone"] == "Europe/Moscow"


def test_blueprint_access_never_trusts_requested_business_id(monkeypatch):
    from api import agent_blueprints_api

    class Cursor:
        def execute(self, query, params=None):
            self.result = {"id": "bp-other", "business_id": "business-other"}

        def fetchone(self):
            return self.result

    checked = {}

    def deny_other_business(cursor, business_id, user_data):
        checked["business_id"] = business_id
        return False, "forbidden"

    monkeypatch.setattr(agent_blueprints_api, "_require_business_access", deny_other_business)
    blueprint, error = agent_blueprints_api._require_blueprint_access(Cursor(), "bp-other", {"user_id": "owner1"})
    assert blueprint is None
    assert error == "forbidden"
    assert checked["business_id"] == "business-other"


def test_admin_agent_runtime_overview_exposes_queue_scheduler_billing_and_consistency(monkeypatch):
    from api import agent_blueprints_api

    now = datetime(2026, 7, 19, 12, 0, tzinfo=timezone.utc)

    class Cursor:
        def __init__(self):
            self.result = None
            self.results = []

        def execute(self, query, params=None):
            normalized = " ".join(query.split()).lower()
            self.results = []
            if normalized.startswith("select count(*) filter") and "from agent_runs" in normalized:
                self.result = {
                    "queued": 2,
                    "running": 1,
                    "retry_wait": 1,
                    "waiting_approval": 4,
                    "stale_running": 1,
                    "failed_24h": 2,
                    "completed_24h": 7,
                    "billing_bound_runs": 3,
                    "last_run_at": now,
                }
            elif "count(distinct r.id) filter" in normalized:
                self.result = {
                    "archived_unfinished_runs": 4,
                    "archived_pending_approvals": 0,
                    "waiting_without_pending_approval": 4,
                }
            elif "from agent_trigger_events" in normalized:
                self.result = {"total": 8, "events_24h": 1, "last_event_at": now}
            elif "from agent_integrations" in normalized:
                self.result = {"active": 5, "inactive": 2}
            elif "from operatorcreditreservations" in normalized:
                self.result = {
                    "active_reservations": 1,
                    "reserved_credits": 6,
                    "charged_credits": 3,
                    "released_credits": 3,
                }
            elif "select r.id run_id" in normalized:
                self.result = None
                self.results = [
                    {
                        "run_id": "run-1",
                        "blueprint_id": "bp-1",
                        "business_id": "biz-1",
                        "status": "failed",
                        "attempt_count": 3,
                        "error_text": "provider timeout",
                        "updated_at": now,
                        "agent_name": "Проверка таблицы",
                        "business_name": "Riderra",
                    }
                ]
            else:
                raise AssertionError(f"Unexpected SQL: {query}")

        def fetchone(self):
            return self.result

        def fetchall(self):
            return self.results

    monkeypatch.setenv("AGENT_ASYNC_RUNS_ENABLED", "true")
    monkeypatch.setenv("AGENT_SCHEDULE_DISPATCH_ENABLED", "true")
    monkeypatch.setenv("AGENT_BETA_BUSINESS_IDS", "biz-1,biz-2,biz-3")

    runtime = agent_blueprints_api._admin_agent_runtime_overview(Cursor())

    assert runtime["flags"]["async_runs_enabled"] is True
    assert runtime["flags"]["schedule_dispatch_enabled"] is True
    assert runtime["flags"]["beta_businesses_count"] == 3
    assert runtime["runs"]["billing_bound_runs"] == 3
    assert runtime["billing"]["charged_credits"] == 3
    assert runtime["billing"]["active_reservations"] == 1
    assert runtime["scheduler"]["total_events"] == 8
    assert runtime["consistency"]["archived_unfinished_runs"] == 4
    assert runtime["recent_issues"][0]["error"] == "provider timeout"


def test_agent_beta_reconciliation_supersedes_archived_unfinished_runs():
    from scripts import migrate_agent_beta_state

    class Cursor:
        def __init__(self):
            self.rowcount = 0
            self.queries = []

        def execute(self, query, params=None):
            normalized = " ".join(query.split()).lower()
            self.queries.append(normalized)
            if normalized.startswith("update agent_approvals"):
                self.rowcount = 2
            elif normalized.startswith("update agent_runs"):
                self.rowcount = 4
            elif normalized.startswith("update agent_blueprints") and "suggested_execution_mode" in normalized:
                self.rowcount = 6141
            elif normalized.startswith("update agent_blueprints"):
                self.rowcount = 0
            else:
                raise AssertionError(f"Unexpected SQL: {query}")

    cursor = Cursor()
    result = migrate_agent_beta_state.apply_plan(cursor)

    assert result["approvals_superseded"] == 2
    assert result["archived_runs_superseded"] == 4
    assert result["suggested_modes_written"] == 6141
    archived_run_query = next(query for query in cursor.queries if query.startswith("update agent_runs"))
    assert "status = 'superseded'" in archived_run_query
    assert "b.status = 'archived'" in archived_run_query


def test_admin_agents_ui_exposes_runtime_health():
    source = Path("frontend/src/pages/dashboard/AdminPage.tsx").read_text(encoding="utf-8")

    assert "Работа агентов" in source
    assert "billing_bound_runs" in source
    assert "Списано кредитов" in source
    assert "downloadAgentSupportExport" in source
    assert "archived_unfinished_runs" in source
    assert "schedule_dispatch_enabled" in source
