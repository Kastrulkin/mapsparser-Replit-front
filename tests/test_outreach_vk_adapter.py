import sys
import urllib.parse
from pathlib import Path

import pytest


if "src" not in sys.path:
    sys.path.insert(0, "src")

from services import outreach_vk_adapter, vk_oauth_service


def test_vk_outreach_oauth_requests_messages_only(monkeypatch):
    monkeypatch.setenv("VK_OAUTH_CLIENT_ID", "vk-client-id")
    monkeypatch.setenv("VK_OAUTH_REDIRECT_URI", "https://localos.pro/api/vk/oauth/callback")

    url = vk_oauth_service.build_vk_authorization_url(
        state="signed-state",
        code_challenge="c" * 43,
        scopes=outreach_vk_adapter.VK_OUTREACH_SCOPES,
    )

    query = urllib.parse.parse_qs(urllib.parse.urlsplit(url).query)
    assert query["scope"] == ["messages"]


def test_vk_outreach_preflight_reads_zero_conversations_and_does_not_send(monkeypatch):
    calls = []

    def fake_call(method, access_token, params):
        calls.append((method, params))
        if method == "users.get":
            return [{"id": 42, "first_name": "Александр", "last_name": "Демьянов", "screen_name": "alex"}]
        if method == "messages.getConversations":
            return {"count": 0, "items": []}
        raise AssertionError(method)

    monkeypatch.setattr(outreach_vk_adapter, "vk_api_call", fake_call)

    result = outreach_vk_adapter.verify_vk_outreach_access("token")

    assert result["user_id"] == "42"
    assert result["profile_url"] == "https://vk.com/alex"
    assert result["capabilities"] == {
        "direct_send": True,
        "reply_sync": True,
        "provider": "vk_user_api",
    }
    assert ("messages.getConversations", {"count": 0}) in calls
    assert all(method != "messages.send" for method, _params in calls)


def test_vk_profile_type_error_is_actionable_and_never_attempts_send(monkeypatch):
    error = outreach_vk_adapter.classify_vk_api_error({
        "error_code": 1051,
        "error_msg": "Method is not available for this profile type: method is unavailable with current profile type",
    })

    assert error.code == "vk_profile_type_unsupported"
    assert "личных сообщений" in str(error).lower()


def test_vk_id_profile_token_is_rejected_before_any_vk_api_call(monkeypatch):
    calls = []

    def fake_call(method, access_token, params):
        calls.append((method, params))
        raise AssertionError("VK API must not be called for an unsupported profile token")

    monkeypatch.setattr(outreach_vk_adapter, "vk_api_call", fake_call)

    with pytest.raises(outreach_vk_adapter.VkOutreachAdapterError) as error:
        outreach_vk_adapter.verify_vk_outreach_access("vk2.a.test-token")

    assert error.value.code == "vk_profile_type_unsupported"
    assert calls == []


def test_vk_community_preflight_binds_token_to_group_and_never_sends(monkeypatch):
    calls = []

    def fake_call(method, access_token, params):
        calls.append((method, params))
        if method == "groups.getTokenPermissions":
            return {"permissions": [{"name": "messages", "setting": 4096}]}
        if method == "groups.getById":
            return {"groups": [{
                "id": 123,
                "name": "Покупай мою шаверму",
                "screen_name": "localospro",
                "photo_200": "https://example.test/avatar.jpg",
            }]}
        if method == "groups.getLongPollSettings":
            return {"is_enabled": 1, "events": {"message_new": 1}}
        if method == "messages.getConversations":
            return {"count": 0, "items": []}
        raise AssertionError(method)

    monkeypatch.setattr(outreach_vk_adapter, "vk_api_call", fake_call)

    result = outreach_vk_adapter.verify_vk_community_access(
        "community-token",
        "https://vk.ru/localospro",
    )

    assert result["group_id"] == "123"
    assert result["display_name"] == "Покупай мою шаверму"
    assert result["profile_url"] == "https://vk.ru/localospro"
    assert result["capabilities"]["provider"] == "vk_community_api"
    assert ("groups.getLongPollSettings", {"group_id": "123"}) in calls
    assert ("messages.getConversations", {"count": 0}) in calls
    assert all(method != "messages.send" for method, _params in calls)


def test_vk_community_preflight_requires_messages_permission(monkeypatch):
    monkeypatch.setattr(
        outreach_vk_adapter,
        "vk_api_call",
        lambda method, access_token, params: {"permissions": [{"name": "wall", "setting": 8192}]},
    )

    with pytest.raises(outreach_vk_adapter.VkOutreachAdapterError) as error:
        outreach_vk_adapter.verify_vk_community_access("community-token", "localospro")

    assert error.value.code == "vk_group_messages_permission_required"


def test_vk_community_send_reports_community_provider(monkeypatch):
    monkeypatch.setenv("OUTREACH_VK_SECRET_KEY", "v" * 40)
    sender = {
        "id": "sender-community",
        "auth_data_encrypted": outreach_vk_adapter.encrypt_vk_outreach_config({
            "access_token": "community-token",
            "account_kind": "community",
            "group_id": "123",
        }),
    }

    calls = []

    def fake_call(method, access_token, params):
        calls.append((method, params))
        if method == "utils.resolveScreenName":
            return {"type": "user", "object_id": 42}
        if method == "messages.send":
            return 777
        raise AssertionError(method)

    monkeypatch.setattr(outreach_vk_adapter, "vk_api_call", fake_call)

    result = outreach_vk_adapter.send_vk_message(
        sender,
        recipient_value="https://vk.com/id42",
        body="Здравствуйте!",
        idempotency_key="community-touch-1",
    )

    assert result["provider_name"] == "vk_community_api"
    assert result["provider_message_id"] == "777"
    send_params = next(params for method, params in calls if method == "messages.send")
    assert send_params["group_id"] == "123"


def test_vk_community_token_is_not_sent_to_oauth_refresh(monkeypatch):
    monkeypatch.setenv("OUTREACH_VK_SECRET_KEY", "v" * 40)
    sender = {
        "auth_data_encrypted": outreach_vk_adapter.encrypt_vk_outreach_config({
            "access_token": "community-token",
            "account_kind": "community",
            "group_id": "123",
            "expires_at": "2020-01-01T00:00:00+00:00",
        }),
    }
    monkeypatch.setattr(
        outreach_vk_adapter,
        "refresh_vk_oauth_tokens",
        lambda **kwargs: pytest.fail("Community keys are not VK ID refresh tokens"),
    )

    config, encrypted = outreach_vk_adapter.ensure_vk_outreach_config(sender)

    assert config["account_kind"] == "community"
    assert encrypted is None


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("https://vk.com/id42", {"recipient_kind": "user_id", "recipient_value": "42"}),
        ("https://vk.com/alex.local", {"recipient_kind": "domain", "recipient_value": "alex.local"}),
        ("@alex_local", {"recipient_kind": "domain", "recipient_value": "alex_local"}),
        ("https://vk.com/feed", None),
        ("https://example.com/id42", None),
    ],
)
def test_vk_recipient_normalization(raw, expected):
    assert outreach_vk_adapter.normalize_vk_recipient(raw) == expected


def test_vk_send_uses_stable_random_id_and_personal_peer(monkeypatch):
    monkeypatch.setenv("OUTREACH_VK_SECRET_KEY", "v" * 40)
    sender = {
        "id": "sender-1",
        "auth_data_encrypted": outreach_vk_adapter.encrypt_vk_outreach_config({"access_token": "token"}),
    }
    calls = []

    def fake_call(method, access_token, params):
        calls.append((method, access_token, params))
        if method == "utils.resolveScreenName":
            return {"type": "user", "object_id": 42}
        if method == "messages.send":
            return 501
        raise AssertionError(method)

    monkeypatch.setattr(outreach_vk_adapter, "vk_api_call", fake_call)

    first = outreach_vk_adapter.send_vk_message(
        sender,
        recipient_value="https://vk.com/alex",
        body="Здравствуйте!",
        idempotency_key="outreach:queue-1",
    )
    second = outreach_vk_adapter.send_vk_message(
        sender,
        recipient_value="https://vk.com/alex",
        body="Здравствуйте!",
        idempotency_key="outreach:queue-1",
    )

    send_calls = [params for method, _token, params in calls if method == "messages.send"]
    assert first["provider_message_id"] == "501"
    assert first["recipient_value"] == "42"
    assert send_calls[0]["random_id"] == send_calls[1]["random_id"]
    assert send_calls[0]["peer_id"] == "42"


def test_vk_outreach_token_refresh_keeps_messages_scope(monkeypatch):
    monkeypatch.setenv("OUTREACH_VK_SECRET_KEY", "v" * 40)
    sender = {
        "auth_data_encrypted": outreach_vk_adapter.encrypt_vk_outreach_config({
            "access_token": "expired-token",
            "refresh_token": "refresh-token",
            "device_id": "device-1",
            "expires_at": "2020-01-01T00:00:00+00:00",
        }),
    }
    observed = {}

    def fake_refresh(*, refresh_token, device_id, scopes):
        observed.update({
            "refresh_token": refresh_token,
            "device_id": device_id,
            "scopes": scopes,
        })
        return {"access_token": "fresh-token", "refresh_token": "fresh-refresh", "expires_in": 3600}

    monkeypatch.setattr(outreach_vk_adapter, "refresh_vk_oauth_tokens", fake_refresh)

    config, encrypted = outreach_vk_adapter.ensure_vk_outreach_config(sender)

    assert observed == {
        "refresh_token": "refresh-token",
        "device_id": "device-1",
        "scopes": outreach_vk_adapter.VK_OUTREACH_SCOPES,
    }
    assert config["access_token"] == "fresh-token"
    assert encrypted.startswith(outreach_vk_adapter.VK_OUTREACH_CREDENTIAL_PREFIX)


def test_vk_is_an_automatic_campaign_channel_with_runtime_gates():
    campaign_source = Path("src/services/outreach_campaign_service.py").read_text(encoding="utf-8")
    safety_source = Path("src/services/outreach_safety_service.py").read_text(encoding="utf-8")
    worker_source = Path("src/worker.py").read_text(encoding="utf-8")

    assert 'AUTOMATIC_CHANNELS = {"telegram", "email", "vk"}' in campaign_source
    assert 'item.get("channel") in {"telegram", "email", "vk"}' in safety_source
    dispatch_block = worker_source[
        worker_source.index("def _dispatch_outreach_queue_if_due"):
        worker_source.index("def _run_card_automation_if_due")
    ]
    assert "sync_vk_replies" in dispatch_block
    assert dispatch_block.index("sync_vk_replies(") < dispatch_block.index("dispatch_due_outreach_queue(")


def test_vk_reply_sync_only_reads_campaign_peers():
    source = Path("src/services/outreach_vk_reply_service.py").read_text(encoding="utf-8")

    assert "q.channel = 'vk'" in source
    assert "q.provider_name IN ('vk_user_api', 'vk_community_api')" in source
    assert "q.delivery_status IN ('sent', 'delivered')" in source
    assert "fetch_vk_replies(" in source
    assert "messages.getConversations" not in source


def test_vk_platform_oauth_returns_to_platform_sender_scope():
    source = Path("src/api/outreach_campaign_api.py").read_text(encoding="utf-8")

    assert 'return_to += "&sender_scope=platform"' in source
