"""Pure transport regressions for the approved Operator colleague message."""

from __future__ import annotations

import pytest

from services import operator_colleagues


class _Cursor:
    def __init__(self):
        self.delivery = {
            "dedupe_key": "delivery-1",
            "message_text": "Approved colleague message",
            "attempted_at": None,
            "sent_at": None,
            "provider_message_id": None,
            "dispatch_state": "queued",
        }
        self._row = None

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        if normalized.startswith("select * from journey_action_notification_deliveries"):
            self._row = self.delivery
        elif normalized.startswith("update journey_action_notification_deliveries set attempted_at"):
            self.delivery["attempted_at"] = "synthetic-attempt"
            self.delivery["dispatch_state"] = "unknown"
        elif normalized.startswith("update journey_action_notification_deliveries set dispatch_state='failed'"):
            self.delivery["dispatch_state"] = "failed"
        elif normalized.startswith("update journey_action_notification_deliveries set sent_at"):
            self.delivery["sent_at"] = "synthetic-sent"
            self.delivery["dispatch_state"] = "sent"
            self.delivery["provider_message_id"] = str(params[0])
        else:
            raise AssertionError(f"unexpected SQL: {query}")

    def fetchone(self):
        return self._row


class _Connection:
    def __init__(self, cursor: _Cursor):
        self.cursor_value = cursor
        self.commits = 0

    def cursor(self):
        return self.cursor_value

    def commit(self):
        self.commits += 1


class _DatabaseManager:
    instances: list["_DatabaseManager"] = []
    cursor_state: _Cursor | None = None

    def __init__(self):
        if self.cursor_state is None:
            self.cursor_state = _Cursor()
        self.cursor_value = self.cursor_state
        self.conn = _Connection(self.cursor_value)
        self.closed = False
        self.instances.append(self)

    def close(self):
        self.closed = True


class _Response:
    def __init__(self, status_code=200, body=None):
        self.status_code = status_code
        self.body = body if body is not None else {"ok": True, "result": {"message_id": 71}}

    def json(self):
        return self.body


def _job():
    return {
        "business_id": "business-1",
        "user_id": "user-1",
        "payload_json": {
            "dedupe_key": "delivery-1",
            "envelope": {
                "recipient_version": 3,
                "telegram_id": "12345",
                "date": "2026-09-20",
                "schedule_version": 7,
            },
        },
    }


def _clear_telegram_proxy_env(monkeypatch):
    for key in ("TELEGRAM_HTTP_PROXY", "TELEGRAM_API_PROXY", "OUTBOUND_HTTP_PROXY"):
        monkeypatch.delenv(key, raising=False)


def _configure(monkeypatch):
    _DatabaseManager.instances = []
    _DatabaseManager.cursor_state = _Cursor()
    monkeypatch.setattr(operator_colleagues, "DatabaseManager", _DatabaseManager)
    monkeypatch.setattr(operator_colleagues.operator_workday, "authorize", lambda _cursor, _business, _user: None)
    monkeypatch.setattr(
        operator_colleagues,
        "recipient",
        lambda _cursor, _business: {"version": 3, "telegram_id": "12345"},
    )
    monkeypatch.setattr(operator_colleagues.operator_workday, "schedule", lambda _cursor, _business, _date: {"version": 7})
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "synthetic-token")
    _clear_telegram_proxy_env(monkeypatch)


@pytest.mark.parametrize(
    ("configured", "expected"),
    (
        ({"TELEGRAM_HTTP_PROXY": "http://telegram-proxy", "TELEGRAM_API_PROXY": "http://api-proxy", "OUTBOUND_HTTP_PROXY": "http://outbound-proxy"}, "http://telegram-proxy"),
        ({"TELEGRAM_API_PROXY": "http://api-proxy", "OUTBOUND_HTTP_PROXY": "http://outbound-proxy"}, "http://api-proxy"),
        ({"OUTBOUND_HTTP_PROXY": "http://outbound-proxy"}, "http://outbound-proxy"),
    ),
)
def test_colleague_send_uses_configured_telegram_proxy_priority(monkeypatch, configured, expected):
    _configure(monkeypatch)
    for key, value in configured.items():
        monkeypatch.setenv(key, value)
    observed = []

    def send(*_args, **kwargs):
        manager = _DatabaseManager.instances[0]
        observed.append(
            {
                "kwargs": kwargs,
                "commits_before_effect": manager.conn.commits,
                "attempted_before_effect": manager.cursor_value.delivery["attempted_at"],
            }
        )
        return _Response()

    monkeypatch.setattr(operator_colleagues.requests, "post", send)

    result = operator_colleagues.process_job(_job())
    replay = operator_colleagues.process_job(_job())

    assert result["delivery_state"] == "sent"
    assert replay["status"] == "completed"
    assert replay["provider_message_id"] == "71"
    assert observed == [
        {
            "kwargs": {
                "json": {"chat_id": "12345", "text": "Approved colleague message"},
                "timeout": (10, 30),
                "proxies": {"http": expected, "https": expected},
            },
            "commits_before_effect": 1,
            "attempted_before_effect": "synthetic-attempt",
        }
    ]


def test_colleague_send_preserves_requests_defaults_without_application_proxy(monkeypatch):
    _configure(monkeypatch)
    observed = []
    monkeypatch.setattr(operator_colleagues.requests, "post", lambda *args, **kwargs: observed.append(kwargs) or _Response())

    assert operator_colleagues.process_job(_job())["delivery_state"] == "sent"
    assert "proxies" not in observed[0]


def test_colleague_transport_timeout_keeps_no_blind_retry_fence(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setenv("TELEGRAM_HTTP_PROXY", "http://telegram-proxy")
    calls = []

    def timeout(*_args, **kwargs):
        calls.append(kwargs)
        raise operator_colleagues.requests.Timeout("synthetic timeout")

    monkeypatch.setattr(operator_colleagues.requests, "post", timeout)

    first = operator_colleagues.process_job(_job())
    second = operator_colleagues.process_job(_job())

    assert first["delivery_state"] == second["delivery_state"] == "unknown"
    assert len(calls) == 1
    assert calls[0]["proxies"]["https"] == "http://telegram-proxy"


def test_colleague_transport_rejection_keeps_failed_status(monkeypatch):
    _configure(monkeypatch)
    calls = []
    monkeypatch.setattr(operator_colleagues.requests, "post", lambda *_args, **_kwargs: calls.append(1) or _Response(403, {"ok": False}))

    result = operator_colleagues.process_job(_job())
    replay = operator_colleagues.process_job(_job())

    assert result["delivery_state"] == "failed"
    assert result["status"] == "blocked"
    assert replay["delivery_state"] == "unknown"
    assert calls == [1]


def test_colleague_authorization_denial_happens_before_transport(monkeypatch):
    _configure(monkeypatch)
    monkeypatch.setattr(
        operator_colleagues.operator_workday,
        "authorize",
        lambda _cursor, _business, _user: (_ for _ in ()).throw(PermissionError("denied")),
    )
    monkeypatch.setattr(
        operator_colleagues.requests,
        "post",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(AssertionError("transport must not run")),
    )

    with pytest.raises(PermissionError, match="denied"):
        operator_colleagues.process_job(_job())
