from flask import Flask

from api import auth_user_api
from api.prospecting.access_schema import _resolve_business_for_user
from core.auth_helpers import verify_business_access
from services.social_posts import dispatch_reports


class AccessCursor:
    def __init__(self, row):
        self.row = row
        self.executed = []

    def execute(self, query, params):
        self.executed.append((query, params))

    def fetchone(self):
        return self.row


class PartnershipAccessCursor:
    def __init__(self):
        self.row = None

    def execute(self, query, params):
        normalized = " ".join(str(query).split()).lower()
        if "exists ( select 1 from business_members" in normalized:
            self.row = {
                "owner_id": "owner-1",
                "has_business_membership": False,
                "has_network_membership": True,
                "owns_network": False,
            }
        else:
            self.row = None

    def fetchone(self):
        return self.row


def test_network_member_has_business_access():
    cursor = AccessCursor({
        "owner_id": "owner-1",
        "has_business_membership": False,
        "has_network_membership": True,
    })

    allowed, owner_id = verify_business_access(
        cursor,
        "business-1",
        {"user_id": "member-1", "is_superadmin": False},
    )

    assert allowed is True
    assert owner_id == "owner-1"
    assert cursor.executed[0][1] == ("member-1", "member-1", "member-1", "business-1")


def test_partnership_business_resolution_accepts_network_member():
    business_id = _resolve_business_for_user(
        PartnershipAccessCursor(),
        {"user_id": "member-1", "is_superadmin": False},
        "business-1",
    )

    assert business_id == "business-1"


def test_direct_business_member_has_business_access():
    cursor = AccessCursor({
        "owner_id": "owner-1",
        "has_business_membership": True,
        "has_network_membership": False,
    })

    allowed, owner_id = verify_business_access(
        cursor,
        "business-1",
        {"user_id": "member-1", "is_superadmin": False},
    )

    assert allowed is True
    assert owner_id == "owner-1"


def test_business_owner_has_business_access():
    cursor = AccessCursor({
        "owner_id": "owner-1",
        "has_business_membership": False,
        "has_network_membership": False,
        "owns_network": False,
    })

    allowed, owner_id = verify_business_access(
        cursor,
        "business-1",
        {"user_id": "owner-1", "is_superadmin": False},
    )

    assert allowed is True
    assert owner_id == "owner-1"


def test_unrelated_user_does_not_gain_business_access():
    cursor = AccessCursor({
        "owner_id": "owner-1",
        "has_business_membership": False,
        "has_network_membership": False,
    })

    allowed, owner_id = verify_business_access(
        cursor,
        "business-1",
        {"user_id": "other-user", "is_superadmin": False},
    )

    assert allowed is False
    assert owner_id == "owner-1"


def test_network_owner_has_business_access():
    cursor = AccessCursor({
        "owner_id": "owner-1",
        "has_business_membership": False,
        "has_network_membership": False,
        "owns_network": True,
    })

    allowed, owner_id = verify_business_access(
        cursor,
        "business-1",
        {"user_id": "network-owner", "is_superadmin": False},
    )

    assert allowed is True
    assert owner_id == "owner-1"


def test_superadmin_has_business_access():
    cursor = AccessCursor({
        "owner_id": "owner-1",
        "has_business_membership": False,
        "has_network_membership": False,
        "owns_network": False,
    })

    allowed, _ = verify_business_access(
        cursor,
        "business-1",
        {"user_id": "admin-1", "is_superadmin": True},
    )

    assert allowed is True


def test_demo_session_can_open_its_business_scope():
    cursor = AccessCursor({
        "owner_id": "owner-1",
        "has_business_membership": True,
        "has_network_membership": False,
        "owns_network": False,
    })

    allowed, _ = verify_business_access(
        cursor,
        "business-1",
        {
            "user_id": "member-1",
            "session_kind": "demo",
            "scope_business_id": "business-1",
            "is_superadmin": False,
        },
    )

    assert allowed is True


def test_demo_session_cannot_escape_its_business_scope():
    cursor = AccessCursor({
        "owner_id": "owner-1",
        "has_business_membership": True,
        "has_network_membership": False,
        "owns_network": False,
    })

    allowed, owner_id = verify_business_access(
        cursor,
        "business-2",
        {
            "user_id": "member-1",
            "session_kind": "demo",
            "scope_business_id": "business-1",
            "is_superadmin": False,
        },
    )

    assert allowed is False
    assert owner_id is None
    assert cursor.executed == []


def test_auth_me_returns_network_member_businesses(monkeypatch):
    calls = []

    class FakeDatabaseManager:
        def is_superadmin(self, user_id):
            return False

        def get_businesses_for_user_access(self, user_id):
            calls.append(user_id)
            return [{"id": "business-1", "name": "Shared network location"}]

        def close(self):
            return None

    monkeypatch.setattr(
        auth_user_api,
        "verify_session",
        lambda token: {
            "user_id": "member-1",
            "email": "member@example.com",
            "name": "Member",
            "is_active": True,
            "is_superadmin": False,
        },
    )
    monkeypatch.setattr(auth_user_api, "DatabaseManager", FakeDatabaseManager)

    app = Flask(__name__)
    app.register_blueprint(auth_user_api.auth_user_bp)
    response = app.test_client().get(
        "/api/auth/me",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    assert response.get_json()["businesses"][0]["id"] == "business-1"
    assert response.get_json()["businesses"][0]["web_tracking_available"] is False
    assert response.get_json()["businesses"][0]["subscription_access"] == {
        "tier": "none",
        "tier_name": "Без тарифа",
        "status": "inactive",
        "active": False,
        "subscription_expired": False,
        "capabilities": [],
        "groups": {"maps": False, "acquisition": False, "management": False},
    }
    assert calls == ["member-1"]


def test_auth_me_exposes_web_tracking_only_for_pilot_business(monkeypatch):
    class FakeDatabaseManager:
        def is_superadmin(self, user_id):
            return False

        def get_businesses_for_user_access(self, user_id):
            return [
                {"id": "business-1", "name": "Pilot"},
                {"id": "business-2", "name": "Control"},
            ]

        def close(self):
            return None

    monkeypatch.setenv("WEB_TRACKING_ENABLED", "true")
    monkeypatch.setenv("WEB_TRACKING_BUSINESS_IDS", "business-1")
    monkeypatch.setattr(
        auth_user_api,
        "verify_session",
        lambda token: {
            "user_id": "member-1",
            "email": "member@example.com",
            "is_active": True,
        },
    )
    monkeypatch.setattr(auth_user_api, "DatabaseManager", FakeDatabaseManager)

    app = Flask(__name__)
    app.register_blueprint(auth_user_api.auth_user_bp)
    response = app.test_client().get(
        "/api/auth/me",
        headers={"Authorization": "Bearer test-token"},
    )

    assert response.status_code == 200
    businesses = response.get_json()["businesses"]
    assert businesses[0]["web_tracking_available"] is True
    assert businesses[1]["web_tracking_available"] is False


def test_network_member_migration_has_safe_constraints():
    from pathlib import Path

    migration = Path(
        "alembic_migrations/versions/20260729_add_network_members.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision = "20260727_002"' in migration
    assert "UNIQUE (network_id, user_id)" in migration
    assert "status IN ('active', 'revoked')" in migration


def test_business_member_migration_has_safe_constraints():
    from pathlib import Path

    migration = Path(
        "alembic_migrations/versions/20260729_add_business_members.py"
    ).read_text(encoding="utf-8")

    assert 'down_revision = "20260729_001"' in migration
    assert "UNIQUE (business_id, user_id)" in migration
    assert "status IN ('active', 'revoked')" in migration


def test_social_post_access_uses_network_membership(monkeypatch):
    class UserCursor:
        def execute(self, query, params):
            return None

        def fetchone(self):
            return {"coalesce": False}

    calls = []

    def allow_network_member(cursor, business_id, user_data):
        calls.append((business_id, user_data))
        return True, "owner-1"

    monkeypatch.setattr(dispatch_reports, "verify_business_access", allow_network_member)

    dispatch_reports._require_business_access(UserCursor(), "member-1", "business-1")

    assert calls == [
        ("business-1", {"user_id": "member-1", "is_superadmin": False})
    ]
