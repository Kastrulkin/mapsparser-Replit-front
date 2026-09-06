"""Exercise the real bounded HTTP server, not a mocked transport."""
from concurrent.futures import ThreadPoolExecutor
import http.client
import importlib.util
import json
from pathlib import Path
import socket
import threading
import time

import pytest

from services.compiled_script_artifact import build_artifact
from services import compiled_script_artifact, compiled_script_runtime


@pytest.fixture
def runner(monkeypatch):
    spec = importlib.util.spec_from_file_location("compiled_load_runner", Path(__file__).parents[1] / "docker/compiled-script-runner/server.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.SECRET = "test-only-transport-secret-" * 2
    module.IMAGE_DIGEST = "sha256:" + "b" * 64
    server = module.BoundedHTTPServer(("127.0.0.1", 0), module.Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_URL", "http://127.0.0.1:" + str(server.server_port))
    monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_SHARED_SECRET", module.SECRET)
    monkeypatch.setenv("COMPILED_SCRIPT_RUNNER_IMAGE_DIGEST", module.IMAGE_DIGEST)
    yield module, server
    server.shutdown()
    server.server_close()
    thread.join(timeout=5)


def artifact(digest):
    manifest = {"kind": "localos.python_transform.v1", "input_schema": {"type": "object", "properties": {}},
        "output_schema": {"type": "object", "properties": {"value": {"type": "integer"}}, "required": ["value"]},
        "runtime_version": "python-3.12-restricted-v1", "dependencies": [], "runner_image_digest": digest}
    return build_artifact("def process(input_payload):\n    return {'value': 7}", manifest, [{"input": {}, "expected": {"value": 7}, "source": "user"}])


def test_real_runtime_replay_is_atomic_and_never_calls_model(runner, monkeypatch):
    module, server = runner
    def forbid_model(*_args, **_kwargs):
        raise AssertionError("runtime attempted a model call")
    monkeypatch.setattr(compiled_script_artifact, "run_llm_task", forbid_model)
    program = artifact(module.IMAGE_DIGEST)
    assert compiled_script_runtime.execute_in_attested_sandbox(program, {})["value"] == 7
    body, headers = compiled_script_runtime._request_payload(program, {})
    def send():
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=4)
        try:
            connection.request("POST", "/v1/run", body, headers)
            response = connection.getresponse()
            response.read()
            return response.status
        finally:
            connection.close()
    pool = ThreadPoolExecutor(max_workers=2)
    try:
        assert sorted(pool.map(lambda _index: send(), range(2))) == [200, 401]
    finally:
        pool.shutdown()


def test_slow_requests_are_bounded_and_server_recovers(runner):
    module, server = runner
    sockets = []
    try:
        for _index in range(2):
            connection = socket.create_connection(("127.0.0.1", server.server_port), timeout=4)
            connection.sendall(b"POST /v1/run HTTP/1.0\r\nContent-Length: 200\r\n\r\n")
            sockets.append(connection)
        deadline = time.monotonic() + 1
        while server.capacity._value and time.monotonic() < deadline:
            time.sleep(0.01)
        assert server.capacity._value == 0
        connection = http.client.HTTPConnection("127.0.0.1", server.server_port, timeout=1)
        try:
            connection.request("POST", "/v1/run", b"{}")
            assert connection.getresponse().status == 503
        finally:
            connection.close()
        for connection in sockets:
            assert b"408" in connection.recv(4096)
        deadline = time.monotonic() + 1
        while server.capacity._value != 2 and time.monotonic() < deadline:
            time.sleep(0.01)
        assert compiled_script_runtime.execute_in_attested_sandbox(artifact(module.IMAGE_DIGEST), {})["value"] == 7
    finally:
        for connection in sockets:
            connection.close()
