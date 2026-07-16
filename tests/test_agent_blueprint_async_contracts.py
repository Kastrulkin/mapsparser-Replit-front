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
        },
    }
    steps = [{"type": "capability", "capability": "content_plan.item.create_draft"}]
    public_schema = effective_agent_input_schema(schema, steps)

    assert "business_id" not in public_schema["properties"]
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
    assert "waitForAgentRun" in frontend_source
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
