import main
from legacy_routes import auth_admin


def test_login_allows_active_network_member_without_owned_businesses(monkeypatch):
    calls = []

    class FakeDatabaseManager:
        def is_superadmin(self, user_id):
            return False

        def get_businesses_by_owner(self, user_id):
            calls.append(("owned", user_id))
            return []

        def get_businesses_for_user_access(self, user_id):
            calls.append(("accessible", user_id))
            return [{"id": "business-1", "name": "Shared network location"}]

        def close(self):
            return None

    monkeypatch.setattr(
        main,
        "authenticate_user",
        lambda email, password: {
            "id": "member-1",
            "email": email,
            "name": "Network member",
            "phone": "",
        },
    )
    monkeypatch.setattr(main, "DatabaseManager", FakeDatabaseManager)
    monkeypatch.setattr(main, "create_session", lambda user_id: "session-token")

    response = auth_admin.app.test_client().post(
        "/api/auth/login",
        json={"email": "member@example.com", "password": "secret-password"},
    )

    assert response.status_code == 200
    assert response.get_json()["token"] == "session-token"
    assert calls == [("accessible", "member-1")]
