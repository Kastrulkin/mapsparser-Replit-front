import importlib.util
import json
from pathlib import Path
import sys

import pytest


MODULE_PATH = Path(__file__).parents[1] / "scripts" / "readiness_journey_benchmark.py"
SPEC = importlib.util.spec_from_file_location("readiness_journey_benchmark", MODULE_PATH)
benchmark = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
sys.modules[SPEC.name] = benchmark
SPEC.loader.exec_module(benchmark)


@pytest.mark.parametrize(
    "dsn",
    [
        "postgresql://owner@localhost:35418/readiness_test",
        "postgresql://owner@127.0.0.1:5432/readiness_test",
        "postgresql://owner@127.0.0.1:35418/production",
        "postgresql://owner@127.0.0.1:35418/readiness_test?service=unsafe",
    ],
)
def test_guarded_dsn_rejects_non_disposable_targets(monkeypatch, dsn):
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    monkeypatch.delenv("PGSERVICE", raising=False)
    monkeypatch.delenv("PGSERVICEFILE", raising=False)
    with pytest.raises(ValueError):
        benchmark.guarded_dsn(dsn)


def test_guarded_dsn_allows_explicit_loopback_readiness_database(monkeypatch):
    monkeypatch.delenv("PGHOSTADDR", raising=False)
    monkeypatch.delenv("PGSERVICE", raising=False)
    monkeypatch.delenv("PGSERVICEFILE", raising=False)
    dsn = "postgresql://owner@127.0.0.1:35418/readiness_operator_test"
    assert benchmark.guarded_dsn(dsn) == dsn


def test_guarded_dsn_rejects_inherited_pgoptions(monkeypatch):
    monkeypatch.setenv("PGOPTIONS", "-c search_path=public")
    with pytest.raises(ValueError):
        benchmark.guarded_dsn("postgresql://owner@127.0.0.1:35418/readiness_operator_test")


def test_migration_subprocess_preserves_guard_first_pythonpath(monkeypatch):
    observed = {}

    class Completed:
        returncode = 0
        stderr = ""
        stdout = ""

    def run(_command, **kwargs):
        observed.update(kwargs["env"])
        return Completed()

    monkeypatch.setenv("PYTHONPATH", "/private/guard:/existing")
    monkeypatch.setattr(benchmark.subprocess, "run", run)
    benchmark.migrate("postgresql://owner@127.0.0.1:35418/localos_readiness_benchmark_test")

    paths = observed["PYTHONPATH"].split(":")
    assert paths[:2] == ["/private/guard", "/existing"]
    assert str(benchmark.ROOT / "src") in paths
    assert observed["PYTHON_DOTENV_DISABLED"] == "1"
    assert "GIGACHAT_API_KEY" not in observed


def test_record_preserves_a_failed_http_status_as_a_failed_measurement():
    class Response:
        status_code = 500

    samples = []
    benchmark.record(samples, "content", "draft", Response, {200})
    assert len(samples) == 1
    assert samples[0].success is False
    assert samples[0].status_code == 500


def test_record_rejects_http_success_when_nested_generation_failed():
    class Response:
        status_code = 200

        @staticmethod
        def get_json():
            return {"success": True, "generation": {"success": False}}

    samples = []
    benchmark.record(
        samples,
        "content",
        "draft",
        Response,
        {200},
        lambda response: bool((response.get_json() or {}).get("generation", {}).get("success")),
    )
    assert samples[0].success is False
    assert samples[0].kind == "request"


def test_required_coverage_records_missing_steps_as_failures():
    samples = []
    benchmark.verify_required_coverage(samples)
    assert samples
    assert all(sample.success is False for sample in samples)
    assert all(sample.kind == "coverage" for sample in samples)


def test_environment_allowlist_removes_gigachat_keys_and_proxies(monkeypatch):
    original_environment = benchmark.os.environ.copy()
    monkeypatch.setenv("GIGACHAT_KEYS", "should-not-survive")
    monkeypatch.setenv("HTTPS_PROXY", "http://should-not-survive")
    monkeypatch.setenv("PYTHONPATH", "/private/guard")

    try:
        benchmark.remove_external_provider_environment()

        assert "GIGACHAT_KEYS" not in benchmark.os.environ
        assert "HTTPS_PROXY" not in benchmark.os.environ
        assert benchmark.os.environ["PYTHONPATH"] == "/private/guard"
    finally:
        benchmark.os.environ.clear()
        benchmark.os.environ.update(original_environment)


def test_result_provenance_names_both_provider_seams(tmp_path):
    output = tmp_path / "result.json"
    benchmark.write_result(output, "localos_readiness_benchmark_test", [])
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert payload["provider_seams"] == ["content_text_generation", "operator_planner"]
    assert payload["sample_type"] == "mixed_request_and_invariant_samples"
    assert payload["script_sha256"]
    assert "commit" in payload


def test_sitecustomize_provenance_hashes_the_active_guard(tmp_path):
    guard = tmp_path / "sitecustomize.py"
    guard.write_text("raise RuntimeError('network guard')\n", encoding="utf-8")

    provenance = benchmark.sitecustomize_provenance(str(tmp_path))

    assert provenance is not None
    assert provenance["path"] == str(guard)
    assert len(provenance["sha256"]) == 64
    assert benchmark.sitecustomize_provenance("") is None


def test_drop_guard_refuses_non_owned_database():
    with pytest.raises(ValueError):
        benchmark.drop_owned_database("postgresql://owner@127.0.0.1:35418/readiness_operator_test", "postgres")


def test_owned_database_name_accepts_only_generated_uuid_forms():
    measure_name = "localos_readiness_measure_0123456789abcdef0123456789abcdef"
    assert benchmark.owned_database_name(measure_name)
    assert benchmark.owned_database_name("localos_readiness_measure_test") is False
    assert benchmark.owned_database_name("readiness_operator_test") is False
