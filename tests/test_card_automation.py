from core import card_automation


class _FakeConn:
    def __init__(self) -> None:
        self.rollback_calls = 0
        self.commit_calls = 0

    def rollback(self) -> None:
        self.rollback_calls += 1

    def commit(self) -> None:
        self.commit_calls += 1


def test_run_card_automation_action_rolls_back_before_error_event(monkeypatch):
    conn = _FakeConn()
    observed: dict[str, int | str] = {}

    monkeypatch.setattr(card_automation, "ensure_card_automation_tables", lambda _conn: None)
    monkeypatch.setattr(card_automation, "_ensure_settings_row", lambda _conn, _business_id: None)
    monkeypatch.setattr(
        card_automation,
        "_load_settings_row",
        lambda _conn, _business_id: {"review_sync_interval_hours": 24},
    )

    def _boom(_conn, _business_id):
        raise RuntimeError("sql failed before rollback")

    def _record_event(_conn, **kwargs):
        observed["rollback_calls_during_event"] = conn.rollback_calls
        observed["event_status"] = str(kwargs.get("status") or "")

    def _update_runtime(_conn, **kwargs):
        observed["runtime_status"] = str(kwargs.get("status") or "")

    monkeypatch.setattr(card_automation, "_enqueue_review_sync", _boom)
    monkeypatch.setattr(card_automation, "_record_event", _record_event)
    monkeypatch.setattr(card_automation, "_update_action_runtime", _update_runtime)

    result = card_automation.run_card_automation_action(
        conn,
        business_id="biz_1",
        action_type=card_automation.ACTION_REVIEW_SYNC,
        triggered_by="scheduler",
    )

    assert result["success"] is False
    assert result["status"] == "error"
    assert observed["rollback_calls_during_event"] == 1
    assert observed["event_status"] == "error"
    assert observed["runtime_status"] == "error"
    assert conn.commit_calls == 1


def test_run_card_automation_action_returns_error_even_if_error_logging_fails(monkeypatch):
    conn = _FakeConn()

    monkeypatch.setattr(card_automation, "ensure_card_automation_tables", lambda _conn: None)
    monkeypatch.setattr(card_automation, "_ensure_settings_row", lambda _conn, _business_id: None)
    monkeypatch.setattr(
        card_automation,
        "_load_settings_row",
        lambda _conn, _business_id: {"review_sync_interval_hours": 24},
    )
    monkeypatch.setattr(
        card_automation,
        "_enqueue_review_sync",
        lambda _conn, _business_id: (_ for _ in ()).throw(RuntimeError("queue failure")),
    )

    def _broken_record_event(_conn, **kwargs):
        raise RuntimeError("cannot write error event")

    monkeypatch.setattr(card_automation, "_record_event", _broken_record_event)
    monkeypatch.setattr(card_automation, "_update_action_runtime", lambda _conn, **kwargs: None)

    result = card_automation.run_card_automation_action(
        conn,
        business_id="biz_1",
        action_type=card_automation.ACTION_REVIEW_SYNC,
        triggered_by="scheduler",
    )

    assert result["success"] is False
    assert result["status"] == "error"
    assert result["message"] == "queue failure"
    assert conn.rollback_calls == 2
    assert conn.commit_calls == 0


class _BusinessCursor:
    def __init__(self, row):
        self.row = row
        self.executed: list[str] = []

    def execute(self, query, params):
        self.executed.append(" ".join(str(query).split()))

    def fetchone(self):
        return self.row


class _BusinessConn:
    def __init__(self, row):
        self.cursor_obj = _BusinessCursor(row)

    def cursor(self):
        return self.cursor_obj


def test_business_context_prefers_ai_agent_language_column(monkeypatch):
    conn = _BusinessConn(
        {
            "id": "biz_1",
            "owner_id": "user_1",
            "name": "Capri",
            "language": "ru",
            "address": "Кудрово",
        }
    )

    def _fake_has_column(_cursor, table_name, column_name):
        return table_name == "businesses" and column_name == "ai_agent_language"

    monkeypatch.setattr(card_automation, "_table_has_column", _fake_has_column)

    result = card_automation._business_context(conn, "biz_1")

    assert result["language"] == "ru"
    assert "ai_agent_language AS language" in conn.cursor_obj.executed[0]
