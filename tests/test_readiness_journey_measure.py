import importlib.util
import json
from pathlib import Path
import sys

import pytest


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "readiness_journey_measure.py"
SPEC = importlib.util.spec_from_file_location("readiness_journey_measure", MODULE_PATH)
measure = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = measure
SPEC.loader.exec_module(measure)


def test_quantiles_and_failures_are_separated():
    runs = [
        {
            "samples": [
                {"kind": "request", "journey": "finance_import", "step": "apply", "success": True, "duration_ms": 10},
                {"kind": "request", "journey": "finance_import", "step": "apply", "success": True, "duration_ms": 30},
                {"kind": "request", "journey": "finance_import", "step": "apply", "success": False, "duration_ms": 999},
                {"kind": "invariant", "journey": "finance_import", "step": "apply", "success": True, "duration_ms": None},
            ]
        }
    ]

    summary = measure.summarize(runs)["finance_import/apply"]

    assert summary["request_count"] == 3
    assert summary["success_count"] == 2
    assert summary["failure_count"] == 1
    assert summary["p50_ms"] == 20
    assert summary["p99_note"]


def test_correctness_counts_keep_non_request_failures():
    counts = measure.correctness_counts(
        [{"samples": [{"kind": "request", "success": True}, {"kind": "invariant", "success": False}]}]
    )

    assert counts == {"request": {"total": 1, "failed": 0}, "invariant": {"total": 1, "failed": 1}}


def test_required_limits_are_bounded():
    measure.validate_limits(10, 50, 20, 2)
    with pytest.raises(ValueError):
        measure.validate_limits(11, 50, 20, 2)
    with pytest.raises(ValueError):
        measure.validate_limits(10, 51, 20, 2)
    with pytest.raises(ValueError):
        measure.validate_limits(10, 50, 21, 2)
    with pytest.raises(ValueError):
        measure.validate_limits(10, 50, 20, 3)


def test_guarded_dsn_rejects_non_local_identity(monkeypatch):
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    monkeypatch.delenv("PGSERVICE", raising=False)
    monkeypatch.delenv("PGSERVICEFILE", raising=False)
    monkeypatch.delenv("PGOPTIONS", raising=False)
    with pytest.raises(ValueError):
        measure.guarded_dsn("postgresql://owner@127.0.0.1:5432/readiness_test")
    with pytest.raises(ValueError):
        measure.guarded_dsn("postgresql://owner@127.0.0.1:35418/readiness_test?dbname=other")


def test_guard_provenance_requires_sitecustomize(tmp_path):
    with pytest.raises(ValueError):
        measure.guard_provenance("")

    guard = tmp_path / "sitecustomize.py"
    guard.write_text("# local egress guard\n", encoding="utf-8")

    provenance = measure.guard_provenance(str(tmp_path))

    assert provenance["path"] == str(guard)
    assert len(provenance["sha256"]) == 64


def test_guard_provenance_rejects_guard_after_another_path(tmp_path):
    first = tmp_path / "first"
    guarded = tmp_path / "guarded"
    first.mkdir()
    guarded.mkdir()
    (guarded / "sitecustomize.py").write_text("# guard\n", encoding="utf-8")

    with pytest.raises(ValueError):
        measure.guard_provenance(f"{first}:{guarded}")


def test_child_environment_drops_provider_configuration(monkeypatch, tmp_path):
    monkeypatch.setenv("GIGACHAT_KEYS", "must-not-reach-harness")
    monkeypatch.setenv("OPENAI_API_KEY", "must-not-reach-harness")

    environment = measure.safe_environment(
        "postgresql://owner@127.0.0.1:35418/readiness_test",
        tmp_path,
        "/private/tmp/guard",
    )

    assert "GIGACHAT_KEYS" not in environment
    assert "OPENAI_API_KEY" not in environment
    assert environment["PYTHONPATH"].split(":")[0] == "/private/tmp/guard"
    assert environment["PYTHON_DOTENV_DISABLED"] == "1"


def test_child_environment_keeps_only_first_guard_directory(monkeypatch, tmp_path):
    monkeypatch.setenv("PYTHONPATH", "/private/guard:/hostile/current-repository")

    environment = measure.safe_environment(
        "postgresql://owner@127.0.0.1:35418/readiness_test",
        tmp_path,
        "/private/guard:/hostile/current-repository",
    )

    assert environment["PYTHONPATH"].split(":") == ["/private/guard", str(tmp_path / "src"), str(tmp_path)]
    assert "/hostile/current-repository" not in environment["PYTHONPATH"]


def test_validation_fails_when_expected_request_step_is_missing():
    run = {
        "exit_code": 0,
        "samples": [{"kind": "request", "journey": "auth_tenant", "step": "login", "success": True}],
    }

    reasons = measure.validation_reasons(run)

    assert "request_count:auth_tenant/me:0" in reasons
    assert "request_count:operator/confirm_replay:0" in reasons


def test_validation_fails_for_coverage_failure_even_with_success_exit():
    run = {
        "exit_code": 0,
        "samples": [
            {"kind": "coverage", "journey": "content", "step": "draft", "success": False, "error": "missing"}
        ],
    }

    reasons = measure.validation_reasons(run)

    assert "failed_coverage:content/draft:missing" in reasons


def test_import_origin_preflight_uses_archive_paths_only(monkeypatch, tmp_path):
    source_root = tmp_path / "archive"
    (source_root / "src").mkdir(parents=True)
    expected = {
        "database_manager": str(source_root / "src" / "database_manager.py"),
        "main": str(source_root / "src" / "main.py"),
    }

    class Completed:
        returncode = 0
        stdout = "startup line\n__LOCALOS_READINESS_IMPORT_ORIGINS__" + json.dumps(expected)
        stderr = ""

    observed = {}

    def run(_command, **kwargs):
        observed.update(kwargs["env"])
        return Completed()

    monkeypatch.setattr(measure.subprocess, "run", run)
    origins = measure.import_origins(
        source_root,
        "postgresql://owner@127.0.0.1:35418/readiness_test",
        "/private/guard:/hostile/current-repository",
    )

    assert origins == expected
    assert observed["PYTHONPATH"].split(":") == ["/private/guard", str(source_root / "src"), str(source_root)]


def test_import_origins_uses_real_subprocess_without_importing_app(tmp_path):
    source_root = tmp_path / "archive"
    guard_root = tmp_path / "guard"
    (source_root / "src").mkdir(parents=True)
    guard_root.mkdir()
    (source_root / "src" / "__init__.py").write_text("", encoding="utf-8")
    (source_root / "src" / "main.py").write_text("raise RuntimeError('must not import')\n", encoding="utf-8")
    (source_root / "src" / "database_manager.py").write_text("raise RuntimeError('must not import')\n", encoding="utf-8")
    (guard_root / "sitecustomize.py").write_text("", encoding="utf-8")

    origins = measure.import_origins(
        source_root,
        "postgresql://owner@127.0.0.1:35418/readiness_test",
        str(guard_root),
    )

    assert origins == {
        "database_manager": str(source_root / "src" / "database_manager.py"),
        "main": str(source_root / "src" / "main.py"),
    }


def test_collision_never_starts_child_or_drops_database(monkeypatch, tmp_path):
    harness_root = tmp_path / "scripts"
    guard_root = tmp_path / "guard"
    harness_root.mkdir()
    guard_root.mkdir()
    (harness_root / "readiness_journey_benchmark.py").write_text("", encoding="utf-8")
    (guard_root / "sitecustomize.py").write_text("", encoding="utf-8")
    monkeypatch.setattr(measure, "owned_database_absent", lambda _dsn, _name: False)

    def forbidden(*_args, **_kwargs):
        raise AssertionError("collision must not start or remove a database")

    monkeypatch.setattr(measure.subprocess, "Popen", forbidden)
    monkeypatch.setattr(measure, "cleanup_owned_database", forbidden)

    result = measure.run_harness_once(
        tmp_path,
        "postgresql://owner@127.0.0.1:35418/readiness_test",
        str(guard_root),
        tmp_path / "out.json",
        "f" * 40,
        "serial",
        0,
    )

    assert result["cleanup"]["skipped"] == "not_proven_absent_before_child"
    assert result["valid"] is False
