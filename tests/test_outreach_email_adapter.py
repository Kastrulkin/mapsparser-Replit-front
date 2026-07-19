from datetime import datetime, timezone
from email import policy

import pytest

from services.outreach_campaign_service import channel_availability
from services.outreach_email_adapter import (
    EMAIL_CREDENTIAL_PREFIX,
    EmailAdapterError,
    encrypt_mailbox_config,
    load_mailbox_config,
    normalize_mailbox_config,
    public_mail_host_addresses,
    send_email,
)
from services.outreach_email_reply_service import _match_queue_item


class _Cursor:
    def __init__(self, rows):
        self.rows = rows

    def execute(self, _query, _params):
        return None

    def fetchall(self):
        return self.rows


def test_mailbox_config_requires_smtp_imap_and_does_not_guess_credentials():
    config = normalize_mailbox_config({
        "email": " Founder@Пример.РФ ",
        "password": "secret",
        "smtp_host": "smtp.example.org",
        "imap_host": "imap.example.org",
    })

    assert config["email"] == "founder@xn--e1afmkfd.xn--p1ai"
    assert config["username"] == config["email"]
    assert config["smtp_security"] == "starttls"
    assert config["imap_security"] == "ssl"

    with pytest.raises(ValueError, match="mailbox_credentials_required"):
        normalize_mailbox_config({
            "email": "founder@example.org",
            "smtp_host": "smtp.example.org",
            "imap_host": "imap.example.org",
        })


def test_mailbox_credentials_use_dedicated_versioned_encryption(monkeypatch):
    monkeypatch.setenv("OUTREACH_EMAIL_SECRET_KEY", "a-secure-outreach-email-key-with-more-than-32-characters")
    config = normalize_mailbox_config({
        "email": "founder@example.org",
        "display_name": "Founder",
        "password": "secret-password",
        "smtp_host": "smtp.example.org",
        "imap_host": "imap.example.org",
    })

    encrypted = encrypt_mailbox_config(config)
    restored = load_mailbox_config({"auth_data_encrypted": encrypted})

    assert encrypted.startswith(EMAIL_CREDENTIAL_PREFIX)
    assert "secret-password" not in encrypted
    assert restored == config


def test_mailbox_encryption_requires_dedicated_secret(monkeypatch):
    monkeypatch.delenv("OUTREACH_EMAIL_SECRET_KEY", raising=False)
    config = normalize_mailbox_config({
        "email": "founder@example.org",
        "password": "secret-password",
        "smtp_host": "smtp.example.org",
        "imap_host": "imap.example.org",
    })

    with pytest.raises(EmailAdapterError) as raised:
        encrypt_mailbox_config(config)

    assert raised.value.code == "outreach_email_secret_missing"


def test_mail_host_guard_rejects_private_resolution(monkeypatch):
    monkeypatch.setattr(
        "services.outreach_email_adapter.socket.getaddrinfo",
        lambda *_args, **_kwargs: [(2, 1, 6, "", ("127.0.0.1", 465))],
    )

    with pytest.raises(EmailAdapterError) as raised:
        public_mail_host_addresses("smtp.example.org", 465)

    assert raised.value.code == "mail_host_not_public"


def test_native_email_send_uses_concrete_sender_and_message_id(monkeypatch):
    sent_messages = []

    class FakeSmtp:
        def send_message(self, message, **_kwargs):
            sent_messages.append(message)
            return {}

        def quit(self):
            return None

    monkeypatch.setattr(
        "services.outreach_email_adapter.load_mailbox_config",
        lambda _sender: {
            "email": "founder@example.org",
            "display_name": "Founder",
            "username": "founder@example.org",
            "password": "secret",
            "smtp_host": "smtp.example.org",
            "smtp_port": 465,
            "smtp_security": "ssl",
            "imap_host": "imap.example.org",
            "imap_port": 993,
            "imap_security": "ssl",
            "imap_folder": "INBOX",
        },
    )
    monkeypatch.setattr(
        "services.outreach_email_adapter._smtp_connection",
        lambda _config, timeout: FakeSmtp(),
    )

    result = send_email(
        {"id": "sender-1"},
        recipient="lead@example.net",
        subject="Короткий вопрос",
        body="Персональное сообщение",
        idempotency_key="outreach:touch-1",
    )

    assert result["provider_name"] == "native_email"
    assert result["provider_account_id"] == "sender-1"
    assert result["provider_message_id"].startswith("<")
    assert sent_messages[0]["X-LocalOS-Idempotency-Key"] == "outreach:touch-1"
    assert "secret" not in sent_messages[0].as_string(policy=policy.default)


def test_native_email_does_not_retry_when_transport_fails_after_send_started(monkeypatch):
    class AmbiguousSmtp:
        def send_message(self, _message, **_kwargs):
            raise TimeoutError("connection closed after DATA")

        def quit(self):
            return None

    monkeypatch.setattr(
        "services.outreach_email_adapter.load_mailbox_config",
        lambda _sender: {
            "email": "founder@example.org",
            "display_name": "Founder",
            "username": "founder@example.org",
            "password": "secret",
            "smtp_host": "smtp.example.org",
            "smtp_port": 465,
            "smtp_security": "ssl",
            "imap_host": "imap.example.org",
            "imap_port": 993,
            "imap_security": "ssl",
            "imap_folder": "INBOX",
        },
    )
    monkeypatch.setattr(
        "services.outreach_email_adapter._smtp_connection",
        lambda _config, timeout: AmbiguousSmtp(),
    )

    with pytest.raises(EmailAdapterError) as raised:
        send_email(
            {"id": "sender-1"},
            recipient="lead@example.net",
            subject="Короткий вопрос",
            body="Персональное сообщение",
            idempotency_key="outreach:touch-1",
        )

    assert raised.value.code == "email_send_uncertain"
    assert raised.value.retryable is False


def test_email_availability_requires_permission_direct_send_and_reply_sync():
    context = {
        "workstream_type": "client_partnership",
        "client_business_id": "business-1",
        "contacts": [{
            "id": "contact-1",
            "contact_type": "email",
            "value": "lead@example.net",
            "verification_status": "confirmed_source",
        }],
    }
    sender = {
        "id": "sender-1",
        "channel": "email",
        "status": "connected",
        "health_status": "healthy",
        "sender_outreach_enabled": True,
        "telegram_outreach_enabled": None,
        "capabilities_json": {"direct_send": True, "reply_sync": True},
    }

    ready = channel_availability(_Cursor([sender]), context)
    assert ready["email"]["status"] == "ready"

    sender["sender_outreach_enabled"] = False
    forbidden = channel_availability(_Cursor([sender]), context)
    assert forbidden["email"]["status"] == "permission_required"

    sender["sender_outreach_enabled"] = True
    sender["capabilities_json"]["reply_sync"] = False
    incomplete = channel_availability(_Cursor([sender]), context)
    assert incomplete["email"]["status"] == "adapter_unavailable"


def test_multiple_tenant_senders_require_explicit_selection():
    context = {
        "workstream_type": "client_partnership",
        "client_business_id": "business-1",
        "contacts": [{
            "id": "contact-1",
            "contact_type": "email",
            "value": "lead@example.net",
            "verification_status": "confirmed_source",
        }],
    }
    senders = [
        {
            "id": "sender-1",
            "channel": "email",
            "status": "connected",
            "health_status": "healthy",
            "sender_identity": "first@example.org",
            "sender_outreach_enabled": True,
            "capabilities_json": {"direct_send": True, "reply_sync": True},
        },
        {
            "id": "sender-2",
            "channel": "email",
            "status": "connected",
            "health_status": "healthy",
            "sender_identity": "second@example.org",
            "sender_outreach_enabled": True,
            "capabilities_json": {"direct_send": True, "reply_sync": True},
        },
    ]

    availability = channel_availability(_Cursor(senders), context)

    assert availability["email"]["status"] == "sender_selection_required"
    assert availability["email"]["sender_account_id"] is None
    assert [item["id"] for item in availability["email"]["sender_accounts"]] == ["sender-1", "sender-2"]


def test_reply_matching_prefers_message_thread_then_recipient_fallback():
    sent_at = datetime(2026, 7, 17, 10, 0, tzinfo=timezone.utc)
    candidates = [{
        "id": "queue-1",
        "provider_message_id": "<outgoing@example.org>",
        "recipient_value": "lead@example.net",
        "sent_at": sent_at,
    }]

    threaded = _match_queue_item({
        "in_reply_to": "<outgoing@example.org>",
        "references": "",
        "body": "Да, интересно",
        "from_email": "other@example.net",
        "occurred_at": sent_at,
    }, candidates)
    fallback = _match_queue_item({
        "in_reply_to": "",
        "references": "",
        "body": "Да, интересно",
        "from_email": "lead@example.net",
        "occurred_at": sent_at,
    }, candidates)

    assert threaded["id"] == "queue-1"
    assert fallback["id"] == "queue-1"


def test_email_runtime_has_no_global_smtp_or_openclaw_fallback():
    source = open("src/api/prospecting/audit_generation.py", encoding="utf-8").read()
    function_start = source.index("def _dispatch_outreach_queue_item")
    function_end = source.index("\n@admin_prospecting_bp.route", function_start)
    dispatch = source[function_start:function_end]

    assert "_dispatch_via_email_sender(item, message)" in dispatch
    assert 'if channel in {"whatsapp", "email"}' not in dispatch
    assert 'if channel == "whatsapp"' in dispatch


def test_worker_syncs_telegram_and_email_before_dispatch():
    source = open("src/worker.py", encoding="utf-8").read()
    function_start = source.index("def _dispatch_outreach_queue_if_due()")
    function_end = source.index("\ndef _run_card_automation_if_due()", function_start)
    worker_block = source[function_start:function_end]

    assert worker_block.index("_sync_telegram_app_replies") < worker_block.index("dispatch_due_outreach_queue")
    assert worker_block.index("sync_email_replies") < worker_block.index("dispatch_due_outreach_queue")
    assert "OUTREACH_REPLY_SYNC_FAIL_CLOSED" in worker_block
