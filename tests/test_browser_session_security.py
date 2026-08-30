import main
from api import auth_user_api
from legacy_routes import auth_admin


class AccessibleBusinessDatabase:
    def is_superadmin(self, _user_id):
        return False

    def get_businesses_for_user_access(self, _user_id):
        return [{"id": "business-1", "name": "Cookie session business"}]

    def close(self):
        return None


def enable_cookie_auth(monkeypatch):
    monkeypatch.setenv("BROWSER_COOKIE_AUTH_ENABLED", "true")
    monkeypatch.setenv("BROWSER_COOKIE_AUTH_SECURE", "true")


def test_login_uses_http_only_cookie_without_exposing_session_token(monkeypatch):
    enable_cookie_auth(monkeypatch)
    monkeypatch.setattr(
        main,
        "authenticate_user",
        lambda email, _password: {
            "id": "user-1",
            "email": email,
            "name": "Cookie user",
            "phone": "",
        },
    )
    monkeypatch.setattr(main, "DatabaseManager", AccessibleBusinessDatabase)
    monkeypatch.setattr(main, "create_session", lambda _user_id: "session-token")

    response = main.app.test_client().post(
        "/api/auth/login",
        json={"email": "cookie@example.com", "password": "secret-password"},
    )

    payload = response.get_json()
    session_cookie = response.headers.get("Set-Cookie", "")
    assert response.status_code == 200
    assert "token" not in payload
    assert "localos_session=session-token" in session_cookie
    assert "HttpOnly" in session_cookie
    assert "Secure" in session_cookie
    assert "SameSite=Lax" in session_cookie


def test_authenticated_get_accepts_browser_session_cookie(monkeypatch):
    enable_cookie_auth(monkeypatch)
    monkeypatch.setattr(
        auth_user_api,
        "verify_session",
        lambda token: {
            "user_id": "user-1",
            "email": "cookie@example.com",
            "is_active": True,
            "session_kind": "standard",
        }
        if token == "session-token"
        else None,
    )
    monkeypatch.setattr(auth_user_api, "DatabaseManager", AccessibleBusinessDatabase)
    client = main.app.test_client()
    client.set_cookie("localos_session", "session-token")

    response = client.get("/api/auth/me")

    assert response.status_code == 200
    assert response.get_json()["user"]["id"] == "user-1"


def test_cookie_session_requires_matching_csrf_for_mutation(monkeypatch):
    enable_cookie_auth(monkeypatch)
    monkeypatch.setattr(auth_user_api, "logout_session", lambda token: token == "session-token")
    client = main.app.test_client()
    client.set_cookie("localos_session", "session-token")

    rejected = client.post("/api/auth/logout")
    assert rejected.status_code == 403
    assert rejected.get_json()["code"] == "csrf_required"

    client.set_cookie("localos_csrf", "csrf-token")
    accepted = client.post("/api/auth/logout", headers={"X-CSRF-Token": "csrf-token"})
    assert accepted.status_code == 200
    cleared_cookies = accepted.headers.getlist("Set-Cookie")
    assert any("localos_session=" in item and "Max-Age=0" in item for item in cleared_cookies)
    assert any("localos_csrf=" in item and "Max-Age=0" in item for item in cleared_cookies)


def test_bearer_session_remains_available_without_csrf(monkeypatch):
    enable_cookie_auth(monkeypatch)
    monkeypatch.setattr(auth_user_api, "logout_session", lambda token: token == "miniapp-token")

    response = main.app.test_client().post(
        "/api/auth/logout",
        headers={"Authorization": "Bearer miniapp-token"},
    )

    assert response.status_code == 200


def test_auth_internal_error_does_not_expose_exception_details(monkeypatch):
    secret = "postgresql://private-user:private-password@database/internal"

    def fail_logout(_token):
        raise RuntimeError(secret)

    monkeypatch.setattr(auth_user_api, "logout_session", fail_logout)
    response = main.app.test_client().post(
        "/api/auth/logout",
        headers={"Authorization": "Bearer miniapp-token", "X-Request-ID": "auth-redaction-test"},
    )

    payload = response.get_json()
    assert response.status_code == 500
    assert payload == {
        "code": "internal_error",
        "message": "Не удалось завершить сессию",
        "request_id": "auth-redaction-test",
    }
    assert secret not in response.get_data(as_text=True)


def test_email_verification_issues_browser_cookie_without_json_token(monkeypatch):
    enable_cookie_auth(monkeypatch)
    monkeypatch.setattr(
        main,
        "verify_email_token",
        lambda _token: {
            "id": "user-1",
            "email": "cookie@example.com",
            "name": "Cookie user",
            "phone": "",
        },
    )
    monkeypatch.setattr(main, "create_session", lambda *_args, **_kwargs: "verified-session-token")
    monkeypatch.setattr(auth_admin, "journey_enabled", lambda *_args: False)

    response = main.app.test_client().post(
        "/api/auth/verify-email",
        json={"token": "email-verification-token"},
    )

    assert response.status_code == 200
    assert "token" not in response.get_json()
    assert "localos_session=verified-session-token" in response.headers.get("Set-Cookie", "")
