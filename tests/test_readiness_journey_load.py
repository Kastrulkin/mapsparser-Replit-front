import hashlib
import importlib.util
import json
from pathlib import Path
import argparse
import os
import signal
import subprocess
import sys
from types import ModuleType

import pytest


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "readiness_journey_load.py"
SPEC = importlib.util.spec_from_file_location("readiness_journey_load", MODULE_PATH)
load = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = load
SPEC.loader.exec_module(load)


def sample(target, step):
    return load.RequestSample(target, step, 200, 1.0, True)


def test_parent_preparation_imports_source_in_a_fresh_guard_only_process(tmp_path):
    program = """
import sys
from pathlib import Path
sys.path.insert(0, sys.argv[1])
import readiness_journey_load

class Cursor:
    def execute(self, *_args):
        pass
    def close(self):
        pass

class Connection:
    def cursor(self):
        return Cursor()
    def commit(self):
        pass
    def close(self):
        pass

readiness_journey_load.readiness_journey_benchmark.psycopg2.connect = lambda *_args: Connection()
targets = readiness_journey_load.prepare_targets('unreachable-fixture-only', 2)
assert len(targets) == 2
assert targets[0]['user_id'] != targets[1]['user_id']
import auth_system
assert Path(auth_system.__file__).resolve() == readiness_journey_load.ROOT / 'src' / 'auth_system.py'
"""
    # Do not inherit pytest/conftest's application import path. Preserve only
    # the optional no-egress guard, never the parent application's src path.
    guard_entry = os.environ.get("PYTHONPATH", "").split(os.pathsep)[0]
    environment = {
        "PATH": os.environ.get("PATH", ""),
        "PYTHON_DOTENV_DISABLED": "1",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONPATH": guard_entry if guard_entry and (Path(guard_entry) / "sitecustomize.py").is_file() else "",
    }
    result = subprocess.run(
        [sys.executable, "-c", program, str(MODULE_PATH.parent)],
        cwd=tmp_path,
        env=environment,
        capture_output=True,
        text=True,
        timeout=15,
        check=False,
    )
    assert result.returncode == 0, result.stderr


def test_limits_target_identity_and_pair_waves_are_strict():
    load.validate_limits(2, 1, 1)
    with pytest.raises(ValueError):
        load.validate_limits(1, 1, 1)
    with pytest.raises(ValueError):
        load.validate_limits(9, 1, 1)
    targets = [
        {"user_id": "u1", "business_id": "b1", "service_id": "s1", "email": "u1@benchmark.invalid"},
        {"user_id": "u2", "business_id": "b2", "service_id": "s2", "email": "u2@benchmark.invalid"},
        {"user_id": "u3", "business_id": "b3", "service_id": "s3", "email": "u3@benchmark.invalid"},
    ]
    assert [len(wave) for wave in load.pair_waves(targets)] == [2, 1]
    assert load.validate_targets(targets, 3) == targets
    targets[2]["user_id"] = "u1"
    with pytest.raises(ValueError):
        load.validate_targets(targets, 3)


def test_guard_requires_actual_loaded_canonical_origin_and_hash(tmp_path, monkeypatch):
    guard = tmp_path / "canonical" / "sitecustomize.py"
    guard.parent.mkdir()
    guard.write_text("# no external network\n", encoding="utf-8")
    loaded = ModuleType("sitecustomize")
    loaded.__file__ = str(guard)
    monkeypatch.setitem(sys.modules, "sitecustomize", loaded)
    sha256 = hashlib.sha256(guard.read_bytes()).hexdigest()
    assert load.guard_provenance(str(guard), sha256)["sha256"] == sha256
    with pytest.raises(ValueError):
        load.guard_provenance(str(guard), "0" * 64)
    other = tmp_path / "other" / "sitecustomize.py"
    other.parent.mkdir()
    other.write_text("# guard\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load.guard_provenance(str(other), hashlib.sha256(other.read_bytes()).hexdigest())


def test_create_race_failure_never_authorizes_cleanup(monkeypatch):
    name = "localos_readiness_load_0123456789abcdef0123456789abcdef"
    monkeypatch.setattr(load, "database_absent", lambda *_args: False)
    with pytest.raises(ValueError):
        load.create_owned_database("postgresql://owner@127.0.0.1:35418/db", name)
    result = load.cleanup_owned_database("postgresql://owner@127.0.0.1:35418/db", name, False)
    assert result["skipped"] == "not_created_by_this_invocation"


def test_watchdog_sigterm_then_sigkill_reaps_before_cleanup(monkeypatch, tmp_path):
    class Child:
        pid = 735
        returncode = -9
        calls = 0

        def communicate(self, timeout=None):
            self.calls += 1
            if self.calls < 3:
                raise load.subprocess.TimeoutExpired("child", timeout)
            return "application print ignored", ""

    child = Child()
    signals = []
    monkeypatch.setattr(load.subprocess, "Popen", lambda *_args, **_kwargs: child)
    monkeypatch.setattr(load.os, "killpg", lambda pid, value: signals.append((pid, value)))
    config = {"result_path": str(tmp_path / "result.json")}
    rows, resources, termination = load.run_child_process(config, 1)
    assert resources == {}
    assert termination == "sigkill"
    assert signals == [(735, signal.SIGTERM), (735, signal.SIGKILL)]
    assert rows[0].error == "child_exit:-9"
    assert child.calls == 3


def test_child_mode_is_executable_without_parent_output_argument(monkeypatch, tmp_path):
    result_path = tmp_path / "child.json"
    config = {"result_path": str(result_path)}
    monkeypatch.setattr(load, "child_payload", lambda value: {"samples": [], "resources": {"tested": True}})
    monkeypatch.setenv(load.CONFIG_ENV, json.dumps(config))
    monkeypatch.setattr(sys, "argv", [str(MODULE_PATH), "--child"])
    assert load.main() == 0
    assert json.loads(result_path.read_text(encoding="utf-8"))["resources"] == {"tested": True}


def test_child_command_carries_no_database_dsn_in_argv(monkeypatch, tmp_path):
    seen = {}

    class Child:
        pid = 1
        returncode = 0

        def communicate(self, timeout=None):
            return "ignored", "ignored"

    def popen(command, **kwargs):
        seen["command"] = command
        seen["environment"] = kwargs["env"]
        Path(json.loads(kwargs["env"][load.CONFIG_ENV])["result_path"]).write_text(
            json.dumps({"samples": [], "resources": {}}), encoding="utf-8"
        )
        return Child()

    monkeypatch.setattr(load.subprocess, "Popen", popen)
    config = {
        "database_url": "postgresql://owner@127.0.0.1:35418/secret_db",
        "pythonpath": "/private/tmp/canonical-guard",
        "result_path": str(tmp_path / "child.json"),
    }
    load.run_child_process(config, 1)
    assert "secret_db" not in " ".join(seen["command"])
    assert "secret_db" in seen["environment"][load.CONFIG_ENV]
    assert seen["environment"]["PYTHONPATH"] == "/private/tmp/canonical-guard"


def test_coverage_requires_exact_login_me_and_business_counts():
    rows = [sample(0, "login"), sample(0, "login"), sample(0, "me"), sample(0, "business_data")]
    failures = load.coverage_failures(rows, 2, 2)
    errors = {row.error for row in failures}
    assert "login:expected=1:observed=2" in errors
    assert "me:expected=2:observed=1" in errors
    assert "business_data:expected=2:observed=1" in errors
    assert "login:expected=1:observed=0" in errors


def test_semantic_status_200_checks_reject_wrong_identity_and_missing_service():
    assert load.identity_from_payload({"user": {"id": "u1"}}) == "u1"
    assert load.identity_from_payload({"id": "u2"}) == "u2"
    assert load.identity_from_payload({}) == ""
    rows = [sample(0, "login"), sample(0, "me"), sample(0, "business_data")]
    summary = load.summarize(rows)
    assert summary["login"]["success_count"] == 1
    assert summary["business_data"]["p99_note"].startswith("exploratory")


def test_actual_business_request_semantics_reject_wrong_mixed_missing_and_non_200():
    class Response:
        def __init__(self, status_code, payload):
            self.status_code = status_code
            self.payload = payload

        def get_json(self):
            return self.payload

    target = {"business_id": "b1", "service_id": "s1"}
    valid = lambda payload: load.valid_business_payload(payload, target)
    correct = {"business": {"id": "b1"}, "services": [{"id": "s1"}]}
    wrong_business = {"business": {"id": "other"}, "services": [{"id": "s1"}]}
    mixed_services = {"business": {"id": "b1"}, "services": [{"id": "s1"}, {"id": "foreign"}]}
    missing_service = {"business": {"id": "b1"}, "services": []}
    assert load.request_sample(0, "business_data", lambda: Response(200, correct), valid)[0].success
    assert not load.request_sample(0, "business_data", lambda: Response(200, wrong_business), valid)[0].success
    assert not load.request_sample(0, "business_data", lambda: Response(200, mixed_services), valid)[0].success
    assert not load.request_sample(0, "business_data", lambda: Response(200, missing_service), valid)[0].success
    assert not load.request_sample(0, "business_data", lambda: Response(500, correct), valid)[0].success


def test_parent_failure_writes_sanitized_json_and_nonzero(monkeypatch, tmp_path):
    output = tmp_path / "failure.json"
    monkeypatch.setattr(load, "parent_run", lambda _args: load.parent_failure("ValueError", {"skipped": "not_started"}))
    monkeypatch.setattr(sys, "argv", [str(MODULE_PATH), "--execute", "--output", str(output)])
    assert load.main() == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["valid"] is False
    assert payload["invalid_reasons"] == ["ValueError"]


def test_parent_marks_child_failure_and_missing_coverage_invalid(monkeypatch, tmp_path):
    guard = tmp_path / "guard" / "sitecustomize.py"
    guard.parent.mkdir()
    guard.write_text("# guard\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(guard.parent))
    monkeypatch.setenv(load.DEFAULT_DSN_ENV, "postgresql://owner@127.0.0.1:35418/readiness_source")
    monkeypatch.setattr(load.readiness_journey_measure, "guarded_dsn", lambda value: value)
    monkeypatch.setattr(load, "data_directory_identity", lambda *_args: "/private/tmp/readiness-data")
    monkeypatch.setattr(load, "create_owned_database", lambda *_args: "postgresql://owner@127.0.0.1:35418/readiness_child")
    monkeypatch.setattr(load.readiness_journey_benchmark, "remove_external_provider_environment", lambda: None)
    monkeypatch.setattr(load.readiness_journey_benchmark, "migrate", lambda *_args: None)
    monkeypatch.setattr(load, "prepare_targets", lambda *_args: [
        {"user_id": "u1", "business_id": "b1", "service_id": "s1", "email": "u1@benchmark.invalid"},
        {"user_id": "u2", "business_id": "b2", "service_id": "s2", "email": "u2@benchmark.invalid"},
    ])
    monkeypatch.setattr(
        load,
        "run_child_process",
        lambda *_args: ([load.RequestSample(0, "login", 500, 1.0, False, "semantic_response_mismatch")], {"before_timed_phase": {}, "after_timed_phase": {}}, "completed"),
    )
    monkeypatch.setattr(load, "cleanup_owned_database", lambda *_args: {"removed": True})
    payload = load.parent_run(argparse.Namespace(targets=2, repetitions=1, timeout=1, output=str(tmp_path / "out.json")))
    assert payload["valid"] is False
    assert any(reason.startswith("failed:0:login") for reason in payload["invalid_reasons"])
    assert any(reason.startswith("failed:1:coverage") for reason in payload["invalid_reasons"])
