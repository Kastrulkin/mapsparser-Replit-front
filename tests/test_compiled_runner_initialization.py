"""Initialization lifecycle regression tests for the compiled script runner."""
import importlib.util
from pathlib import Path

import pytest


RUNNER_PATH = Path(__file__).parents[1] / "docker" / "compiled-script-runner" / "server.py"


def load_runner_module():
    specification = importlib.util.spec_from_file_location(
        "compiled_runner_initialization", RUNNER_PATH
    )
    module = importlib.util.module_from_spec(specification)
    specification.loader.exec_module(module)
    return module


def test_bind_failure_preserves_original_permission_error(monkeypatch):
    module = load_runner_module()
    parent_close_calls = []
    original_parent_close = module.HTTPServer.server_close

    def deny_bind(_server):
        raise PermissionError("synthetic bind denial")

    def record_parent_close(_server):
        parent_close_calls.append(True)
        original_parent_close(_server)

    monkeypatch.setattr(module.HTTPServer, "server_bind", deny_bind)
    monkeypatch.setattr(module.HTTPServer, "server_close", record_parent_close)

    with pytest.raises(PermissionError, match="synthetic bind denial"):
        module.BoundedHTTPServer(("127.0.0.1", 8091), module.Handler)

    assert parent_close_calls == [True]


def test_initialized_server_shuts_down_created_pool(monkeypatch):
    module = load_runner_module()
    parent_close_calls = []
    pool_shutdown_calls = []

    class FakePool:
        def shutdown(self, wait):
            pool_shutdown_calls.append(wait)

    def fake_parent_init(_server, _address, _handler):
        return None

    def record_parent_close(_server):
        parent_close_calls.append(True)

    def create_pool(max_workers, thread_name_prefix):
        assert max_workers == 2
        assert thread_name_prefix == "compiled"
        return FakePool()

    monkeypatch.setattr(module.HTTPServer, "__init__", fake_parent_init)
    monkeypatch.setattr(module.HTTPServer, "server_close", record_parent_close)
    monkeypatch.setattr(module, "ThreadPoolExecutor", create_pool)

    server = module.BoundedHTTPServer(("127.0.0.1", 8091), module.Handler)
    server.server_close()

    assert parent_close_calls == [True]
    assert pool_shutdown_calls == [True]
