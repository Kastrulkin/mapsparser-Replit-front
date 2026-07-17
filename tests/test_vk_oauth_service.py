import sys
import urllib.parse

import pytest


if "src" not in sys.path:
    sys.path.insert(0, "src")

from services import vk_oauth_service


def test_vk_oauth_state_rejects_tampering(monkeypatch):
    monkeypatch.setenv("VK_OAUTH_STATE_SECRET", "test-state-secret")
    state = vk_oauth_service.encode_vk_oauth_state(
        {
            "business_id": "business-1",
            "user_id": "user-1",
            "group_id": "182541984",
        }
    )

    payload = vk_oauth_service.decode_vk_oauth_state(state)
    assert payload["business_id"] == "business-1"

    replacement = "A" if state[-1] != "A" else "B"
    with pytest.raises(vk_oauth_service.VkOAuthError) as error:
        vk_oauth_service.decode_vk_oauth_state(f"{state[:-1]}{replacement}")

    assert error.value.code == "invalid_state"


def test_vk_oauth_state_accepts_compact_callback_state_returned_by_vkid(monkeypatch):
    monkeypatch.setenv("VK_OAUTH_STATE_SECRET", "test-state-secret")
    state = vk_oauth_service.encode_vk_oauth_state(
        {
            "business_id": "business-1",
            "user_id": "user-1",
            "group_id": "182541984",
        }
    )

    payload = vk_oauth_service.decode_vk_oauth_state(state.replace(".", ""))
    legacy_payload = vk_oauth_service.decode_vk_oauth_state(
        f"v1.{state[2:-43]}.{state[-43:]}"
    )

    assert payload["business_id"] == "business-1"
    assert payload["group_id"] == "182541984"
    assert legacy_payload["business_id"] == "business-1"


def test_vk_authorization_url_uses_vkid_pkce_and_publish_scopes(monkeypatch):
    monkeypatch.setenv("VK_OAUTH_CLIENT_ID", "vk-client-id")
    monkeypatch.setenv("VK_OAUTH_REDIRECT_URI", "https://localos.pro/api/vk/oauth/callback")
    challenge = "c" * 43

    url = vk_oauth_service.build_vk_authorization_url(
        state="signed-state",
        code_challenge=challenge,
    )

    parsed = urllib.parse.urlsplit(url)
    query = urllib.parse.parse_qs(parsed.query)
    assert parsed.scheme == "https"
    assert parsed.netloc == "id.vk.com"
    assert parsed.path == "/authorize"
    assert query["client_id"] == ["vk-client-id"]
    assert query["code_challenge"] == [challenge]
    assert query["code_challenge_method"] == ["S256"]
    assert query["redirect_uri"] == ["https://localos.pro/api/vk/oauth/callback"]
    assert set(query["scope"][0].split()) == {"wall", "photos", "groups"}


def test_vk_code_exchange_sends_pkce_verifier(monkeypatch):
    monkeypatch.setenv("VK_OAUTH_CLIENT_ID", "vk-client-id")
    monkeypatch.setenv("VK_OAUTH_REDIRECT_URI", "https://localos.pro/api/vk/oauth/callback")
    captured = {}

    def fake_oauth_request(payload):
        captured.update(payload)
        return {"access_token": "token"}

    monkeypatch.setattr(vk_oauth_service, "_oauth_request", fake_oauth_request)
    verifier = "v" * 43

    result = vk_oauth_service.exchange_vk_authorization_code(
        code="authorization-code",
        device_id="device-id",
        code_verifier=verifier,
    )

    assert result["access_token"] == "token"
    assert captured["grant_type"] == "authorization_code"
    assert captured["client_id"] == "vk-client-id"
    assert captured["code"] == "authorization-code"
    assert captured["device_id"] == "device-id"
    assert captured["code_verifier"] == verifier


def test_vk_access_check_requires_admin_of_selected_group(monkeypatch):
    responses = {
        "account.getAppPermissions": (
            vk_oauth_service.VK_API_PERMISSION_PHOTOS
            | vk_oauth_service.VK_API_PERMISSION_WALL
            | vk_oauth_service.VK_API_PERMISSION_GROUPS
        ),
        "groups.get": {"items": [{"id": 999, "name": "Another group"}]},
    }

    monkeypatch.setattr(
        vk_oauth_service,
        "_vk_api_call",
        lambda method, access_token, params: responses[method],
    )

    with pytest.raises(vk_oauth_service.VkOAuthError) as error:
        vk_oauth_service.verify_vk_oauth_access("user-token", "182541984")

    assert error.value.code == "not_group_admin"


def test_vk_access_check_confirms_selected_group(monkeypatch):
    calls = []
    permissions = (
        vk_oauth_service.VK_API_PERMISSION_PHOTOS
        | vk_oauth_service.VK_API_PERMISSION_WALL
        | vk_oauth_service.VK_API_PERMISSION_GROUPS
    )
    responses = {
        "account.getAppPermissions": permissions,
        "groups.get": {"items": [{"id": 182541984, "name": "Riderra"}]},
        "wall.get": {"count": 0, "items": []},
        "users.get": [{"id": 42}],
    }

    def fake_vk_api_call(method, access_token, params):
        calls.append((method, params))
        return responses[method]

    monkeypatch.setattr(vk_oauth_service, "_vk_api_call", fake_vk_api_call)

    result = vk_oauth_service.verify_vk_oauth_access("user-token", "-182541984")

    assert result["group_id"] == "182541984"
    assert result["owner_id"] == "-182541984"
    assert result["group_name"] == "Riderra"
    assert result["user_id"] == "42"
    assert ("wall.get", {"owner_id": "-182541984", "count": "1", "filter": "owner"}) in calls


def test_vk_id_publish_token_is_rejected_before_legacy_api_call(monkeypatch):
    calls = []

    def fake_vk_api_call(method, access_token, params):
        calls.append((method, access_token, params))
        return 0

    monkeypatch.setattr(vk_oauth_service, "_vk_api_call", fake_vk_api_call)

    with pytest.raises(vk_oauth_service.VkOAuthError) as error:
        vk_oauth_service.verify_vk_oauth_access("vk2.a.identity-token", "182541984")

    assert error.value.code == "vk_id_publish_unsupported"
    assert "публикац" in str(error.value).lower()
    assert calls == []
