import pytest

from src.core.action_orchestrator import ActionOrchestrator
import src.core.action_orchestrator as action_orchestrator_module
import src.core.outbound_network as outbound_network


class RecordingCursor:
    def __init__(self):
        self.executed = []

    def execute(self, query, params):
        self.executed.append((query, params))

    def fetchone(self):
        return ("outbox-id",)


@pytest.mark.parametrize(
    "callback_url",
    [
        "http://127.0.0.1/internal",
        "http://169.254.169.254/latest/meta-data",
        "http://10.0.0.8/private",
        "http://localhost/admin",
        "file:///etc/passwd",
    ],
)
def test_callback_outbox_rejects_non_public_destinations(callback_url):
    cursor = RecordingCursor()
    orchestrator = ActionOrchestrator({})

    with pytest.raises(ValueError, match="public"):
        orchestrator._enqueue_callback(
            cursor,
            action_id="action-1",
            tenant_id="tenant-1",
            callback_url=callback_url,
            event_type="pending_human",
            payload={"status": "pending_human"},
        )

    assert cursor.executed == []


class DispatchCursor:
    def __init__(self, rows=None):
        self.rows = rows or []
        self.executed = []

    def execute(self, query, params):
        self.executed.append((query, params))

    def fetchall(self):
        return self.rows


class DispatchConnection:
    def __init__(self, cursor):
        self._cursor = cursor

    def cursor(self):
        return self._cursor

    def commit(self):
        return None


class DispatchDatabase:
    def __init__(self, cursor):
        self.conn = DispatchConnection(cursor)

    def close(self):
        return None


def test_callback_dispatch_does_not_follow_redirects(monkeypatch):
    callback_url = "https://callbacks.example.com/localos"
    outbox_cursor = DispatchCursor(
        rows=[
            (
                "outbox-1",
                "action-1",
                "tenant-1",
                callback_url,
                "completed",
                {"status": "completed"},
                0,
                5,
                "action-1:completed",
            )
        ]
    )
    result_cursor = DispatchCursor()
    databases = iter([DispatchDatabase(outbox_cursor), DispatchDatabase(result_cursor)])
    monkeypatch.setattr(action_orchestrator_module, "DatabaseManager", lambda: next(databases))
    monkeypatch.setattr(
        outbound_network.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )
    post_calls = []

    class RedirectResponse:
        status_code = 302
        text = "redirect"

    def record_post(url, body, headers, timeout=5):
        post_calls.append((url, body, headers, timeout))
        return RedirectResponse()

    monkeypatch.setattr(action_orchestrator_module, "public_pinned_post", record_post)
    orchestrator = ActionOrchestrator({})
    monkeypatch.setattr(orchestrator, "ensure_tables", lambda _cursor: None)

    result = orchestrator.dispatch_callback_outbox(batch_size=1)

    assert post_calls[0][0] == callback_url
    assert post_calls[0][1] == b'{"status":"completed"}'
    assert post_calls[0][2]["Content-Type"] == "application/json"
    assert post_calls[0][3] == 5
    assert result["sent"] == 0
    assert result["retried"] == 1


def test_public_pinned_post_connects_to_resolved_ip_with_original_tls_hostname(monkeypatch):
    captured = {}

    monkeypatch.setattr(
        outbound_network.socket,
        "getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("93.184.216.34", 443))],
    )

    class FakeResponse:
        status = 200

        def read(self, _size):
            return b"accepted"

        def release_conn(self):
            captured["released"] = True

    class FakePool:
        def __init__(self, host, **kwargs):
            captured["pool_host"] = host
            captured["pool_kwargs"] = kwargs

        def urlopen(self, method, path, **kwargs):
            captured["method"] = method
            captured["path"] = path
            captured["request_kwargs"] = kwargs
            return FakeResponse()

        def close(self):
            captured["closed"] = True

    monkeypatch.setattr(outbound_network.urllib3, "HTTPSConnectionPool", FakePool)

    response = outbound_network.public_pinned_post(
        "https://callbacks.example.com:443/localos/event?source=journey",
        b'{"status":"completed"}',
        {"Content-Type": "application/json"},
        timeout=7,
    )

    assert captured["pool_host"] == "93.184.216.34"
    assert captured["pool_kwargs"]["assert_hostname"] == "callbacks.example.com"
    assert captured["pool_kwargs"]["server_hostname"] == "callbacks.example.com"
    assert captured["path"] == "/localos/event?source=journey"
    assert captured["request_kwargs"]["redirect"] is False
    assert captured["request_kwargs"]["headers"]["Host"] == "callbacks.example.com"
    assert captured["released"] is True
    assert captured["closed"] is True
    assert response.status_code == 200
    assert response.text == "accepted"
