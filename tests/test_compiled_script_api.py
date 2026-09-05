import json

from flask import Flask


class RecordingCursor:
    def __init__(self):
        self.calls = []
        self.row = {"next_version": 1}

    def execute(self, query, params=None):
        self.calls.append((query, params))

    def fetchone(self):
        return self.row


class Database:
    def __init__(self):
        self.conn = self
    def cursor(self):
        return RecordingCursor()
    def commit(self):
        return None
    def rollback(self):
        return None
    def close(self):
        return None


def test_public_insert_version_strips_forged_compiled_fields(monkeypatch):
    from api import agent_blueprints_api
    cursor = RecordingCursor()
    cursor.row = {"next_version": 1}
    original_fetchone = cursor.fetchone
    calls = 0
    def fetchone():
        nonlocal calls
        calls += 1
        return {"next_version": 1} if calls == 1 else {"id": "v1", "compiled_state": "legacy"}
    cursor.fetchone = fetchone
    payload = {"goal": "x", "steps": [], "compiled_state": "approved", "compiled_artifact": {"source": "bad"}, "compiled_artifact_hash": "sha256:forged"}
    version = agent_blueprints_api._insert_version(cursor, "b1", payload, {"user_id": "u1"})
    insert_params = cursor.calls[1][1]
    assert insert_params[-4] == "{}"
    assert insert_params[-3] is None
    assert insert_params[-2] == "legacy"
    assert version["compiled_state"] == "legacy"


def test_compile_keeps_request_fixtures_and_forces_model_fixtures_generator(monkeypatch):
    from api import agent_blueprints_api
    app = Flask(__name__)
    db = Database()
    captured = {}
    user_fixture = {"input": {"number": 1}, "expected": {"value": 8}, "source": "user"}
    generated_fixture = {"input": {"number": 2}, "expected": {"value": 9}, "source": "user"}
    monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST", "sha256:" + "a" * 64)
    monkeypatch.setattr(agent_blueprints_api, "DatabaseManager", lambda: db)
    monkeypatch.setattr(agent_blueprints_api, "_require_auth", lambda: ({"user_id": "u1"}, None))
    monkeypatch.setattr(agent_blueprints_api, "_require_blueprint_access", lambda cursor, blueprint_id, user: ({"id": blueprint_id, "business_id": "biz", "metadata_json": {}}, None))
    monkeypatch.setattr(agent_blueprints_api, "generate_candidate_from_description", lambda *args, **kwargs: {"status": "ready", "candidate": {"source": "def process(input_payload):\n    return {'value': input_payload.get('number', 0) + 7}\n", "manifest": {"kind": "localos.python_transform.v1", "input_schema": {"type": "object", "properties": {}, "required": []}, "output_schema": {"type": "object", "properties": {}, "required": []}, "runtime_version": "python-3.12-restricted-v1", "dependencies": []}, "fixtures": [generated_fixture]}})
    monkeypatch.setattr(agent_blueprints_api, "_resolve_candidate_version", lambda cursor, blueprint: {})
    def insert(cursor, blueprint_id, payload, user, **kwargs):
        captured["payload"] = payload
        captured["trusted"] = kwargs.get("trusted_compiled")
        return {"id": "v1", **payload}
    monkeypatch.setattr(agent_blueprints_api, "_insert_version", insert)
    with app.test_request_context("/api/agent-blueprints/b1/compiled-script/compile", method="POST", json={"description": "transform", "fixtures": [user_fixture]}):
        response, status = agent_blueprints_api.compile_agent_blueprint_script("b1")
    assert status == 201
    assert response.get_json()["success"] is True
    fixtures = captured["payload"]["compiled_artifact"]["fixtures"]
    assert fixtures[0] == user_fixture
    assert fixtures[1]["source"] == "generator"
    assert captured["trusted"] is True


def test_runtime_rejects_runner_digest_change(monkeypatch):
    from services.compiled_script_artifact import build_artifact
    from services.compiled_script_runtime import CompiledRuntimeUnavailable, execute_in_attested_sandbox
    manifest = {"kind": "localos.python_transform.v1", "input_schema": {"type": "object", "properties": {}, "required": []}, "output_schema": {"type": "object", "properties": {}, "required": []}, "runtime_version": "python-3.12-restricted-v1", "dependencies": [], "runner_image_digest": "sha256:" + "a" * 64}
    artifact = build_artifact("def process(input_payload):\n    return {}\n", manifest, [{"input": {}, "expected": {}, "source": "user"}])
    monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_URL", "http://runner")
    monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST", "sha256:" + "b" * 64)
    monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_SHARED_SECRET", "s" * 32)
    try:
        execute_in_attested_sandbox(artifact, {})
    except CompiledRuntimeUnavailable as error:
        assert str(error) == "compiled_script_runner_digest_changed"
    else:
        raise AssertionError("runtime accepted changed runner digest")


def test_real_generator_validation_uses_deployment_digest_not_model_guess():
    from services.compiled_script_artifact import generate_candidate_from_description
    source = "def process(input_payload):\n    return {'value': 8}\n"
    manifest = {"kind":"localos.python_transform.v1", "runtime_version":"python-3.12-restricted-v1",
        "dependencies":[], "input_schema":{"type":"object"},
        "output_schema":{"type":"object","properties":{"value":{"type":"integer"}},"required":["value"]}}
    result = generate_candidate_from_description("Report",business_id="biz",user_id="u1",
        runner_image_digest="sha256:"+"a"*64,
        generator=lambda _prompt: json.dumps({"source":source,"manifest":manifest,
            "fixtures":[{"input":{},"expected":{"value":8},"source":"user"}]}))
    assert result["status"] == "ready"
    assert result["candidate"]["manifest"]["runner_image_digest"] == "sha256:"+"a"*64
    assert result["candidate"]["fixtures"][0]["source"] == "generator"


def test_rollback_previously_active_compiled_version_rechecks_runtime(monkeypatch):
    from api import agent_blueprints_api
    from services.compiled_script_artifact import build_artifact
    manifest = {"kind":"localos.python_transform.v1", "runtime_version":"python-3.12-restricted-v1",
        "dependencies":[], "input_schema":{"type":"object"},"output_schema":{"type":"object"},
        "runner_image_digest":"sha256:"+"a"*64}
    artifact = build_artifact("def process(input_payload):\n    return {}",manifest,[{"input":{},"expected":{},"source":"user"}])
    monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST","sha256:"+"b"*64)
    monkeypatch.setattr(agent_blueprints_api,"DatabaseManager",Database)
    monkeypatch.setattr(agent_blueprints_api,"_require_auth",lambda: ({"user_id":"u1"},None))
    monkeypatch.setattr(agent_blueprints_api,"_require_blueprint_access",lambda *_args: ({"id":"b1"},None))
    monkeypatch.setattr(agent_blueprints_api,"_load_blueprint_version_for_blueprint",lambda *_args: {"id":"v1","compiled_state":"approved","compiled_artifact_json":artifact})
    monkeypatch.setattr(agent_blueprints_api,"_resolve_active_version",lambda *_args: {"id":"v2"})
    monkeypatch.setattr(agent_blueprints_api,"_version_was_active_before",lambda *_args: True)
    def no_activation(*_args):
        raise AssertionError("Obsolete runtime version must not be activated")
    monkeypatch.setattr(agent_blueprints_api,"_remember_active_version",no_activation)
    app = Flask(__name__)
    with app.test_request_context(method="POST",json={}):
        response, status = agent_blueprints_api.rollback_agent_blueprint_version("b1","v1")
    assert status == 409
    assert response.get_json()["code"] == "COMPILED_ROLLBACK_RUNTIME_MISMATCH"


def test_execution_flag_blocks_shared_queue_and_already_queued_worker(monkeypatch):
    from services import agent_run_queue, agent_blueprint_runner
    monkeypatch.setenv("COMPILED_SCRIPT_EXECUTE_ENABLED","false")
    version = {"id":"v1","blueprint_id":"b1","compiled_state":"approved"}
    assert agent_run_queue._validate_pinned_version({"id":"b1"},version) == "compiled script execution is disabled"
    assert agent_run_queue._validate_pinned_version({"id":"b1"},{**version,"compiled_state":"legacy"}) == ""
    class StoppedRun:
        failures = []
        def _fail_run(self, run_id, error):
            self.failures.append((run_id,error))
        def load_run(self, run_id):
            return {"id":run_id,"status":"failed"}
    def no_sandbox(*_args):
        raise AssertionError("Disabled execution must not reach sandbox")
    monkeypatch.setattr(agent_blueprint_runner,"execute_in_attested_sandbox",no_sandbox)
    run = StoppedRun()
    result = agent_blueprint_runner.AgentBlueprintRunner._execute_queued_compiled_script(run,"r1",version)
    assert result["error"] == "compiled_execution_disabled"
    assert run.failures == [("r1","compiled script execution is disabled")]
