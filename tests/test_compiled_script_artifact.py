import importlib.util
import errno
import threading
from pathlib import Path

import pytest

from services.compiled_script_artifact import build_artifact, validate_artifact
from services.compiled_script_runtime import CompiledRuntimeUnavailable, execute_in_attested_sandbox, execute_pilot


SOURCE = '''def process(rows):
    return rows
'''
MANIFEST = {
    "kind": "localos.sheet_validate_dedupe_report.v1",
    "input_schema": {"type": "object", "properties": {"rows": {"type": "array", "items": {"type": "object", "properties": {}, "required": [], "additionalProperties": True}}}, "required": []},
    "output_schema": {"type": "object", "properties": {}, "required": []},
    "required_columns": ["email", "amount"],
    "dedupe_columns": ["email"],
    "runtime_version": "python-3.12-restricted-v1",
    "dependencies": [],
    "runner_image_digest": "sha256:" + "a" * 64,
}
FIXTURES = [{"input": {"rows": [{"email": "a@example.com", "amount": "10"}]}, "expected": {}, "source": "user"}]


def test_preview_is_deterministic_and_has_no_runtime_ai():
    artifact = build_artifact(SOURCE, MANIFEST, FIXTURES)
    result = execute_pilot(artifact, {"rows": [{"email": "a@example.com", "amount": "10"}, {"email": "A@example.com", "amount": "12"}, {"amount": "2"}]})
    assert result["runtime_ai_calls"] == 0
    assert result["report"] == {"received": 3, "accepted": 1, "duplicates": 1, "invalid": 1, "errors": [{"row": 3, "code": "required", "columns": ["email"]}]}


def test_artifact_hash_detects_tampering():
    artifact = build_artifact(SOURCE, MANIFEST, FIXTURES)
    artifact["source"] = "print('changed')"
    checked = validate_artifact(artifact)
    assert checked["valid"] is False
    assert any(item["code"] == "hash_mismatch" for item in checked["errors"])


def test_forbidden_runtime_access_is_rejected():
    with pytest.raises(ValueError):
        build_artifact("import subprocess\nsubprocess.run([])", MANIFEST, FIXTURES)


def test_production_execution_fails_closed_without_attested_runtime(monkeypatch):
    monkeypatch.delenv("LOCALOS_COMPILED_SCRIPT_SANDBOX", raising=False)
    artifact = build_artifact(SOURCE, MANIFEST, FIXTURES)
    with pytest.raises(CompiledRuntimeUnavailable):
        execute_in_attested_sandbox(artifact, {"rows": []})


def test_legacy_runner_cannot_fall_back_to_dsl_for_compiled_version():
    from services.agent_blueprint_runner import AgentBlueprintRunner
    from tests.agent_blueprint_fakes import FakeCursor

    cursor = FakeCursor()
    cursor.tables["agent_blueprint_versions"]["version-1"] = {
        "id": "version-1",
        "blueprint_id": "blueprint-1",
        "compiled_state": "approved",
    }
    result = AgentBlueprintRunner(cursor).start_run("version-1", {}, {"user_id": "user-1"})
    assert result == {"success": False, "error": "compiled_script_requires_dedicated_runtime"}


def _runner_module():
    path = Path(__file__).parents[1] / "docker" / "compiled-script-runner" / "server.py"
    spec = importlib.util.spec_from_file_location("compiled_script_runner_test", path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def test_isolated_runner_executes_approved_source_not_oracle():
    runner = _runner_module()
    source = "def process(input_payload):\n    return {'value': input_payload.get('value', 0) + 7}\n"
    assert runner.run_source(source, {"value": 3}) == {"value": 10}


def test_actual_source_divergence_is_visible_against_pilot_oracle():
    runner = _runner_module()
    artifact = build_artifact("def process(input_payload):\n    return {'rows': []}\n", MANIFEST, FIXTURES)
    actual = runner.run_source(artifact["source"], {"rows": [{"email": "a@example.com", "amount": "10"}]})
    assert actual != execute_pilot(artifact, {"rows": [{"email": "a@example.com", "amount": "10"}]})


def test_introspection_is_rejected_before_runner():
    with pytest.raises(ValueError):
        build_artifact("def process(input_payload):\n    return ().__class__\n", MANIFEST, FIXTURES)


def test_authenticated_runner_transport_executes_actual_source(monkeypatch):
    runner = _runner_module()
    secret = "s" * 32
    digest = "sha256:" + "a" * 64
    runner.SECRET, runner.IMAGE_DIGEST = secret, digest
    try:
        server = runner.HTTPServer(("127.0.0.1", 0), runner.Handler)
    except PermissionError as error:
        if error.errno == errno.EPERM:
            pytest.skip("sandbox blocks local socket binding; covered by Docker integration test")
        raise
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_SHARED_SECRET", secret)
    monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST", digest)
    monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_URL", "http://127.0.0.1:%d" % server.server_port)
    manifest = {"kind": "localos.python_transform.v1", "input_schema": {"type": "object", "properties": {"number": {"type": "integer"}}, "required": []}, "output_schema": {"type": "object", "properties": {"changed": {"type": "integer"}}, "required": ["changed"]}, "runtime_version": "python-3.12-restricted-v1", "dependencies": [], "runner_image_digest": digest}
    artifact = build_artifact("def process(input_payload):\n    return {'changed': input_payload.get('number', 0) + 9}\n", manifest, [{"input": {"number": 1}, "expected": {"changed": 10}, "source": "user"}])
    try:
        assert execute_in_attested_sandbox(artifact, {"number": 2})["changed"] == 11
    finally:
        server.shutdown()
        thread.join(timeout=2)


def test_isolated_runner_enforces_wall_time_limit():
    runner = _runner_module()
    with pytest.raises(Exception):
        runner.run_source("def process(input_payload):\n    while True:\n        pass\n", {})


def test_runner_defense_rejects_import_and_dunder_introspection():
    runner = _runner_module()
    with pytest.raises(ValueError):
        runner.run_source("import os\ndef process(input_payload):\n    return os.getenv('x')\n", {})
    with pytest.raises(ValueError):
        runner.run_source("def process(input_payload):\n    return ().__class__\n", {})
