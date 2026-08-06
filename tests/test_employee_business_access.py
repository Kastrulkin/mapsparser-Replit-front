import main
from services import content_plan_service


class AccessCursor:
    def __init__(self):
        self.one = None
        self.many = []

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
        elif "select owner_id, name, business_type" in normalized:
            self.one = {
                "owner_id": "owner-1",
                "name": "Shared network location",
                "business_type": "beauty",
                "address": "Prospekt Engelsa, 154",
                "working_hours": "",
                "is_active": True,
                "city": "Saint Petersburg",
                "geo_lat": None,
                "geo_lon": None,
                "site": "",
                "website": "",
            }
        elif "from businessprofiles" in normalized:
            self.one = None
        elif "select id, email, name, phone from users" in normalized:
            self.one = {"id": "owner-1", "email": "owner@example.com", "name": "Owner", "phone": ""}
        elif "select coalesce(is_superadmin, false)" in normalized:
            self.one = {"coalesce": False}
        elif "to_regclass('public.tokenusage')" in normalized:
            self.one = {"tokenusage_table": None}

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


def test_network_member_can_read_shared_business_profile(monkeypatch):
    monkeypatch.setattr(main, "verify_session", _network_member_session)
    monkeypatch.setattr(main, "DatabaseManager", AccessDatabase)

    response = main.app.test_client().get(
        "/api/client-info?business_id=business-1",
        headers={"Authorization": "Bearer member-token"},
    )

    assert response.status_code == 200
    assert response.get_json()["businessName"] == "Shared network location"


def test_network_member_can_read_shared_business_token_usage(monkeypatch):
    monkeypatch.setattr(main, "verify_session", _network_member_session)
    monkeypatch.setattr(main, "DatabaseManager", AccessDatabase)
    monkeypatch.setattr(main, "get_business_owner_id", lambda cursor, business_id: "owner-1")

    response = main.app.test_client().get(
        "/api/token-usage?months=1&business_id=business-1",
        headers={"Authorization": "Bearer member-token"},
    )

    assert response.status_code == 200
    assert response.get_json()["success"] is True


def test_network_member_can_load_shared_business_content_context(monkeypatch):
    database = AccessDatabase()
    business = {
        "id": "business-1",
        "name": "Shared network location",
        "network_id": "network-1",
        "city": "Saint Petersburg",
        "address": "Prospekt Engelsa, 154",
    }
    monkeypatch.setattr(content_plan_service, "DatabaseManager", lambda: database)
    monkeypatch.setattr(content_plan_service, "ensure_content_plan_tables", lambda cursor: None)
    monkeypatch.setattr(content_plan_service, "_fetch_business_row", lambda cursor, business_id: business)
    monkeypatch.setattr(content_plan_service, "get_business_owner_id", lambda cursor, business_id: "owner-1")
    monkeypatch.setattr(content_plan_service, "get_subscription_access", lambda business_id: {"automation_access": True})
    monkeypatch.setattr(content_plan_service, "get_allowed_content_plan_horizons", lambda business_id: [14, 30])
    monkeypatch.setattr(
        content_plan_service,
        "_fetch_network_scope_options",
        lambda cursor, row: [{"scope_type": "single_business", "scope_target_id": "business-1", "is_current": True, "label": row["name"]}],
    )
    monkeypatch.setattr(content_plan_service, "_build_scope_business_context", lambda cursor, row, scope_type, target_id: row)
    monkeypatch.setattr(content_plan_service, "_scope_context_business_ids", lambda cursor, row, scope_type, target_id: ["business-1"])
    monkeypatch.setattr(content_plan_service, "_fetch_map_link_count_for_businesses", lambda cursor, ids: 0)
    monkeypatch.setattr(content_plan_service, "_fetch_services_for_businesses", lambda cursor, ids: [])
    monkeypatch.setattr(content_plan_service, "_fetch_custom_seo_keywords_for_businesses", lambda cursor, ids: [])
    monkeypatch.setattr(content_plan_service, "_fetch_seo_keywords_isolated", lambda user_id, business_id: [])
    monkeypatch.setattr(content_plan_service, "_select_context_seo_keywords", lambda ranked, custom, business_name: [])
    monkeypatch.setattr(content_plan_service, "_fetch_sales_signals_for_businesses", lambda cursor, user_id, ids: [])
    monkeypatch.setattr(content_plan_service, "_fetch_recent_news_for_businesses", lambda cursor, user_id, ids: [])
    monkeypatch.setattr(content_plan_service, "_fetch_audit_signals", lambda business_id: [])
    monkeypatch.setattr(content_plan_service, "_load_content_plan_learning_feedback", lambda cursor, business_id: {})

    context = content_plan_service.load_plan_context_for_business(
        "member-1",
        "business-1",
        "single_business",
    )

    assert context["business"]["id"] == "business-1"
