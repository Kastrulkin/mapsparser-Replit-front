from core.auth_context import AuthContext


class _ReadCursor:
    def __init__(self):
        self.queries = []

    def execute(self, query, params=()):
        normalized = " ".join(str(query).lower().split())
        assert not normalized.startswith(("create ", "alter ", "drop "))
        self.queries.append(normalized)

    def fetchone(self):
        return None

    def fetchall(self):
        return []


def test_average_ticket_read_helpers_never_create_schema():
    from api.average_ticket_api import _load_events, _load_latest_matrix, _load_packages

    cursor = _ReadCursor()
    assert _load_latest_matrix(cursor, "business-1") is None
    assert _load_events(cursor, "business-1") == []
    assert _load_packages(cursor, "business-1") == []
    assert cursor.queries


def test_sales_room_analytics_read_never_bootstraps_schema():
    from api.prospecting.analytics_routes import _load_latest_sales_room_url_for_lead

    cursor = _ReadCursor()
    cursor.connection = object()
    assert _load_latest_sales_room_url_for_lead(cursor, "lead-1") == ""


def test_content_voice_auth_uses_shared_membership_check_and_demo_scope(monkeypatch):
    from services import content_voice_service

    calls = []

    def verify(cursor, business_id, user_data):
        calls.append((business_id, user_data))
        return True, "owner-1"

    monkeypatch.setattr(content_voice_service, "verify_business_access", verify)
    auth = AuthContext(user_id="member-1", session_kind="standard")
    assert content_voice_service._verify_access(object(), auth, "business-1") is auth
    assert calls[0][1]["user_id"] == "member-1"

    demo = AuthContext(user_id="demo-1", session_kind="demo", scope_business_id="business-1")
    assert content_voice_service._verify_access(object(), demo, "business-1") is demo
    try:
        content_voice_service._verify_access(object(), demo, "business-2")
    except PermissionError:
        pass
    else:
        raise AssertionError("demo context crossed its business scope")
