import hashlib
import sys
import types

import pytest

from tests.test_services_content_viewer_readiness import GUARD_ENV, TEST_DSN_ENV, isolated_test_dsn


def configure_guard(monkeypatch, tmp_path):
    guard = tmp_path / "sitecustomize.py"
    guard.write_text("# isolated guard\n", encoding="utf-8")
    loaded = types.SimpleNamespace(__file__=str(guard))
    monkeypatch.setenv("PYTHONPATH", str(tmp_path))
    monkeypatch.setenv(GUARD_ENV, hashlib.sha256(guard.read_bytes()).hexdigest())
    monkeypatch.setitem(sys.modules, "sitecustomize", loaded)


@pytest.mark.parametrize("database_url", [
    "postgresql://readiness_test_owner@127.0.0.1:35418/readiness_full_test_reviewed_20260918",
    "postgresql://readiness_test_owner@127.0.0.1:35418/readiness_full_test_a1b2c3d4_001122334455",
])
def test_isolated_test_dsn_accepts_only_legacy_or_strict_fresh_owned_names(monkeypatch, tmp_path, database_url):
    configure_guard(monkeypatch, tmp_path)
    monkeypatch.setenv(TEST_DSN_ENV, database_url)
    assert isolated_test_dsn() == database_url


@pytest.mark.parametrize("database_url", [
    "postgresql://readiness_test_owner@127.0.0.1:35418/readiness_full_test_arbitrary",
    "postgresql://readiness_test_owner@127.0.0.1:35418/readiness_full_test_a1b2c3d4_001122334455_more",
    "postgresql://readiness_test_owner@127.0.0.1:5432/readiness_full_test_a1b2c3d4_001122334455",
    "postgresql://readiness_test_owner@localhost:35418/readiness_full_test_a1b2c3d4_001122334455",
    "postgresql://readiness_test_owner@127.0.0.1:35418/readiness_full_test_a1b2c3d4_001122334455?sslmode=require",
])
def test_isolated_test_dsn_rejects_nonowned_or_noncannonical_targets(monkeypatch, tmp_path, database_url):
    configure_guard(monkeypatch, tmp_path)
    monkeypatch.setenv(TEST_DSN_ENV, database_url)
    with pytest.raises(RuntimeError, match="owned loopback"):
        isolated_test_dsn()


def test_isolated_test_dsn_rejects_libpq_override(monkeypatch, tmp_path):
    configure_guard(monkeypatch, tmp_path)
    monkeypatch.setenv(TEST_DSN_ENV, "postgresql://readiness_test_owner@127.0.0.1:35418/readiness_full_test_a1b2c3d4_001122334455")
    monkeypatch.setenv("PGSERVICE", "untrusted")
    with pytest.raises(RuntimeError, match="libpq overrides"):
        isolated_test_dsn()


def test_isolated_test_dsn_rejects_guard_hash_mismatch(monkeypatch, tmp_path):
    configure_guard(monkeypatch, tmp_path)
    monkeypatch.setenv(TEST_DSN_ENV, "postgresql://readiness_test_owner@127.0.0.1:35418/readiness_full_test_a1b2c3d4_001122334455")
    monkeypatch.setenv(GUARD_ENV, "0" * 64)
    with pytest.raises(RuntimeError, match="pinned guard"):
        isolated_test_dsn()
