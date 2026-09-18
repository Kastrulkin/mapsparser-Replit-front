import hashlib
import importlib.util
import json
from pathlib import Path
import signal
import sys
from types import ModuleType

import pytest


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "readiness_query_plans.py"
SPEC = importlib.util.spec_from_file_location("readiness_query_plans", MODULE_PATH)
plans = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = plans
SPEC.loader.exec_module(plans)


def test_owned_namespace_and_statement_categories_are_bounded():
    assert plans.exact_owned_name("localos_readiness_queryproof_0123456789abcdef0123456789abcdef")
    assert not plans.exact_owned_name("localos_readiness_load_0123456789abcdef0123456789abcdef")
    assert plans.statement_category(" SELECT 1") == "read"
    assert plans.statement_category("ALTER TABLE users ADD COLUMN x text") == "ddl_or_write"
    assert plans.statement_category("VACUUM") == "other"


def test_only_three_constant_query_specs_have_stable_source_hashes():
    target = {"user_id": "u", "business_id": "b"}
    assert [item[0] for item in plans.QUERY_SPECS] == [
        "auth_me_business_access_representative", "business_data_services", "business_data_cards",
    ]
    for _name, query, parameters in plans.QUERY_SPECS:
        assert parameters(target)
        assert len(plans.statement_hash(query)) == 64
        assert "EXPLAIN" not in query.upper()


def test_guard_requires_loaded_canonical_origin_and_exact_hash(tmp_path, monkeypatch):
    guard = tmp_path / "guard" / "sitecustomize.py"
    guard.parent.mkdir()
    guard.write_text("# canonical\n", encoding="utf-8")
    module = ModuleType("sitecustomize")
    module.__file__ = str(guard)
    monkeypatch.setitem(sys.modules, "sitecustomize", module)
    digest = hashlib.sha256(guard.read_bytes()).hexdigest()
    assert plans.loaded_guard(str(guard), digest)["sha256"] == digest
    with pytest.raises(ValueError):
        plans.loaded_guard(str(guard), "0" * 64)


def test_cleanup_skips_when_create_never_returned():
    result = plans.cleanup_owned_database(
        "postgresql://owner@127.0.0.1:35418/readiness_source",
        "localos_readiness_queryproof_0123456789abcdef0123456789abcdef",
        False,
    )
    assert result["skipped"] == "not_created_by_this_invocation"


def test_explain_uses_constant_sql_and_fixture_parameters(monkeypatch):
    seen = []

    class Cursor:
        def execute(self, query, params=None):
            seen.append((query, params))

        def fetchone(self):
            return [[{"Plan": {"Node Type": "Index Scan"}}]]

        def close(self):
            return None

    class Connection:
        def cursor(self):
            return Cursor()

        def close(self):
            return None

    monkeypatch.setattr(plans.psycopg2, "connect", lambda *_args, **_kwargs: Connection())
    target = {"user_id": "owner", "business_id": "business"}
    result = plans.explain_plans("postgresql://owner@127.0.0.1:35418/readiness_proof", target)
    assert len(result) == 3
    explained = seen[-3:]
    assert all(query.startswith("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON)") for query, _params in explained)
    assert explained[0][1] == ("owner", "owner", "owner", "owner")
    assert explained[1][1] == ("business",)
    assert explained[2][1] == ("business",)


def test_route_count_categories_keep_ddl_separate_from_reads():
    events = [
        plans.QueryEvent("dashboard", "read", "one"),
        plans.QueryEvent("dashboard", "ddl_or_write", "two"),
        plans.QueryEvent("dashboard", "other", "three"),
    ]
    assert plans.count_events(events) == {"all": 3, "read": 1, "ddl_or_write": 1, "other": 1}


def test_validity_requires_exact_plans_consistent_counts_and_cleanup():
    plan_rows = [{"name": name, "plan": [{}]} for name, _query, _parameters in plans.QUERY_SPECS]
    counts = {
        "auth_me": {"all": 2, "read": 2, "ddl_or_write": 0, "other": 0},
        "business_data": {"all": 4, "read": 3, "ddl_or_write": 1, "other": 0},
    }
    assert plans.validity(counts, plan_rows, {"removed": True}, "completed") == []
    assert "missing_or_malformed_plan_set" in plans.validity(counts, plan_rows[:-1], {"removed": True}, "completed")
    bad = dict(counts)
    bad["auth_me"] = {"all": 2, "read": 1, "ddl_or_write": 0, "other": 0}
    assert "inconsistent_route_counts:auth_me" in plans.validity(bad, plan_rows, {"removed": True}, "completed")


def test_main_writes_structured_failure_and_exit_one(monkeypatch, tmp_path):
    output = tmp_path / "failure.json"
    monkeypatch.setattr(plans, "run", lambda _args: (_ for _ in ()).throw(ValueError("guard")))
    monkeypatch.setattr(sys, "argv", [str(MODULE_PATH), "--execute", "--output", str(output)])
    assert plans.main() == 1
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["valid"] is False
    assert payload["invalid_reasons"] == ["ValueError"]


def test_watchdog_terms_kills_and_reaps_child(monkeypatch, tmp_path):
    class Child:
        pid = 41
        returncode = -9
        calls = 0

        def communicate(self, timeout=None):
            self.calls += 1
            if self.calls < 3:
                raise plans.subprocess.TimeoutExpired("proof", timeout)
            return "", ""

    child = Child()
    calls = []
    monkeypatch.setattr(plans.subprocess, "Popen", lambda *_args, **_kwargs: child)
    monkeypatch.setattr(plans.os, "killpg", lambda pid, value: calls.append((pid, value)))
    with pytest.raises(RuntimeError):
        plans.run_child_process({"result_path": str(tmp_path / "none.json"), "pythonpath": ""}, 1)
    assert calls == [(41, signal.SIGTERM), (41, signal.SIGKILL)]
    assert child.calls == 3


def test_post_create_failure_cleans_once_and_preserves_cleanup(monkeypatch, tmp_path):
    monkeypatch.setenv(plans.DEFAULT_DSN_ENV, "postgresql://owner@127.0.0.1:35418/readiness_source")
    guard = tmp_path / "guard" / "sitecustomize.py"
    guard.parent.mkdir()
    guard.write_text("# guard\n", encoding="utf-8")
    monkeypatch.setenv("PYTHONPATH", str(guard.parent))
    monkeypatch.setattr(plans.readiness_journey_measure, "guarded_dsn", lambda value: value)
    monkeypatch.setattr(plans, "loaded_guard", lambda *_args: {"sha256": "a" * 64})
    monkeypatch.setattr(plans, "data_directory_identity", lambda *_args: "/proof")
    monkeypatch.setattr(plans, "create_owned_database", lambda *_args: "postgresql://owner@127.0.0.1:35418/readiness_child")
    monkeypatch.setattr(plans.readiness_journey_benchmark, "migrate", lambda *_args: (_ for _ in ()).throw(RuntimeError("stop")))
    cleanup_calls = []
    monkeypatch.setattr(plans, "cleanup_owned_database", lambda _dsn, name, created: cleanup_calls.append((name, created)) or {"database_name": name, "removed": True})
    payload = plans.run(type("Args", (), {"output": tmp_path / "out.json"})())
    assert payload["valid"] is False
    assert payload["cleanup"]["removed"] is True
    assert len(cleanup_calls) == 1 and cleanup_calls[0][1] is True


def test_parent_reuses_load_seed_helper_before_child_launch(monkeypatch, tmp_path):
    guard = tmp_path / "guard" / "sitecustomize.py"
    guard.parent.mkdir()
    guard.write_text("# guard\n", encoding="utf-8")
    monkeypatch.setenv(plans.DEFAULT_DSN_ENV, "postgresql://owner@127.0.0.1:35418/readiness_source")
    monkeypatch.setenv("PYTHONPATH", str(guard.parent))
    monkeypatch.setattr(plans.readiness_journey_measure, "guarded_dsn", lambda value: value)
    monkeypatch.setattr(plans, "loaded_guard", lambda *_args: {"sha256": "a" * 64})
    monkeypatch.setattr(plans, "data_directory_identity", lambda *_args: "/proof")
    monkeypatch.setattr(plans, "create_owned_database", lambda *_args: "postgresql://owner@127.0.0.1:35418/readiness_child")
    monkeypatch.setattr(plans.readiness_journey_benchmark, "migrate", lambda *_args: None)
    target = {"user_id": "u", "business_id": "b", "service_id": "s", "email": "u@benchmark.invalid"}
    seed_calls = []
    monkeypatch.setattr(plans.readiness_journey_load, "prepare_targets", lambda dsn, count: seed_calls.append((dsn, count)) or [target])
    monkeypatch.setattr(plans, "run_child_process", lambda *_args: ({"query_counts": {"auth_me": {"all": 1, "read": 1, "ddl_or_write": 0, "other": 0}, "business_data": {"all": 1, "read": 1, "ddl_or_write": 0, "other": 0}}, "plans": [{"name": name, "plan": [{}]} for name, _query, _parameters in plans.QUERY_SPECS]}, "completed"))
    monkeypatch.setattr(plans, "cleanup_owned_database", lambda *_args: {"removed": True})
    payload = plans.run(type("Args", (), {"output": tmp_path / "proof.json"})())
    assert payload["valid"] is True
    assert seed_calls == [("postgresql://owner@127.0.0.1:35418/readiness_child", 1)]


def test_precreate_failure_never_requests_destructive_cleanup(monkeypatch, tmp_path):
    monkeypatch.setattr(plans.readiness_journey_measure, "guarded_dsn", lambda _value: (_ for _ in ()).throw(ValueError("bad")))
    cleanup_calls = []
    monkeypatch.setattr(plans, "cleanup_owned_database", lambda _dsn, _name, created: cleanup_calls.append(created) or {"skipped": "not_created_by_this_invocation"})
    payload = plans.run(type("Args", (), {"output": tmp_path / "out.json"})())
    assert payload["valid"] is False
    assert cleanup_calls == [False]
