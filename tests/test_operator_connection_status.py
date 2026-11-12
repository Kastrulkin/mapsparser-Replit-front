import pytest

from services.operator_connection_status import read_connection_status


@pytest.fixture(autouse=True)
def scope_guard(monkeypatch):
    def require(cursor, *, user_id, scope_kind, scope_id, actor=None, write=False):
        if scope_kind == 'platform':
            from services.operator_platform_outreach import require_platform_actor
            require_platform_actor(cursor, user_id, actor)
        return {'kind': scope_kind, 'id': scope_id}
    monkeypatch.setattr('services.operator_platform_outreach.require_outreach_scope', require)


class Cursor:
    description = []

    def __init__(self, *, admin=False, senders=None):
        self.admin = admin
        self.senders = senders or []
        self.queries = []
        self.rows = []

    def execute(self, query, params=None):
        self.queries.append((query, params))
        if "JOIN users actor" in query:
            self.rows = [{"id": "localos-platform-telegram-radar"}] if self.admin else []
        elif "FROM outreach_sender_accounts" in query:
            self.rows = self.senders
        elif "FROM externalbusinessaccounts" in query:
            self.rows = []
        else:
            raise AssertionError(query)

    def fetchall(self):
        return self.rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


def riderra_sender(**overrides):
    return {"id": "sender-1", "channel": "email", "sender_identity": "riderracs@gmail.com",
            "business_id": "riderra", "business_name": "Riderra", "scope_type": "business",
            "status": "connected", "outreach_enabled": True, "reply_sync": True, **overrides}


def test_operator_finds_saved_email_sender_outside_external_cabinets():
    cursor = Cursor(senders=[riderra_sender()])
    result = read_connection_status(cursor, business_id="riderra", user_id="owner")
    account = result["accounts"][0]
    assert account["external_id"] == "riderracs@gmail.com"
    assert account["business_name"] == "Riderra"
    assert account["reply_sync_enabled"] is True
    assert result["active_count"] == 1
    assert result["external_writes_performed"] is False
    assert "сейчас не выполнялась" in result["evidence"]
    assert "не означает доступ ко всей почте" in result["mail_read_scope"]
    for query, params in cursor.queries:
        assert params == ("riderra",)
        assert "business_id = %s" in query


def test_platform_lookup_rechecks_current_admin_before_any_connection_read():
    cursor = Cursor(admin=False)
    with pytest.raises(PermissionError):
        read_connection_status(cursor, business_id="localos-platform-telegram-radar", user_id="revoked-admin")
    assert len(cursor.queries) == 1
    assert "actor.is_superadmin=TRUE" in cursor.queries[0][0]
    assert "actor.is_active,TRUE" in cursor.queries[0][0]


def test_platform_admin_can_find_riderra_without_switching_business():
    cursor = Cursor(admin=True, senders=[riderra_sender()])
    result = read_connection_status(cursor, business_id="localos-platform-telegram-radar", user_id="admin", query="Riderra")
    assert result["scope"] == "platform"
    assert result["accounts"][0]["external_id"] == "riderracs@gmail.com"
    assert all(params == ("%Riderra%",) * 3 for _, params in cursor.queries[1:])


def test_credentials_and_raw_errors_never_enter_operator_observation():
    cursor = Cursor(senders=[riderra_sender(has_error=True, reply_sync_error="password=secret", auth_data="secret", settings_path="/private")])
    result = read_connection_status(cursor, business_id="riderra", user_id="owner")
    assert "secret" not in str(result)
    assert "settings_path" not in str(result)
    assert result["error_count"] == 1
    assert result["accounts"][0]["last_error"] == "Есть ошибка синхронизации. Проверьте подключение."


def test_disconnected_sender_is_not_claimed_active_and_does_not_sync():
    cursor = Cursor(senders=[riderra_sender(status="disabled", outreach_enabled=False)])
    result = read_connection_status(cursor, business_id="riderra", user_id="owner")
    assert result["active_count"] == 0
    assert result["accounts"][0]["status"] == "disabled"
    assert result["accounts"][0]["reply_sync_enabled"] is False


def test_truncated_connection_list_cannot_prove_mailbox_is_absent():
    cursor = Cursor(senders=[riderra_sender(id=str(index)) for index in range(201)])
    result = read_connection_status(cursor, business_id="riderra", user_id="owner")
    assert result["count"] == 200
    assert result["has_more"] is True
    assert result["absence_is_conclusive"] is False


def test_named_lookup_uses_parameters_and_literal_wildcards():
    cursor = Cursor()
    result = read_connection_status(cursor, business_id="riderra", user_id="owner", query="%_'; DROP TABLE users; --")
    assert result["count"] == 0
    assert result["absence_is_conclusive"] is False
    for query, params in cursor.queries:
        assert "DROP TABLE" not in query
        assert params[0] == "riderra"
        assert params[1] == "%\\%\\_'; DROP TABLE users; --%"


def test_revoked_business_access_blocks_detection_before_reading_accounts(monkeypatch):
    calls = []
    def deny(cursor, **kwargs):
        calls.append(kwargs)
        raise PermissionError('Доступ отозван')
    monkeypatch.setattr('services.operator_platform_outreach.require_outreach_scope', deny)
    cursor = Cursor(senders=[riderra_sender()])
    with pytest.raises(PermissionError):
        read_connection_status(cursor, business_id='riderra', user_id='former-owner', actor={'session_kind': 'demo'})
    assert cursor.queries == []
    assert calls == [{'user_id': 'former-owner', 'scope_kind': 'business', 'scope_id': 'riderra', 'actor': {'session_kind': 'demo'}}]
