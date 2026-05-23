import json
from pathlib import Path


def test_agent_blueprint_routes_are_owned_by_blueprint():
    import main

    expected = {
        "/api/agent-blueprints": {
            "GET": "agent_blueprints_api.list_agent_blueprints",
            "POST": "agent_blueprints_api.create_agent_blueprint",
        },
        "/api/agent-blueprints/<blueprint_id>": {
            "GET": "agent_blueprints_api.get_agent_blueprint",
        },
        "/api/agent-blueprints/<blueprint_id>/versions": {
            "POST": "agent_blueprints_api.create_agent_blueprint_version",
        },
        "/api/agent-blueprints/<blueprint_id>/runs": {
            "POST": "agent_blueprints_api.start_agent_blueprint_run",
        },
        "/api/agent-runs/<run_id>": {
            "GET": "agent_blueprints_api.get_agent_run",
        },
        "/api/agent-runs/<run_id>/approvals/<approval_id>/approve": {
            "POST": "agent_blueprints_api.approve_agent_run",
        },
        "/api/agent-runs/<run_id>/approvals/<approval_id>/reject": {
            "POST": "agent_blueprints_api.reject_agent_run",
        },
    }

    actual = {}
    for rule in main.app.url_map.iter_rules():
        methods = rule.methods - {"HEAD", "OPTIONS"}
        actual.setdefault(rule.rule, {})
        for method in methods:
            actual[rule.rule][method] = rule.endpoint

    for route, methods in expected.items():
        for method, endpoint in methods.items():
            assert actual.get(route, {}).get(method) == endpoint


def test_agent_blueprint_migration_creates_expected_tables():
    migration = Path("alembic_migrations/versions/20260523_add_agent_blueprint_layer.py").read_text(encoding="utf-8")
    for table_name in [
        "agent_blueprints",
        "agent_blueprint_versions",
        "agent_runs",
        "agent_run_steps",
        "agent_artifacts",
        "agent_approvals",
    ]:
        assert f"CREATE TABLE IF NOT EXISTS {table_name}" in migration
    assert "JSONB" in migration
    assert "20260523_001" in migration
    assert "20260521_001" in migration


def test_default_supervised_outreach_template_has_approval_gates():
    from services.agent_blueprint_runner import default_supervised_outreach_version_payload

    payload = default_supervised_outreach_version_payload()
    steps = payload["steps"]

    assert payload["capability_allowlist"] == ["outreach.send_batch"]
    assert [step["key"] for step in steps] == [
        "source_leads",
        "shortlist",
        "approve_shortlist",
        "draft_messages",
        "approve_drafts",
        "send_limited_batch",
        "record_outcomes",
    ]
    assert steps[2]["type"] == "approval"
    assert steps[4]["type"] == "approval"
    assert steps[5]["type"] == "capability"
    assert steps[5]["requires_approval"] is True


def test_agent_blueprint_api_guards_version_blueprint_mismatch():
    api_source = Path("src/api/agent_blueprints_api.py").read_text(encoding="utf-8")

    assert "VERSION_BLUEPRINT_MISMATCH" in api_source
    assert "_load_blueprint_version_for_blueprint" in api_source
    assert "build_agent_blueprint_orchestrator" in api_source


def test_outreach_send_batch_handler_queues_approved_drafts_without_external_dispatch(monkeypatch):
    from services import outreach_send_capability

    connection = FakeOutreachConnection(
        [
            {
                "id": "draft1",
                "lead_id": "lead1",
                "channel": "email",
                "email": "owner@example.com",
            }
        ]
    )
    monkeypatch.setattr(outreach_send_capability, "get_db_connection", lambda: connection)

    result = outreach_send_capability.handle_outreach_send_batch(
        {
            "tenant_id": "biz1",
            "actor": {"user_id": "user1"},
            "payload": {"draft_ids": ["draft1"], "daily_limit": 99},
        },
        {"user_id": "user1"},
    )

    output = result["result"]
    assert output["status"] == "queued_for_dispatch"
    assert output["queue_count"] == 1
    assert output["draft_ids"] == ["draft1"]
    assert output["daily_limit"] == 10
    assert output["external_dispatch_performed"] is False
    assert connection.committed is True
    assert any(item["kind"] == "batch" and item["status"] == "approved" for item in connection.inserted)
    assert any(item["kind"] == "queue" and item["draft_id"] == "draft1" for item in connection.inserted)


def test_runner_stops_on_first_approval_step():
    from services.agent_blueprint_runner import AgentBlueprintRunner, default_supervised_outreach_version_payload

    cursor = FakeCursor()
    cursor.tables["agent_blueprints"]["bp1"] = {
        "id": "bp1",
        "business_id": "biz1",
        "name": "Outreach",
        "category": "outreach",
    }
    cursor.tables["agent_blueprint_versions"]["ver1"] = {
        "id": "ver1",
        "blueprint_id": "bp1",
        "steps_json": default_supervised_outreach_version_payload()["steps"],
        "capability_allowlist_json": ["outreach.send_batch"],
    }

    result = AgentBlueprintRunner(cursor).start_run("ver1", {"limit": 30}, {"user_id": "user1"})

    assert result["success"] is True
    run = result["run"]
    assert run["status"] == "waiting_approval"
    assert [step["step_key"] for step in run["steps"]] == ["source_leads", "shortlist", "approve_shortlist"]
    assert run["approvals"][0]["approval_type"] == "shortlist"
    assert run["approvals"][0]["status"] == "pending"


class FakeCursor:
    def __init__(self):
        self.tables = {
            "agent_blueprints": {},
            "agent_blueprint_versions": {},
            "agent_runs": {},
            "agent_run_steps": {},
            "agent_artifacts": {},
            "agent_approvals": {},
        }
        self.last_result = None
        self.last_results = []

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        params = params or ()
        if normalized_query.startswith("select * from agent_blueprint_versions where id"):
            self.last_result = self.tables["agent_blueprint_versions"].get(params[0])
            return None
        if normalized_query.startswith("select * from agent_blueprints where id"):
            self.last_result = self.tables["agent_blueprints"].get(params[0])
            return None
        if normalized_query.startswith("insert into agent_runs"):
            self.tables["agent_runs"][params[0]] = {
                "id": params[0],
                "blueprint_id": params[1],
                "blueprint_version_id": params[2],
                "business_id": params[3],
                "status": params[4],
                "input_json": json.loads(params[5]),
                "output_json": json.loads(params[6]),
                "created_by_user_id": params[7],
            }
            return None
        if normalized_query.startswith("select * from agent_runs where id"):
            self.last_result = self.tables["agent_runs"].get(params[0])
            return None
        if normalized_query.startswith("select step_index from agent_run_steps"):
            run_id = params[0]
            self.last_results = [
                {"step_index": step["step_index"]}
                for step in self.tables["agent_run_steps"].values()
                if step["run_id"] == run_id and step["status"] in {"completed", "rejected"}
            ]
            return None
        if normalized_query.startswith("insert into agent_run_steps"):
            self.tables["agent_run_steps"][params[0]] = {
                "id": params[0],
                "run_id": params[1],
                "step_index": params[2],
                "step_key": params[3],
                "step_type": params[4],
                "status": params[5],
                "input_json": json.loads(params[6]),
                "output_json": json.loads(params[7]),
            }
            return None
        if normalized_query.startswith("insert into agent_artifacts"):
            self.tables["agent_artifacts"][params[0]] = {
                "id": params[0],
                "run_id": params[1],
                "step_id": params[2],
                "artifact_type": params[3],
                "title": params[4],
                "payload_json": json.loads(params[5]),
            }
            return None
        if normalized_query.startswith("insert into agent_approvals"):
            self.tables["agent_approvals"][params[0]] = {
                "id": params[0],
                "run_id": params[1],
                "step_id": params[2],
                "status": "pending",
                "approval_type": params[3],
                "title": params[4],
                "payload_json": json.loads(params[5]),
                "requested_by_user_id": params[6],
            }
            return None
        if normalized_query.startswith("update agent_runs set status = 'waiting_approval'"):
            self.tables["agent_runs"][params[0]]["status"] = "waiting_approval"
            return None
        if normalized_query.startswith("select * from agent_run_steps"):
            run_id = params[0]
            self.last_results = sorted(
                [step for step in self.tables["agent_run_steps"].values() if step["run_id"] == run_id],
                key=lambda item: item["step_index"],
            )
            return None
        if normalized_query.startswith("select * from agent_artifacts"):
            run_id = params[0]
            self.last_results = [item for item in self.tables["agent_artifacts"].values() if item["run_id"] == run_id]
            return None
        if normalized_query.startswith("select * from agent_approvals"):
            run_id = params[0]
            self.last_results = [item for item in self.tables["agent_approvals"].values() if item["run_id"] == run_id]
            return None
        raise AssertionError(f"Unhandled SQL in fake cursor: {query}")

    def fetchone(self):
        return self.last_result

    def fetchall(self):
        return self.last_results


class FakeOutreachConnection:
    def __init__(self, draft_rows):
        self.cursor_instance = FakeOutreachCursor(draft_rows)
        self.inserted = self.cursor_instance.inserted
        self.committed = False
        self.rolled_back = False
        self.closed = False

    def cursor(self):
        return self.cursor_instance

    def commit(self):
        self.committed = True

    def rollback(self):
        self.rolled_back = True

    def close(self):
        self.closed = True


class FakeOutreachCursor:
    def __init__(self, draft_rows):
        self.draft_rows = draft_rows
        self.last_result = None
        self.last_results = []
        self.inserted = []

    def execute(self, query, params=None):
        normalized_query = " ".join(query.split()).lower()
        params = params or ()
        if normalized_query.startswith("select count(*) as cnt"):
            self.last_result = {"cnt": 0}
            return None
        if normalized_query.startswith("select d.id"):
            self.last_results = self.draft_rows
            return None
        if normalized_query.startswith("insert into outreachsendbatches"):
            self.inserted.append(
                {
                    "kind": "batch",
                    "id": params[0],
                    "daily_limit": params[1],
                    "status": params[2],
                    "created_by": params[3],
                    "approved_by": params[4],
                }
            )
            return None
        if normalized_query.startswith("insert into outreachsendqueue"):
            self.inserted.append(
                {
                    "kind": "queue",
                    "id": params[0],
                    "batch_id": params[1],
                    "lead_id": params[2],
                    "draft_id": params[3],
                    "channel": params[4],
                    "delivery_status": params[5],
                }
            )
            return None
        if normalized_query.startswith("update prospectingleads"):
            self.inserted.append(
                {
                    "kind": "lead_update",
                    "status": params[0],
                    "pipeline_status": params[1],
                    "lead_id": params[2],
                    "business_id": params[3],
                }
            )
            return None
        raise AssertionError(f"Unhandled SQL in fake outreach cursor: {query}")

    def fetchone(self):
        return self.last_result

    def fetchall(self):
        return self.last_results
