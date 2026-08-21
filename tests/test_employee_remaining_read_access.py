import main
import yookassa_integration
from api import external_accounts_api
from services import content_plan_service


class AccessCursor:
    def __init__(self):
        self.one = None
        self.many = []
        self.description = []

    def execute(self, query, params=None):
        normalized = " ".join(str(query).split()).lower()
        self.one = None
        self.many = []
        if "exists ( select 1 from business_members" in normalized:
            self.one = {
                "owner_id": "owner-1",
                "has_business_membership": False,
                "has_network_membership": True,
            }
        elif "select owner_id from businesses" in normalized:
            self.one = {"owner_id": "owner-1"}
        elif "select id, network_id, owner_id, name from businesses" in normalized:
            self.one = {
                "id": "business-1",
                "network_id": "network-1",
                "owner_id": "owner-1",
                "name": "Shared network location",
            }
        elif "select coalesce(is_superadmin, false)" in normalized:
            self.one = {"coalesce": False}

    def fetchone(self):
        return self.one

    def fetchall(self):
        return list(self.many)


class AccessDatabase:
    def __init__(self):
        self.cursor_value = AccessCursor()
        self.conn = self

    def cursor(self):
        return self.cursor_value

    def is_superadmin(self, user_id):
        return False

    def close(self):
        return None


def _network_member_session(_token):
    return {"user_id": "member-1", "id": "member-1", "is_superadmin": False}


def _auth_headers():
    return {"Authorization": "Bearer member-token"}


def test_network_member_can_list_shared_business_content_plans(monkeypatch):
    database = AccessDatabase()
    monkeypatch.setattr(content_plan_service, "DatabaseManager", lambda: database)
    monkeypatch.setattr(content_plan_service, "ensure_content_plan_tables", lambda cursor: None)
    monkeypatch.setattr(content_plan_service, "get_business_owner_id", lambda cursor, business_id: "owner-1")

    plans = content_plan_service.list_content_plans("member-1", "business-1")

    assert plans == []


def test_network_member_can_read_shared_business_billing_status():
    allowed = yookassa_integration._subscription_access_allowed(
        AccessCursor(),
        user_id="member-1",
        user_data={"user_id": "member-1", "is_superadmin": False},
        row={"user_id": "owner-1", "business_id": "business-1"},
    )

    assert allowed is True


def test_network_member_can_read_shared_business_parse_status(monkeypatch):
    monkeypatch.setattr(main, "verify_session", _network_member_session)
    monkeypatch.setattr(main, "DatabaseManager", AccessDatabase)
    monkeypatch.setattr(main, "get_business_owner_id", lambda cursor, business_id: "owner-1")

    response = main.app.test_client().get(
        "/api/business/business-1/parse-status",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_network_member_can_read_shared_business_competitors(monkeypatch):
    monkeypatch.setattr(main, "verify_session", _network_member_session)
    monkeypatch.setattr(main, "DatabaseManager", AccessDatabase)
    monkeypatch.setattr(main, "get_business_owner_id", lambda cursor, business_id: "owner-1")

    response = main.app.test_client().get(
        "/api/business/business-1/competitors/manual",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    assert response.get_json()["competitors"] == []


def test_network_member_can_read_shared_business_external_summary(monkeypatch):
    monkeypatch.setattr(external_accounts_api, "verify_session", _network_member_session)
    monkeypatch.setattr(external_accounts_api, "DatabaseManager", AccessDatabase)
    monkeypatch.setattr(external_accounts_api, "get_business_owner_id", lambda cursor, business_id: "owner-1")

    response = main.app.test_client().get(
        "/api/business/business-1/external/summary",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_network_member_can_read_shared_business_external_reviews(monkeypatch):
    monkeypatch.setattr(external_accounts_api, "verify_session", _network_member_session)
    monkeypatch.setattr(external_accounts_api, "DatabaseManager", AccessDatabase)
    monkeypatch.setattr(external_accounts_api, "get_business_owner_id", lambda cursor, business_id: "owner-1")

    response = main.app.test_client().get(
        "/api/business/business-1/external/reviews",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_network_member_can_read_shared_business_external_posts(monkeypatch):
    monkeypatch.setattr(external_accounts_api, "verify_session", _network_member_session)
    monkeypatch.setattr(external_accounts_api, "DatabaseManager", AccessDatabase)
    monkeypatch.setattr(external_accounts_api, "get_business_owner_id", lambda cursor, business_id: "owner-1")

    response = main.app.test_client().get(
        "/api/business/business-1/external/posts",
        headers=_auth_headers(),
    )

    assert response.status_code == 200
    assert response.get_json()["posts"] == []
