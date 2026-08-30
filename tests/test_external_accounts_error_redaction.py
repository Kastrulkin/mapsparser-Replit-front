from flask import Flask

import auth_encryption
from api import external_accounts_api


class _IntegrationCursor:
    def execute(self, _query, _params=None):
        return None

    def fetchone(self):
        return {"table_name": "externalbusinessaccounts"}


class _IntegrationDatabase:
    def __init__(self):
        self.conn = self

    def cursor(self):
        return _IntegrationCursor()

    def close(self):
        return None

    def is_superadmin(self, _user_id):
        return False


def _app(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(external_accounts_api.external_accounts_bp)
    monkeypatch.setattr(external_accounts_api, "verify_session", lambda _token: {"user_id": "owner-1"})
    monkeypatch.setattr(external_accounts_api, "get_business_owner_id", lambda _cursor, _business_id: "owner-1")
    return app


def test_external_accounts_get_redacts_database_failure(monkeypatch):
    app = _app(monkeypatch)

    def fail_database():
        raise RuntimeError("postgresql://private-user:private-password@database/internal")

    monkeypatch.setattr(external_accounts_api, "DatabaseManager", fail_database)
    response = app.test_client().get(
        "/api/business/business-1/external-accounts",
        headers={"Authorization": "Bearer token", "X-Request-ID": "external-get-redaction"},
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "code": "internal_error",
        "message": "Не удалось получить подключения",
        "request_id": "external-get-redaction",
    }
    assert "private-password" not in response.get_data(as_text=True)


def test_external_accounts_upsert_redacts_encryption_failure(monkeypatch):
    app = _app(monkeypatch)
    monkeypatch.setattr(external_accounts_api, "DatabaseManager", _IntegrationDatabase)

    def fail_encryption(_value):
        raise RuntimeError("encryption-key=private-encryption-secret")

    monkeypatch.setattr(auth_encryption, "encrypt_auth_data", fail_encryption)
    response = app.test_client().post(
        "/api/business/business-1/external-accounts",
        json={"source": "google_business", "auth_data": {"token": "provider-token"}},
        headers={"Authorization": "Bearer token", "X-Request-ID": "external-upsert-redaction"},
    )

    assert response.status_code == 500
    assert response.get_json() == {
        "code": "internal_error",
        "message": "Не удалось сохранить подключение",
        "request_id": "external-upsert-redaction",
    }
    body = response.get_data(as_text=True)
    assert "private-encryption-secret" not in body
    assert "provider-token" not in body
