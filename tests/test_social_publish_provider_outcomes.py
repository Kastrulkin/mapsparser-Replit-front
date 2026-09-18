import hashlib
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
        "publish_mode": "api",
        "approval_id": "approval-telegram",
        "platform_text": "Synthetic message",
    }


def approved_snapshot(post, binding):
    from services.social_posts import approval_binding

    payload = {
        "schema": approval_binding.SNAPSHOT_SCHEMA,
        "approval_id": post["approval_id"],
        "business_id": post["business_id"],
        "platform": post["platform"],
        "publish_mode": post["publish_mode"],
        "text_sha256": hashlib.sha256(post["platform_text"].encode("utf-8")).hexdigest(),
        "binding": binding,
        "media": [],
    }
    payload["hash"] = approval_binding._canonical_hash(payload)
    return payload


def telegram_snapshot(post):
    return approved_snapshot(
        post,
        {
            "provider": "telegram",
            "recipient": {"chat_id": "@synthetic"},
            "sender": {"transport_source": "test", "bot_numeric_id": "123"},
        },
    )


def configure_telegram(monkeypatch, response):
    monkeypatch.setattr(social_post_service, "_load_business_publish_context", lambda *_args: {"telegram_chat_id": "@synthetic"})
    monkeypatch.setattr(social_post_service, "_resolve_telegram_publish_transport", lambda *_args: {"bot_token": "123:synthetic", "token_source": "test"})
    monkeypatch.setattr(social_post_service, "_selected_media_assets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(social_post_service, "telegram_urlopen", response)


def configure_vk(monkeypatch, response, ready=True):
    account = {"id": "vk-account", "source": "vk", "external_id": "42"}
    binding = {"provider": "vk", "account": {"id": "vk-account", "source": "vk", "external_id": "42"}, "recipient": {"id": "-12"}}
    monkeypatch.setattr(social_post_service, "frozen_external_account", lambda *_args: (account, binding))
    monkeypatch.setattr(social_post_service, "_external_account_auth_data", lambda *_args: {})
    monkeypatch.setattr(social_post_service, "_vk_auth_data_with_fresh_token", lambda *_args: {"api_version": "5.199"})
    monkeypatch.setattr(social_post_service, "vk_publish_binding", lambda *_args: {"ready": ready, "token": "synthetic", "owner_id": "-12"})
    monkeypatch.setattr(social_post_service, "outbound_urlopen", response)


def vk_post():
    return {"business_id": "business-1", "platform": "vk", "publish_mode": "api", "approval_id": "approval-vk", "platform_text": "Message"}


def vk_snapshot(post):
    return approved_snapshot(post, {"provider": "vk", "account": {"id": "vk-account", "source": "vk", "external_id": "42"}, "recipient": {"id": "-12"}})


def external_post(platform, approval_id):
    return {"business_id": "business-1", "platform": platform, "publish_mode": "api", "approval_id": approval_id, "platform_text": "Message"}


def external_snapshot(post, account_id, source, external_id, recipient):
    return approved_snapshot(post, {"provider": post["platform"], "account": {"id": account_id, "source": source, "external_id": external_id}, "recipient": {"id": recipient}})


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
    monkeypatch.setattr(social_post_service, "_resolve_telegram_publish_transport", lambda *_args: {"bot_token": "123:synthetic", "token_source": "test"})
    monkeypatch.setattr(social_post_service, "_selected_media_assets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(social_post_service, "telegram_urlopen", lambda *_args, **_kwargs: ProviderResponse(json.dumps({"ok": True, "result": {"message_id": 17}})))

    post = telegram_post()
    accepted = recommendations_handoff._publish_telegram_post(None, post, telegram_snapshot(post))

    assert accepted["status"] == "published"
    assert accepted["publish_outcome"] == "accepted"

    monkeypatch.setattr(social_post_service, "telegram_urlopen", lambda *_args, **_kwargs: ProviderResponse(json.dumps({"ok": True, "result": {}})))
    uncertain = recommendations_handoff._publish_telegram_post(None, post, telegram_snapshot(post))

    assert uncertain["status"] == "published"
    assert uncertain["publish_outcome"] == "uncertain"


def test_direct_telegram_adapter_rejects_missing_approval_binding(monkeypatch):
    configure_telegram(monkeypatch, lambda *_args, **_kwargs: ProviderResponse("{}"))

    result = recommendations_handoff._publish_telegram_post(None, telegram_post())

    assert result["status"] == "needs_review"
    assert result["publish_outcome"] == "not_attempted"


def test_telegram_publish_contract_holds_timeout_and_malformed_response(monkeypatch):
    monkeypatch.setattr(social_post_service, "_load_business_publish_context", lambda *_args: {"telegram_chat_id": "@synthetic"})
    monkeypatch.setattr(social_post_service, "_resolve_telegram_publish_transport", lambda *_args: {"bot_token": "123:synthetic", "token_source": "test"})
    monkeypatch.setattr(social_post_service, "_selected_media_assets", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(social_post_service, "telegram_urlopen", lambda *_args, **_kwargs: (_ for _ in ()).throw(URLError("synthetic timeout")))

    post = telegram_post()
    timeout = recommendations_handoff._publish_telegram_post(None, post, telegram_snapshot(post))

    assert timeout["publish_outcome"] == "uncertain"

    monkeypatch.setattr(social_post_service, "telegram_urlopen", lambda *_args, **_kwargs: ProviderResponse("not json"))
    malformed = recommendations_handoff._publish_telegram_post(None, post, telegram_snapshot(post))

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
    configure_vk(monkeypatch, lambda *_args, **_kwargs: ProviderResponse(json.dumps({"error": {"error_code": 15, "error_msg": "denied"}})))

    post = vk_post()
    rejected = recommendations_handoff._publish_vk_post(None, post, vk_snapshot(post))

    assert rejected["publish_outcome"] == "rejected"

    monkeypatch.setattr(social_post_service, "outbound_urlopen", lambda *_args, **_kwargs: ProviderResponse(json.dumps({"response": {}})))
    uncertain = recommendations_handoff._publish_vk_post(None, post, vk_snapshot(post))

    assert uncertain["publish_outcome"] == "uncertain"


def test_google_publish_contract_holds_none_and_accepts_valid_receipt(monkeypatch):
    account = {"id": "google-account", "source": "google_business", "external_id": "locations/approved"}
    module = ModuleType("google_business_sync_worker")

    class Worker:
        def _publish_post(self, *_args):
            return None

    module.GoogleBusinessSyncWorker = Worker
    monkeypatch.setitem(sys.modules, "google_business_sync_worker", module)
    binding = {"provider": "google_business", "account": {"id": "google-account", "source": "google_business", "external_id": "locations/approved"}, "recipient": {"id": "locations/approved"}}
    monkeypatch.setattr(social_post_service, "frozen_external_account", lambda *_args: (account, binding))
    post = external_post("google_business", "approval-google")
    snapshot = external_snapshot(post, "google-account", "google_business", "locations/approved", "locations/approved")

    uncertain = recommendations_handoff._publish_google_business_post(None, post, snapshot)

    assert uncertain["publish_outcome"] == "uncertain"

    class ReceiptWorker:
        def _publish_post(self, *_args):
            return "google-post-1"

    module.GoogleBusinessSyncWorker = ReceiptWorker
    accepted = recommendations_handoff._publish_google_business_post(None, post, snapshot)

    assert accepted["publish_outcome"] == "accepted"


def test_meta_publish_contract_preserves_provider_rejection_and_missing_receipt(monkeypatch):
    account = {"id": "meta-account", "source": "meta", "external_id": "page-1"}
    binding = {"provider": "facebook", "account": {"id": "meta-account", "source": "meta", "external_id": "page-1"}, "recipient": {"id": "page-1"}}
    monkeypatch.setattr(social_post_service, "frozen_external_account", lambda *_args: (account, binding))
    monkeypatch.setattr(social_post_service, "_external_account_auth_data", lambda *_args: {"access_token": "synthetic", "page_id": "page-1"})
    monkeypatch.setattr(social_post_service, "meta_publish_status", lambda *_args: "ready")
    monkeypatch.setattr(social_post_service, "_meta_graph_post", lambda *_args, **_kwargs: {"success": False, "status_code": 403, "error": "denied", "publish_outcome": "rejected"})

    post = external_post("facebook", "approval-facebook")
    snapshot = external_snapshot(post, "meta-account", "meta", "page-1", "page-1")
    rejected = recommendations_handoff._publish_meta_post(None, post, snapshot)

    assert rejected["publish_outcome"] == "rejected"

    monkeypatch.setattr(social_post_service, "_meta_graph_post", lambda *_args, **_kwargs: {"success": True, "status_code": 200, "response": {}})
    uncertain = recommendations_handoff._publish_meta_post(None, post, snapshot)

    assert uncertain["publish_outcome"] == "uncertain"

    monkeypatch.setattr(social_post_service, "_meta_graph_post", lambda *_args, **_kwargs: {"success": True, "status_code": 200, "response": {"post_id": "meta-23"}})
    accepted = recommendations_handoff._publish_meta_post(None, post, snapshot)

    assert accepted["publish_outcome"] == "accepted"

    monkeypatch.setattr(social_post_service, "meta_publish_status", lambda *_args: "missing_binding")
    preflight = recommendations_handoff._publish_meta_post(None, post, snapshot)

    assert preflight["publish_outcome"] == "not_attempted"


@pytest.mark.parametrize(
    ("platform", "account_id", "source", "external_id", "recipient"),
    (
        ("vk", "vk-account", "vk", "42", "-12"),
        ("google_business", "google-account", "google_business", "locations/approved", "locations/approved"),
        ("facebook", "meta-account", "meta", "page-approved", "page-approved"),
        ("instagram", "meta-account", "meta", "page-approved", "ig-approved"),
    ),
)
def test_external_adapter_account_drift_stops_before_provider_transport(monkeypatch, platform, account_id, source, external_id, recipient):
    post = external_post(platform, f"approval-{platform}")
    snapshot = external_snapshot(post, account_id, source, external_id, recipient)
    transport_calls = []
    monkeypatch.setattr(social_post_service, "frozen_external_account", lambda *_args: ({}, {}))
    monkeypatch.setattr(social_post_service, "outbound_urlopen", lambda *_args, **_kwargs: transport_calls.append("called"))

    if platform == "vk":
        result = recommendations_handoff._publish_vk_post(None, post, snapshot)
    elif platform == "google_business":
        result = recommendations_handoff._publish_google_business_post(None, post, snapshot)
    else:
        result = recommendations_handoff._publish_meta_post(None, post, snapshot)

    assert transport_calls == []
    assert result["status"] == "needs_review"
    assert result["publish_outcome"] == "not_attempted"


@pytest.mark.parametrize("status_code", [408, 409])
def test_telegram_and_vk_hold_http_retry_conflicts_without_republishing(monkeypatch, status_code):
    configure_telegram(monkeypatch, provider_http_error(status_code))

    post = telegram_post()
    telegram = recommendations_handoff._publish_telegram_post(None, post, telegram_snapshot(post))

    assert telegram["publish_outcome"] == "uncertain"

    configure_vk(monkeypatch, provider_http_error(status_code))
    post = vk_post()
    vk = recommendations_handoff._publish_vk_post(None, post, vk_snapshot(post))

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

    post = vk_post()
    result = recommendations_handoff._publish_vk_post(None, post, vk_snapshot(post))

    assert result["publish_outcome"] == expected


def test_vk_facade_preflight_is_not_attempted(monkeypatch):
    configure_vk(monkeypatch, lambda *_args, **_kwargs: ProviderResponse("{}"), ready=False)

    post = vk_post()
    result = recommendations_handoff._publish_vk_post(None, post, vk_snapshot(post))

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
