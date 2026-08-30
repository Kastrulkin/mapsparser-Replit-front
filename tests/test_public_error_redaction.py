import main
import auth_system


class _SetPasswordCursor:
    def __init__(self):
        self.query = ""

    def execute(self, query, _params=None):
        self.query = query

    def fetchall(self):
        return [
            {"column_name": "email_verified_at"},
            {"column_name": "personal_data_consent_at"},
            {"column_name": "personal_data_consent_version"},
            {"column_name": "privacy_accepted_at"},
            {"column_name": "terms_accepted_at"},
            {"column_name": "consent_ip"},
            {"column_name": "consent_user_agent"},
        ]

    def fetchone(self):
        if "FROM users" not in self.query:
            return None
        return {
            "id": "user-1",
            "email": "owner@example.com",
            "name": "Owner",
            "phone": "+70000000000",
            "password_hash": None,
            "verification_token": "setup-token",
        }


class _SetPasswordConnection:
    def cursor(self):
        return _SetPasswordCursor()

    def commit(self):
        return None

    def close(self):
        return None


def test_password_reset_does_not_expose_database_exception(monkeypatch):
    secret = "postgresql://private-user:private-password@database/internal"

    def fail_connection():
        raise RuntimeError(secret)

    monkeypatch.setattr(main, "get_db_connection", fail_connection)
    response = main.app.test_client().post(
        "/api/auth/reset-password",
        json={"email": "owner@example.com"},
        headers={"X-Request-ID": "password-reset-redaction"},
    )

    payload = response.get_json()
    assert response.status_code == 500
    assert payload == {
        "code": "internal_error",
        "message": "Не удалось обработать запрос на восстановление пароля",
        "request_id": "password-reset-redaction",
    }
    assert secret not in response.get_data(as_text=True)


def test_public_registration_does_not_expose_provider_exception(monkeypatch):
    secret = "smtp-password-from-provider"

    def fail_email(*_args, **_kwargs):
        raise RuntimeError(secret)

    monkeypatch.setattr(main, "send_email", fail_email)
    response = main.app.test_client().post(
        "/api/public/request-registration",
        json={"email": "owner@example.com"},
        headers={"X-Request-ID": "registration-redaction"},
    )

    payload = response.get_json()
    assert response.status_code == 500
    assert payload == {
        "code": "internal_error",
        "message": "Не удалось принять заявку на регистрацию",
        "request_id": "registration-redaction",
    }
    assert secret not in response.get_data(as_text=True)


def test_set_password_uses_http_only_cookie_without_exposing_token(monkeypatch):
    monkeypatch.setenv("BROWSER_COOKIE_AUTH_ENABLED", "true")
    monkeypatch.setenv("BROWSER_COOKIE_AUTH_SECURE", "false")
    monkeypatch.setattr(main, "get_db_connection", lambda: _SetPasswordConnection())
    monkeypatch.setattr(auth_system, "set_password", lambda _user_id, _password: {"success": True})
    monkeypatch.setattr(main, "create_session", lambda *_args, **_kwargs: "private-session-token")

    response = main.app.test_client().post(
        "/api/auth/set-password",
        json={
            "email": "owner@example.com",
            "password": "strong-password",
            "token": "setup-token",
            "personal_data_consent": True,
        },
    )

    payload = response.get_json()
    assert response.status_code == 200
    assert payload["success"] is True
    assert "token" not in payload
    cookies = response.headers.getlist("Set-Cookie")
    assert any("localos_session=private-session-token" in cookie and "HttpOnly" in cookie for cookie in cookies)
    assert "private-session-token" not in response.get_data(as_text=True)
