import json
import sys
from io import BytesIO
from types import ModuleType
from urllib.error import HTTPError, URLError

import pytest
from services import social_post_service
from services.social_posts import recommendations_handoff


class ProviderResponse:
    def __init__(self, payload: str, status: int = 200, read_error: Exception | None = None):
        self.payload = payload
        self.status = status
        self.read_error = read_error

    def read(self):
        if self.read_error:
            raise self.read_error
        return self.payload.encode("utf-8")

    def close(self):
        return None


def telegram_post():
    return {
        "business_id": "business-1",
        "platform": "telegram",
        "platform_text": "Synthetic message",
    }


def configure_telegram(monkeypatch, response):
    monkeypatch.setattr(social_post_service, "_load_business_publish_context", lambda *_args: {"telegram_chat_id": "@synthetic"})
    monkeypatch.setattr(social_post_service, "_resolve_telegram_publish_transport", lambda *_args: {"bot_token": "synthetic", "token_source": "test"})
    monkeypatch.setattr(social_post_service, "_selected_media_assets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(social_post_service, "telegram_urlopen", response)


def configure_vk(monkeypatch, response, ready=True):
    account = {"id": "vk-account"}
    monkeypatch.setattr(social_post_service, "_find_active_external_account", lambda *_args: account)
    monkeypatch.setattr(social_post_service, "_external_account_auth_data", lambda *_args: {})
    monkeypatch.setattr(social_post_service, "_vk_auth_data_with_fresh_token", lambda *_args: {"api_version": "5.199"})
    monkeypatch.setattr(social_post_service, "_vk_publish_binding", lambda *_args: {"ready": ready, "token": "synthetic", "owner_id": "-12"})
    monkeypatch.setattr(social_post_service, "_selected_media_assets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(social_post_service, "outbound_urlopen", response)


def provider_http_error(status_code: int):
    def raise_error(*_args, **_kwargs):
        raise HTTPError("https://provider.invalid/publish", status_code, "synthetic", None, BytesIO(b'{"error":"synthetic"}'))
    return raise_error


def test_publish_api_contract_marks_preflight_as_not_attempted(monkeypatch):
    monkeypatch.setattr("services.disk_import_media.selected", lambda *_args: False)

    result = recommendations_handoff._publish_api_post(None, {"platform": "unsupported"})

    assert result["publish_outcome"] == "not_attempted"


def test_telegram_publish_contract_accepts_only_positive_message_receipt(monkeypatch):
    monkeypatch.setattr(social_post_service, "_load_business_publish_context", lambda *_args: {"telegram_chat_id": "@synthetic"})
    monkeypatch.setattr(social_post_service, "_resolve_telegram_publish_transport", lambda *_args: {"bot_token": "synthetic", "token_source": "test"})
    monkeypatch.setattr(social_post_service, "_selected_media_assets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(social_post_service, "telegram_urlopen", lambda *_args, **_kwargs: ProviderResponse(json.dumps({"ok": True, "result": {"message_id": 17}})))

    accepted = recommendations_handoff._publish_telegram_post(None, telegram_post())

    assert accepted["status"] == "published"
    assert accepted["publish_outcome"] == "accepted"

    monkeypatch.setattr(social_post_service, "telegram_urlopen", lambda *_args, **_kwargs: ProviderResponse(json.dumps({"ok": True, "result": {}})))
    uncertain = recommendations_handoff._publish_telegram_post(None, telegram_post())

    assert uncertain["status"] == "published"
    assert uncertain["publish_outcome"] == "uncertain"


def test_telegram_publish_contract_holds_timeout_and_malformed_response(monkeypatch):
    monkeypatch.setattr(social_post_service, "_load_business_publish_context", lambda *_args: {"telegram_chat_id": "@synthetic"})
    monkeypatch.setattr(social_post_service, "_resolve_telegram_publish_transport", lambda *_args: {"bot_token": "synthetic", "token_source": "test"})
    monkeypatch.setattr(social_post_service, "_selected_media_assets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(social_post_service, "telegram_urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("synthetic timeout")))

    timeout = recommendations_handoff._publish_telegram_post(None, telegram_post())

    assert timeout["publish_outcome"] == "uncertain"

    monkeypatch.setattr(social_post_service, "telegram_urlopen", lambda *_args, **_kwargs: ProviderResponse("not json"))
    malformed = recommendations_handoff._publish_telegram_post(None, telegram_post())

    assert malformed["publish_outcome"] == "uncertain"


def test_telegram_media_keeps_first_receipt_when_caption_follow_up_fails(monkeypatch):
    monkeypatch.setattr(social_post_service, "_media_asset_file", lambda *_args: {"content": b"image", "mime_type": "image/jpeg", "filename": "image.jpg"})
    responses = [
        {"ok": True, "result": {"message_id": 21}},
        {"ok": False, "error": "synthetic caption failure", "publish_outcome": "uncertain"},
    ]
    monkeypatch.setattr(social_post_service, "_telegram_api_call", lambda *_args, **_kwargs: responses.pop(0))

    result = recommendations_handoff._publish_telegram_media_post(
        bot_token="synthetic",
        chat_id="@synthetic",
        text="x" * 1025,
        media_assets=[{"id": "asset-1"}],
        transport_source="test",
    )

    assert result["provider_post_id"] == "21"
    assert result["publish_outcome"] == "accepted"
    assert result["last_error"] == "synthetic caption failure"


def test_vk_publish_contract_marks_structured_rejection_and_missing_receipt(monkeypatch):
    account = {"id": "vk-account"}
    monkeypatch.setattr(social_post_service, "_find_active_external_account", lambda *_args: account)
    monkeypatch.setattr(social_post_service, "_external_account_auth_data", lambda *_args: {})
    monkeypatch.setattr(social_post_service, "_vk_auth_data_with_fresh_token", lambda *_args: {"api_version": "5.199"})
    monkeypatch.setattr(social_post_service, "_vk_publish_binding", lambda *_args: {"ready": True, "token": "synthetic", "owner_id": "-12"})
    monkeypatch.setattr(social_post_service, "_selected_media_assets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(social_post_service, "outbound_urlopen", lambda *_args, **_kwargs: ProviderResponse(json.dumps({"error": {"error_code": 15, "error_msg": "denied"}})))

    rejected = recommendations_handoff._publish_vk_post(None, {"business_id": "business-1", "platform_text": "Message"})

    assert rejected["publish_outcome"] == "rejected"

    monkeypatch.setattr(social_post_service, "outbound_urlopen", lambda *_args, **_kwargs: ProviderResponse(json.dumps({"response": {}})))
    uncertain = recommendations_handoff._publish_vk_post(None, {"business_id": "business-1", "platform_text": "Message"})

    assert uncertain["publish_outcome"] == "uncertain"


def test_google_publish_contract_holds_none_and_accepts_valid_receipt(monkeypatch):
    account = {"id": "google-account"}
    module = ModuleType("google_business_sync_worker")

    class Worker:
        def _publish_post(self, *_args):
            return None

    module.GoogleBusinessSyncWorker = Worker
    monkeypatch.setitem(sys.modules, "google_business_sync_worker", module)
    monkeypatch.setattr(social_post_service, "_find_active_external_account", lambda *_args: account)
    monkeypatch.setattr(social_post_service, "_selected_media_assets", lambda *_args, **_kwargs: [])

    uncertain = recommendations_handoff._publish_google_business_post(None, {"business_id": "business-1", "platform_text": "Message"})

    assert uncertain["publish_outcome"] == "uncertain"

    class ReceiptWorker:
        def _publish_post(self, *_args):
            return "google-post-1"

    module.GoogleBusinessSyncWorker = ReceiptWorker
    accepted = recommendations_handoff._publish_google_business_post(None, {"business_id": "business-1", "platform_text": "Message"})

    assert accepted["publish_outcome"] == "accepted"


def test_meta_publish_contract_preserves_provider_rejection_and_missing_receipt(monkeypatch):
    account = {"id": "meta-account", "external_id": "page-1"}
    monkeypatch.setattr(social_post_service, "_find_active_external_account", lambda *_args: account)
    monkeypatch.setattr(social_post_service, "_external_account_auth_data", lambda *_args: {"access_token": "synthetic", "page_id": "page-1"})
    monkeypatch.setattr(social_post_service, "_meta_publish_status", lambda *_args: "ready")
    monkeypatch.setattr(social_post_service, "_selected_media_assets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(social_post_service, "_meta_graph_post", lambda *_args, **_kwargs: {"success": False, "status_code": 403, "error": "denied", "publish_outcome": "rejected"})

    rejected = recommendations_handoff._publish_meta_post(None, {"business_id": "business-1", "platform": "facebook", "platform_text": "Message"})

    assert rejected["publish_outcome"] == "rejected"

    monkeypatch.setattr(social_post_service, "_meta_graph_post", lambda *_args, **_kwargs: {"success": True, "status_code": 200, "response": {}})
    uncertain = recommendations_handoff._publish_meta_post(None, {"business_id": "business-1", "platform": "facebook", "platform_text": "Message"})

    assert uncertain["publish_outcome"] == "uncertain"

    monkeypatch.setattr(social_post_service, "_meta_graph_post", lambda *_args, **_kwargs: {"success": True, "status_code": 200, "response": {"post_id": "meta-23"}})
    accepted = recommendations_handoff._publish_meta_post(None, {"business_id": "business-1", "platform": "facebook", "platform_text": "Message"})

    assert accepted["publish_outcome"] == "accepted"

    monkeypatch.setattr(social_post_service, "_meta_publish_status", lambda *_args: "missing_binding")
    preflight = recommendations_handoff._publish_meta_post(None, {"business_id": "business-1", "platform": "facebook", "platform_text": "Message"})

    assert preflight["publish_outcome"] == "not_attempted"


@pytest.mark.parametrize("status_code", [408, 409])
def test_telegram_and_vk_hold_http_retry_conflicts_without_republishing(monkeypatch, status_code):
    configure_telegram(monkeypatch, provider_http_error(status_code))

    telegram = recommendations_handoff._publish_telegram_post(None, telegram_post())

    assert telegram["publish_outcome"] == "uncertain"

    configure_vk(monkeypatch, provider_http_error(status_code))
    vk = recommendations_handoff._publish_vk_post(None, {"business_id": "business-1", "platform_text": "Message"})

    assert vk["publish_outcome"] == "uncertain"


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (lambda *_args, **_kwargs: ProviderResponse(json.dumps({"response": {"post_id": 23}})), "accepted"),
        (lambda *_args, **_kwargs: ProviderResponse(json.dumps({"response": {"post_id": 0}})), "uncertain"),
        (lambda *_args, **_kwargs: ProviderResponse(json.dumps({"error": {"error_code": 15, "error_msg": "denied"}})), "rejected"),
        (lambda *_args, **_kwargs: ProviderResponse("not json"), "uncertain"),
        (lambda *_args, **_kwargs: ProviderResponse("", read_error=OSError("synthetic read failure")), "uncertain"),
        (lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("synthetic timeout")), "uncertain"),
        (provider_http_error(503), "uncertain"),
    ],
)
def test_vk_facade_outcome_matrix(monkeypatch, response, expected):
    configure_vk(monkeypatch, response)

    result = recommendations_handoff._publish_vk_post(None, {"business_id": "business-1", "platform_text": "Message"})

    assert result["publish_outcome"] == expected


def test_vk_facade_preflight_is_not_attempted(monkeypatch):
    configure_vk(monkeypatch, lambda *_args, **_kwargs: ProviderResponse("{}"), ready=False)

    result = recommendations_handoff._publish_vk_post(None, {"business_id": "business-1", "platform_text": "Message"})

    assert result["publish_outcome"] == "not_attempted"


@pytest.mark.parametrize(
    ("response", "expected"),
    [
        (lambda *_args, **_kwargs: ProviderResponse(json.dumps({"id": "meta-23"})), "uncertain"),
        (lambda *_args, **_kwargs: ProviderResponse(json.dumps({"error": {"message": "denied", "code": 10}})), "rejected"),
        (lambda *_args, **_kwargs: ProviderResponse("not json"), "uncertain"),
        (lambda *_args, **_kwargs: ProviderResponse("", read_error=OSError("synthetic read failure")), "uncertain"),
        (lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("synthetic timeout")), "uncertain"),
        (provider_http_error(503), "uncertain"),
    ],
)
def test_meta_transport_outcome_matrix(monkeypatch, response, expected):
    monkeypatch.setattr(social_post_service, "outbound_urlopen", response)

    result = recommendations_handoff._meta_graph_post("page-1/feed", "synthetic", {"message": "Message"})

    assert result["publish_outcome"] == expected
