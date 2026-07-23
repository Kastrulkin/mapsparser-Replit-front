from __future__ import annotations

import sys
from types import ModuleType


oauthlib_package = ModuleType("google_auth_oauthlib")
oauthlib_flow_module = ModuleType("google_auth_oauthlib.flow")
oauthlib_flow_module.Flow = object
sys.modules.setdefault("google_auth_oauthlib", oauthlib_package)
sys.modules.setdefault("google_auth_oauthlib.flow", oauthlib_flow_module)

from google_sheets_auth import (
    GOOGLE_ACCOUNT_EMAIL_SCOPE,
    GOOGLE_ACCOUNT_INFO_URL,
    GOOGLE_OPENID_SCOPE,
    GOOGLE_SHEETS_SCOPE,
    GoogleSheetsAuth,
)


class FakeFlow:
    def __init__(self) -> None:
        self.authorization_kwargs: dict[str, str] = {}

    def authorization_url(self, **kwargs):
        self.authorization_kwargs = kwargs
        return "https://accounts.google.com/o/oauth2/auth", kwargs["state"]


def test_google_sheets_oauth_forces_account_selection(monkeypatch) -> None:
    monkeypatch.setenv("GOOGLE_SHEETS_CLIENT_ID", "sheets-client.apps.googleusercontent.com")
    monkeypatch.setenv("GOOGLE_SHEETS_CLIENT_SECRET", "secret")
    monkeypatch.setenv(
        "GOOGLE_SHEETS_REDIRECT_URI",
        "https://localos.pro/api/google/sheets/oauth/callback",
    )

    auth = GoogleSheetsAuth()
    flow = FakeFlow()
    monkeypatch.setattr(auth, "_create_flow", lambda: flow)

    authorization_url = auth.get_authorization_url("signed-state")

    assert authorization_url == "https://accounts.google.com/o/oauth2/auth"
    assert auth.scopes == [GOOGLE_SHEETS_SCOPE, GOOGLE_ACCOUNT_EMAIL_SCOPE, GOOGLE_OPENID_SCOPE]
    assert flow.authorization_kwargs == {
        "access_type": "offline",
        "include_granted_scopes": "true",
        "state": "signed-state",
        "prompt": "consent select_account",
    }


def test_google_sheets_identity_uses_verified_email(monkeypatch) -> None:
    class Credentials:
        token = "access-token"

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {
                "email": "Demyanovap@Gmail.com",
                "email_verified": True,
                "name": "Aleksandr Demianov",
            }

    def fake_get(url, **kwargs):
        assert url == GOOGLE_ACCOUNT_INFO_URL
        assert kwargs == {
            "headers": {"Authorization": "Bearer access-token"},
            "timeout": 10,
        }
        return Response()

    monkeypatch.setattr("google_sheets_auth.requests.get", fake_get)

    assert GoogleSheetsAuth().get_account_identity(Credentials()) == {
        "email": "demyanovap@gmail.com",
        "name": "Aleksandr Demianov",
    }


def test_google_sheets_identity_rejects_unverified_email(monkeypatch) -> None:
    class Credentials:
        token = "access-token"

    class Response:
        status_code = 200

        @staticmethod
        def json():
            return {"email": "unknown@example.com", "email_verified": False}

    monkeypatch.setattr("google_sheets_auth.requests.get", lambda *_args, **_kwargs: Response())

    assert GoogleSheetsAuth().get_account_identity(Credentials()) == {}
