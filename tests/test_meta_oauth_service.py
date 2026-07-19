import sys
import urllib.parse
import base64
import hashlib
import hmac
import json

import pytest


if "src" not in sys.path:
    sys.path.insert(0, "src")

from services import meta_oauth_service


def _signed_deletion_request(payload, secret):
    encoded_payload = base64.urlsafe_b64encode(
        json.dumps(payload, separators=(",", ":")).encode("utf-8")
    ).decode("ascii").rstrip("=")
    signature = hmac.new(
        secret.encode("utf-8"),
        encoded_payload.encode("ascii"),
        hashlib.sha256,
    ).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).decode("ascii").rstrip("=")
    return f"{encoded_signature}.{encoded_payload}"


def test_meta_oauth_state_rejects_tampering(monkeypatch):
    monkeypatch.setenv("META_OAUTH_STATE_SECRET", "test-meta-state-secret")
    state = meta_oauth_service.encode_meta_oauth_state(
        {
            "business_id": "business-1",
            "user_id": "user-1",
        }
    )

    payload = meta_oauth_service.decode_meta_oauth_state(state)
    assert payload["business_id"] == "business-1"

    replacement = "A" if state[-1] != "A" else "B"
    with pytest.raises(meta_oauth_service.MetaOAuthError) as error:
        meta_oauth_service.decode_meta_oauth_state(f"{state[:-1]}{replacement}")

    assert error.value.code == "invalid_state"


def test_meta_authorization_url_requests_publish_permissions(monkeypatch):
    monkeypatch.setenv("META_OAUTH_APP_ID", "meta-app-id")
    monkeypatch.setenv("META_OAUTH_CONFIG_ID", "meta-config-id")
    monkeypatch.setenv("META_OAUTH_REDIRECT_URI", "https://localos.pro/api/meta/oauth/callback")
    monkeypatch.setenv("META_GRAPH_API_VERSION", "v25.0")

    url = meta_oauth_service.build_meta_authorization_url(state="signed-state")

    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parsed.query)
    assert parsed.netloc == "www.facebook.com"
    assert parsed.path == "/v25.0/dialog/oauth"
    assert query["client_id"] == ["meta-app-id"]
    assert query["config_id"] == ["meta-config-id"]
    assert query["redirect_uri"] == ["https://localos.pro/api/meta/oauth/callback"]
    assert set(query["scope"][0].split(",")) == set(meta_oauth_service.META_OAUTH_SCOPES)


def test_meta_assets_normalize_page_and_linked_instagram(monkeypatch):
    monkeypatch.setattr(
        meta_oauth_service,
        "_graph_request",
        lambda path, params, access_token=None: {
            "data": [
                {
                    "id": "page-1",
                    "name": "Riderra",
                    "access_token": "page-token",
                    "tasks": ["CREATE_CONTENT", "MODERATE"],
                    "instagram_business_account": {
                        "id": "ig-1",
                        "username": "riderra",
                        "name": "Riderra",
                    },
                }
            ]
        },
    )

    assets = meta_oauth_service.list_meta_assets("user-token")

    assert len(assets) == 1
    assert assets[0]["page_id"] == "page-1"
    assert assets[0]["page_access_token"] == "page-token"
    assert assets[0]["ig_user_id"] == "ig-1"
    assert assets[0]["ig_username"] == "riderra"
    assert "page_access_token" not in meta_oauth_service.public_meta_asset(assets[0])


def test_meta_access_check_reports_missing_permissions(monkeypatch):
    monkeypatch.setenv("META_OAUTH_APP_ID", "meta-app-id")
    monkeypatch.setenv("META_OAUTH_APP_SECRET", "meta-app-secret")
    monkeypatch.setattr(
        meta_oauth_service,
        "_graph_request",
        lambda path, params, access_token=None: {
            "data": {
                "is_valid": True,
                "user_id": "user-1",
                "app_id": "meta-app-id",
                "scopes": ["pages_show_list"],
            }
        },
    )

    inspection = meta_oauth_service.inspect_meta_access_token("user-token")

    assert inspection["user_id"] == "user-1"
    assert "pages_manage_posts" in inspection["missing_scopes"]
    assert "instagram_content_publish" in inspection["missing_scopes"]


def test_meta_data_deletion_request_verifies_signature(monkeypatch):
    monkeypatch.setenv("META_OAUTH_APP_SECRET", "meta-app-secret")
    signed_request = _signed_deletion_request(
        {"algorithm": "HMAC-SHA256", "user_id": "meta-user-1"},
        "meta-app-secret",
    )

    payload = meta_oauth_service.decode_meta_data_deletion_request(signed_request)

    assert payload["user_id"] == "meta-user-1"


def test_meta_data_deletion_request_rejects_wrong_signature(monkeypatch):
    monkeypatch.setenv("META_OAUTH_APP_SECRET", "meta-app-secret")
    signed_request = _signed_deletion_request(
        {"algorithm": "HMAC-SHA256", "user_id": "meta-user-1"},
        "wrong-secret",
    )

    with pytest.raises(meta_oauth_service.MetaOAuthError) as error:
        meta_oauth_service.decode_meta_data_deletion_request(signed_request)

    assert error.value.code == "invalid_deletion_signature"
