from services import operator_audit


class FakeCursor:
    def __init__(self):
        self.executed = []
        self.rows = []

    def execute(self, query, params=None):
        self.executed.append((" ".join(str(query or "").lower().split()), params or ()))

    def fetchall(self):
        return self.rows


def test_record_operator_event_uses_agent_action_ledger(monkeypatch) -> None:
    captured = {}

    def fake_log_agent_action(cursor, **kwargs):
        captured.update(kwargs)
        return "ledger-1"

    monkeypatch.setattr(operator_audit, "log_agent_action", fake_log_agent_action)

    ledger_id = operator_audit.record_operator_event(
        FakeCursor(),
        business_id="biz-1",
        user_id="user-1",
        event_type="operator_paid_action_estimated",
        action_key="map_reviews_refresh",
        status="blocked",
        reason_code="estimate_required",
        input_summary={"estimated_credits": ""},
        output_summary={"status": "blocked"},
        metadata={"execution_status": "preflight_only"},
    )

    assert ledger_id == "ledger-1"
    assert captured["agent_client_id"] is None
    assert captured["business_id"] == "biz-1"
    assert captured["action_type"] == "operator_paid_action_estimated"
    assert captured["capability"] == operator_audit.OPERATOR_CAPABILITY
    assert captured["risk_level"] == "medium"
    assert captured["status"] == "blocked"
    assert captured["reason_code"] == "estimate_required"
    assert captured["metadata"]["operator_user_id"] == "user-1"
    assert captured["metadata"]["action_key"] == "map_reviews_refresh"
    assert captured["metadata"]["credit_charged"] is False
    assert captured["metadata"]["external_calls_performed"] is False


def test_record_operator_event_rejects_unknown_event(monkeypatch) -> None:
    called = {"value": False}

    def fake_log_agent_action(cursor, **kwargs):
        called["value"] = True
        return "ledger-1"

    monkeypatch.setattr(operator_audit, "log_agent_action", fake_log_agent_action)

    ledger_id = operator_audit.record_operator_event(
        FakeCursor(),
        business_id="biz-1",
        user_id="user-1",
        event_type="operator_tool_executed",
    )

    assert ledger_id is None
    assert called["value"] is False


def test_list_operator_events_returns_recent_operator_events(monkeypatch) -> None:
    cursor = FakeCursor()
    cursor.rows = [
        (
            "ledger-1",
            "operator_context_built",
            "low",
            '{"query": "today"}',
            '{"signals_count": 2}',
            "completed",
            None,
            '{"operator_channel": "web", "credit_charged": false}',
            "2026-05-20 10:00:00+00",
        )
    ]

    monkeypatch.setattr(operator_audit, "ensure_agent_security_tables", lambda cursor: None)

    events = operator_audit.list_operator_events(cursor, business_id="biz-1", limit=10)

    assert len(events) == 1
    assert events[0]["id"] == "ledger-1"
    assert events[0]["event_type"] == "operator_context_built"
    assert events[0]["metadata"]["operator_channel"] == "web"
    assert events[0]["metadata"]["credit_charged"] is False
    query, params = cursor.executed[0]
    assert "from agent_action_ledger" in query
    assert params[0] == "biz-1"
    assert params[1] == operator_audit.OPERATOR_CAPABILITY
