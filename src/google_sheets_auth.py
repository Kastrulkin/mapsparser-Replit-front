#!/usr/bin/env python3
"""Dedicated OAuth client for Google Sheets access."""
import os
from typing import Any, Dict

import requests
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow


GOOGLE_SHEETS_SCOPE = "https://www.googleapis.com/auth/spreadsheets"
GOOGLE_ACCOUNT_EMAIL_SCOPE = "https://www.googleapis.com/auth/userinfo.email"
GOOGLE_OPENID_SCOPE = "openid"
GOOGLE_ACCOUNT_INFO_URL = "https://openidconnect.googleapis.com/v1/userinfo"


class GoogleSheetsAuth:
    def __init__(self):
        self.client_id = os.getenv("GOOGLE_SHEETS_CLIENT_ID")
        self.client_secret = os.getenv("GOOGLE_SHEETS_CLIENT_SECRET")
        self.redirect_uri = os.getenv(
            "GOOGLE_SHEETS_REDIRECT_URI",
            "http://localhost:8000/api/google/sheets/oauth/callback",
        )
        self.scopes = [
            GOOGLE_SHEETS_SCOPE,
            GOOGLE_ACCOUNT_EMAIL_SCOPE,
            GOOGLE_OPENID_SCOPE,
        ]

    def _create_flow(self) -> Flow:
        if not self.client_id or not self.client_secret:
            raise ValueError("GOOGLE_SHEETS_CLIENT_ID and GOOGLE_SHEETS_CLIENT_SECRET must be configured")
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [self.redirect_uri],
                }
            },
            scopes=self.scopes,
            autogenerate_code_verifier=False,
        )
        flow.redirect_uri = self.redirect_uri
        return flow

    def get_authorization_url(self, state: str) -> str:
        authorization_url, _ = self._create_flow().authorization_url(
            access_type="offline",
            include_granted_scopes="true",
            state=state,
            prompt="consent select_account",
        )
        return authorization_url

    def get_credentials_from_code(self, code: str) -> Credentials:
        flow = self._create_flow()
        flow.fetch_token(code=code)
        return flow.credentials

    def refresh_credentials(self, credentials: Credentials) -> Credentials:
        if credentials.expired and credentials.refresh_token:
            credentials.refresh(Request())
        return credentials

    def get_account_identity(self, credentials: Credentials) -> Dict[str, str]:
        token = str(credentials.token or "").strip()
        if not token:
            return {}
        try:
            response = requests.get(
                GOOGLE_ACCOUNT_INFO_URL,
                headers={"Authorization": f"Bearer {token}"},
                timeout=10,
            )
            if response.status_code != 200:
                return {}
            payload = response.json()
        except (requests.RequestException, ValueError):
            return {}
        if not isinstance(payload, dict):
            return {}
        email = str(payload.get("email") or "").strip().lower()
        if not email or payload.get("email_verified") is not True:
            return {}
        name = str(payload.get("name") or "").strip()
        return {"email": email, "name": name}

    def credentials_to_dict(self, credentials: Credentials) -> Dict[str, Any]:
        return {
            "token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "token_uri": credentials.token_uri,
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "scopes": list(credentials.scopes or self.scopes),
        }

    def dict_to_credentials(self, creds_dict: Dict[str, Any]) -> Credentials:
        return Credentials.from_authorized_user_info(creds_dict, scopes=self.scopes)
