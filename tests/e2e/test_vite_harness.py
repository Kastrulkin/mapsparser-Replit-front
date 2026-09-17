import pytest

from tests.e2e import vite_harness
from tests.e2e.vite_harness import IsolatedViteApp, guard_browser_requests


class FakeRequest:
    def __init__(self, url: str):
        self.url = url


class FakeRoute:
    def __init__(self, url: str):
        self.request = FakeRequest(url)
        self.action = ""

    def abort(self, *, error_code: str) -> None:
        self.action = f"abort:{error_code}"

    def continue_(self) -> None:
        self.action = "continue"


class FakePage:
    def __init__(self):
        self.handler = None

    def route(self, _pattern: str, handler) -> None:
        self.handler = handler


def guarded_route(url: str):
    page = FakePage()
    fulfilled = []
    guard_browser_requests(page, 48123, lambda route: fulfilled.append(route.request.url))
    route = FakeRoute(url)
    page.handler(route)
    return route, fulfilled


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:48124/api/auth/me",
        "https://localhost:8000/api/auth/me",
        "http://localhost:8001/api/auth/me",
        "https://example.test/api/auth/me",
    ],
)
def test_browser_guard_aborts_foreign_loopback_and_external_origins(url: str):
    route, fulfilled = guarded_route(url)

    assert route.action == "abort:blockedbyclient"
    assert fulfilled == []


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1:48123/api/auth/me",
        "http://localhost:8000/api/auth/me",
    ],
)
def test_browser_guard_fulfills_only_explicit_api_origins(url: str):
    route, fulfilled = guarded_route(url)

    assert route.action == ""
    assert fulfilled == [url]


def test_browser_guard_continues_only_own_vite_static_request():
    route, fulfilled = guarded_route("http://127.0.0.1:48123/assets/main.js")

    assert route.action == "continue"
    assert fulfilled == []


def test_failed_vite_start_stops_only_its_mocked_process_and_closes_diagnostics(monkeypatch):
    class FakeDiagnostics:
        def __init__(self):
            self.closed = False

        def close(self) -> None:
            self.closed = True

        def flush(self) -> None:
            return None

        def seek(self, _position: int) -> None:
            return None

        def read(self) -> str:
            return "safe startup failure"

    class FakeProcess:
        pid = 43210

        def __init__(self):
            self.wait_calls = []

        def poll(self):
            return None

        def wait(self, timeout: int) -> None:
            self.wait_calls.append(timeout)

    diagnostics = FakeDiagnostics()
    process = FakeProcess()
    killed = []

    monkeypatch.setattr(vite_harness, "_require_frontend_dependencies", lambda: None)
    monkeypatch.setattr(vite_harness, "_available_loopback_port", lambda: 48123)
    monkeypatch.setattr(vite_harness.tempfile, "TemporaryFile", lambda **_kwargs: diagnostics)
    monkeypatch.setattr(vite_harness.subprocess, "Popen", lambda *_args, **_kwargs: process)
    monkeypatch.setattr(vite_harness, "urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("mock readiness failure")))
    monkeypatch.setattr(vite_harness.os, "killpg", lambda pid, signal_value: killed.append((pid, signal_value)))

    app = IsolatedViteApp("/dashboard/operator")

    try:
        app.start()
    except RuntimeError:
        pass
    else:
        pytest.fail("failed Vite startup must be re-raised")

    assert killed == [(43210, vite_harness.signal.SIGTERM)]
    assert process.wait_calls == [10]
    assert diagnostics.closed is True
