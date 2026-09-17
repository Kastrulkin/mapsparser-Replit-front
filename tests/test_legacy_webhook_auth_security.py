"""Security regression coverage for legacy AI agent webhook ingress.

These tests intentionally describe the deny-by-default contract.  They are
expected to fail until each provider request is authenticated before its
payload is parsed or any business/AI/provider dependency is invoked.
"""
import hashlib
import hmac
import json
import sys

import requests

from flask import Flask


if "src" not in sys.path:
    sys.path.insert(0, "src")


import ai_agent_webhooks
from core.telegram_webhook_auth import derive_telegram_webhook_secret


class _Connection:
    def __init__(self) -> None:
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return object()

    def commit(self) -> None:
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True


class _Database:
    def __init__(self) -> None:
        self.conn = _Connection()
        self.closed = False

    def close(self) -> None:
        self.closed = True


class _TelegramCursor:
    def __init__(self, row: dict | None) -> None:
        self.row = row
        self.executed: list[tuple[str, object]] = []

    def execute(self, query: str, params=None) -> None:
        self.executed.append((query, params))

    def fetchone(self):
        return self.row


class _TelegramDatabase:
    def __init__(self, row: dict | None) -> None:
        self.cursor_instance = _TelegramCursor(row)
        self.conn = _Connection()
        self.conn.cursor = lambda: self.cursor_instance
        self.closed = False

    def close(self) -> None:
        self.closed = True


def _client():
    app = Flask(__name__)
    app.register_blueprint(ai_agent_webhooks.ai_webhooks_bp)
    return app.test_client()


def _whatsapp_message() -> dict:
    return {
        "entry": [
            {
                "id": "waba-account-1",
                "changes": [
                    {
                        "value": {
                            "metadata": {"phone_number_id": "phone-id-1"},
                            "messages": [
                                {
                                    "from": "79990001122",
                                    "id": "wamid.test-1",
                                    "text": {"body": "Нужна запись"},
                                }
                            ],
                        }
                    }
                ],
            }
        ]
    }


def _whatsapp_payload_bytes(payload: object) -> bytes:
    return json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")


def _whatsapp_signature(secret: str, raw_body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), raw_body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _install_whatsapp_side_effect_spies(monkeypatch):
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        ai_agent_webhooks,
        "find_business_by_waba_phone_id",
        lambda phone_id: {
            "id": "business-1",
            "waba_phone_id": phone_id,
            "waba_access_token": "test-access-token",
            "ai_agent_enabled": True,
        },
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "process_message",
        lambda **kwargs: calls.append(("ai", kwargs)) or {"success": True, "response": "Ответ"},
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "send_whatsapp_message",
        lambda **kwargs: calls.append(("send", kwargs)) or True,
    )
    return calls


def _telegram_update() -> dict:
    return {
        "update_id": 10001,
        "message": {
            "message_id": 77,
            "chat": {"id": 99001},
            "from": {"id": 88001, "first_name": "Attacker", "username": "attacker"},
            "text": "Запусти обработку",
        },
    }


def test_unsigned_whatsapp_post_cannot_reach_ai_or_provider_send(monkeypatch) -> None:
    """Meta POSTs require a valid app-secret HMAC before payload handling."""
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "test-app-secret")
    calls = _install_whatsapp_side_effect_spies(monkeypatch)

    response = _client().post("/api/webhooks/whatsapp", json=_whatsapp_message())

    assert response.status_code in {401, 403} and not calls, (
        f"unsigned WhatsApp POST reached protected dependencies: {calls}"
    )


def test_whatsapp_post_rejects_a_signature_for_different_raw_body(monkeypatch) -> None:
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "test-app-secret")
    calls = _install_whatsapp_side_effect_spies(monkeypatch)
    signed_body = _whatsapp_payload_bytes(_whatsapp_message())
    changed_payload = _whatsapp_message()
    changed_payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"] = "Подменено"

    response = _client().post(
        "/api/webhooks/whatsapp",
        data=_whatsapp_payload_bytes(changed_payload),
        content_type="application/json",
        headers={"X-Hub-Signature-256": _whatsapp_signature("test-app-secret", signed_body)},
    )

    assert response.status_code == 403
    assert calls == []


def test_whatsapp_post_rejects_a_malformed_signature_header(monkeypatch) -> None:
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "test-app-secret")
    calls = _install_whatsapp_side_effect_spies(monkeypatch)
    raw_body = _whatsapp_payload_bytes(_whatsapp_message())

    response = _client().post(
        "/api/webhooks/whatsapp",
        data=raw_body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": "sha256=not-a-sha256-digest"},
    )

    assert response.status_code == 403
    assert calls == []


def test_whatsapp_post_fails_closed_when_app_secret_is_missing(monkeypatch) -> None:
    monkeypatch.delenv("WHATSAPP_APP_SECRET", raising=False)
    calls = _install_whatsapp_side_effect_spies(monkeypatch)

    response = _client().post("/api/webhooks/whatsapp", json=_whatsapp_message())

    assert response.status_code == 503
    assert calls == []


def test_whatsapp_post_rejects_malformed_signed_json_without_side_effects(monkeypatch) -> None:
    secret = "test-app-secret"
    monkeypatch.setenv("WHATSAPP_APP_SECRET", secret)
    calls = _install_whatsapp_side_effect_spies(monkeypatch)
    raw_body = b'{"entry":'

    response = _client().post(
        "/api/webhooks/whatsapp",
        data=raw_body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": _whatsapp_signature(secret, raw_body)},
    )

    assert response.status_code == 400
    assert calls == []


def test_whatsapp_post_rejects_signed_invalid_payload_shape_without_side_effects(monkeypatch) -> None:
    secret = "test-app-secret"
    monkeypatch.setenv("WHATSAPP_APP_SECRET", secret)
    calls = _install_whatsapp_side_effect_spies(monkeypatch)
    raw_body = _whatsapp_payload_bytes({"entry": {"not": "a list"}})

    response = _client().post(
        "/api/webhooks/whatsapp",
        data=raw_body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": _whatsapp_signature(secret, raw_body)},
    )

    assert response.status_code == 400
    assert calls == []


def test_valid_signed_whatsapp_post_reaches_expected_side_effects(monkeypatch, capsys, caplog) -> None:
    caplog.set_level("INFO", logger=ai_agent_webhooks.__name__)
    secret = "test-app-secret"
    monkeypatch.setenv("WHATSAPP_APP_SECRET", secret)
    calls = _install_whatsapp_side_effect_spies(monkeypatch)
    raw_body = _whatsapp_payload_bytes(_whatsapp_message())

    response = _client().post(
        "/api/webhooks/whatsapp",
        data=raw_body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": _whatsapp_signature(secret, raw_body)},
    )

    assert response.status_code == 200
    assert [name for name, _payload in calls] == ["ai", "send"]
    captured = capsys.readouterr()
    output = captured.out + captured.err + caplog.text
    assert "79990001122" not in output
    assert "Нужна запись" not in output
    assert "Ответ" not in output
    assert "whatsapp_message_received" in caplog.text


def test_whatsapp_outer_failures_keep_json_error_and_logs_secret_free(monkeypatch, capsys, caplog) -> None:
    caplog.set_level("INFO", logger=ai_agent_webhooks.__name__)
    secret = "https://graph.facebook.com/v20.0/phone-id/messages?access_token=synthetic-secret"
    raw_body = _whatsapp_payload_bytes(_whatsapp_message())
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "test-app-secret")
    monkeypatch.setattr(
        ai_agent_webhooks,
        "find_business_by_waba_phone_id",
        lambda *_args: (_ for _ in ()).throw(RuntimeError(secret)),
    )

    response = _client().post(
        "/api/webhooks/whatsapp",
        data=raw_body,
        content_type="application/json",
        headers={"X-Hub-Signature-256": _whatsapp_signature("test-app-secret", raw_body)},
    )

    output = capsys.readouterr()
    assert response.status_code == 500
    assert response.get_json() == {"error": "Webhook processing failed"}
    assert "synthetic-secret" not in output.out + output.err + caplog.text
    assert "whatsapp_webhook_failed error_type=RuntimeError" in caplog.text


def test_whatsapp_verification_never_accepts_the_public_fallback_token(monkeypatch) -> None:
    """A missing deployment secret must fail closed instead of accepting a known default."""
    monkeypatch.delenv("WHATSAPP_VERIFY_TOKEN", raising=False)

    response = _client().get(
        "/api/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=local_verify_token&hub.challenge=attack",
    )

    assert response.status_code == 403


def test_whatsapp_verification_accepts_the_configured_challenge(monkeypatch) -> None:
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-secret")

    response = _client().get(
        "/api/webhooks/whatsapp?hub.mode=subscribe&hub.verify_token=verify-secret&hub.challenge=challenge-ok",
    )

    assert response.status_code == 200
    assert response.data == b"challenge-ok"


def test_whatsapp_non_ascii_signature_is_denied_without_server_error(monkeypatch):
    monkeypatch.setenv("WHATSAPP_APP_SECRET", "test-app-secret")
    calls = _install_whatsapp_side_effect_spies(monkeypatch)
    response = _client().post(
        "/api/webhooks/whatsapp",
        json=_whatsapp_message(),
        headers={"X-Hub-Signature-256": "sha256=é"},
    )
    assert response.status_code == 403
    assert calls == []


def test_whatsapp_non_ascii_verify_token_is_denied_without_server_error(monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-secret")
    response = _client().get(
        "/api/webhooks/whatsapp",
        query_string={"hub.mode": "subscribe", "hub.verify_token": "é", "hub.challenge": "ok"},
    )
    assert response.status_code == 403


def test_whatsapp_verification_requires_a_challenge(monkeypatch):
    monkeypatch.setenv("WHATSAPP_VERIFY_TOKEN", "verify-secret")
    response = _client().get(
        "/api/webhooks/whatsapp",
        query_string={"hub.mode": "subscribe", "hub.verify_token": "verify-secret"},
    )
    assert response.status_code == 400


BUSINESS_A = "11111111-1111-4111-8111-111111111111"
BUSINESS_B = "22222222-2222-4222-8222-222222222222"
BOT_TOKEN_A = "100001:telegram-business-a-token"
BOT_TOKEN_B = "100002:telegram-business-b-token"


def _telegram_headers(business_id: str, bot_token: str) -> dict[str, str]:
    return {"X-Telegram-Bot-Api-Secret-Token": derive_telegram_webhook_secret(bot_token, business_id)}


def _telegram_url(business_id: str) -> str:
    return f"/api/webhooks/telegram?business_id={business_id}"


def test_unsigned_telegram_update_cannot_dispatch_or_send(monkeypatch) -> None:
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(
        ai_agent_webhooks,
        "DatabaseManager",
        lambda: (_ for _ in ()).throw(AssertionError("unauthenticated request queried the database")),
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "dispatch_telegram_message_to_agent_blueprints",
        lambda *_args, **_kwargs: calls.append(("dispatch", _args)),
    )

    response = _client().post("/api/webhooks/telegram", json=_telegram_update())

    assert response.status_code == 403
    assert calls == []


def test_telegram_rejects_foreign_business_secret_before_side_effects(monkeypatch) -> None:
    database = _TelegramDatabase({"id": BUSINESS_B, "telegram_bot_token": BOT_TOKEN_B})
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(ai_agent_webhooks, "DatabaseManager", lambda: database)
    monkeypatch.setattr(ai_agent_webhooks, "process_message", lambda **kwargs: calls.append(("ai", kwargs)))

    response = _client().post(
        _telegram_url(BUSINESS_B),
        json=_telegram_update(),
        headers=_telegram_headers(BUSINESS_A, BOT_TOKEN_A),
    )

    assert response.status_code == 403
    assert calls == []
    assert database.closed is True
    assert len(database.cursor_instance.executed) == 1


def test_telegram_rejects_legacy_query_token_before_database_lookup(monkeypatch) -> None:
    monkeypatch.setattr(
        ai_agent_webhooks,
        "DatabaseManager",
        lambda: (_ for _ in ()).throw(AssertionError("legacy query token reached the database")),
    )

    response = _client().post(
        f"{_telegram_url(BUSINESS_A)}&bot_token={BOT_TOKEN_A}",
        json=_telegram_update(),
        headers=_telegram_headers(BUSINESS_A, BOT_TOKEN_A),
    )

    assert response.status_code == 403


def test_telegram_rejects_legacy_token_header_before_database_lookup(monkeypatch) -> None:
    monkeypatch.setattr(
        ai_agent_webhooks,
        "DatabaseManager",
        lambda: (_ for _ in ()).throw(AssertionError("legacy token header reached the database")),
    )
    headers = _telegram_headers(BUSINESS_A, BOT_TOKEN_A)
    headers["X-Bot-Token"] = BOT_TOKEN_A

    response = _client().post(_telegram_url(BUSINESS_A), json=_telegram_update(), headers=headers)

    assert response.status_code == 403


def test_telegram_rejects_malformed_secret_header_before_database_lookup(monkeypatch) -> None:
    monkeypatch.setattr(
        ai_agent_webhooks,
        "DatabaseManager",
        lambda: (_ for _ in ()).throw(AssertionError("malformed secret reached the database")),
    )

    response = _client().post(
        _telegram_url(BUSINESS_A),
        json=_telegram_update(),
        headers={"X-Telegram-Bot-Api-Secret-Token": "g" * 64},
    )

    assert response.status_code == 403


def test_telegram_rejects_body_token_after_auth_without_side_effects(monkeypatch) -> None:
    database = _TelegramDatabase({"id": BUSINESS_A, "telegram_bot_token": BOT_TOKEN_A})
    calls: list[tuple[str, object]] = []
    payload = _telegram_update()
    payload["bot_token"] = BOT_TOKEN_A
    monkeypatch.setattr(ai_agent_webhooks, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        ai_agent_webhooks,
        "dispatch_telegram_message_to_agent_blueprints",
        lambda *_args, **_kwargs: calls.append(("dispatch", _args)),
    )

    response = _client().post(
        _telegram_url(BUSINESS_A), json=payload, headers=_telegram_headers(BUSINESS_A, BOT_TOKEN_A)
    )

    assert response.status_code == 400
    assert calls == []
    assert database.closed is True


def test_valid_telegram_callback_dispatches_and_uses_stored_bot_token(monkeypatch) -> None:
    database = _TelegramDatabase({"id": BUSINESS_A, "telegram_bot_token": BOT_TOKEN_A})
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(ai_agent_webhooks, "DatabaseManager", lambda: database)
    monkeypatch.setattr(ai_agent_webhooks, "business_agent_enabled_for_channel", lambda *_args: {"enabled": True})
    monkeypatch.setattr(
        ai_agent_webhooks,
        "dispatch_telegram_message_to_agent_blueprints",
        lambda *_args, **_kwargs: calls.append(("dispatch", _args)) or {"matched_count": 0},
    )
    monkeypatch.setattr(
        ai_agent_webhooks,
        "process_message",
        lambda **kwargs: calls.append(("ai", kwargs)) or {"success": True, "response": "Ответ"},
    )
    monkeypatch.setattr(ai_agent_webhooks, "send_telegram_message", lambda **kwargs: calls.append(("send", kwargs)) or True)

    response = _client().post(
        _telegram_url(BUSINESS_A), json=_telegram_update(), headers=_telegram_headers(BUSINESS_A, BOT_TOKEN_A)
    )

    assert response.status_code == 200
    assert [name for name, _payload in calls] == ["dispatch", "ai", "send"]
    assert calls[-1][1]["bot_token"] == BOT_TOKEN_A
    assert database.conn.committed is True
    assert database.closed is True


def test_duplicate_telegram_agent_event_does_not_reach_legacy_reply(monkeypatch) -> None:
    database = _TelegramDatabase({"id": BUSINESS_A, "telegram_bot_token": BOT_TOKEN_A})
    calls: list[str] = []
    monkeypatch.setattr(ai_agent_webhooks, "DatabaseManager", lambda: database)
    monkeypatch.setattr(ai_agent_webhooks, "business_agent_enabled_for_channel", lambda *_args: {"enabled": True})
    monkeypatch.setattr(
        ai_agent_webhooks,
        "dispatch_telegram_message_to_agent_blueprints",
        lambda *_args, **_kwargs: {"duplicate": True, "matched_count": 0, "legacy_reply_should_continue": False},
    )
    monkeypatch.setattr(ai_agent_webhooks, "process_message", lambda **_kwargs: calls.append("process"))
    monkeypatch.setattr(ai_agent_webhooks, "send_telegram_message", lambda **_kwargs: calls.append("send"))

    response = _client().post(
        _telegram_url(BUSINESS_A), json=_telegram_update(), headers=_telegram_headers(BUSINESS_A, BOT_TOKEN_A)
    )

    assert response.status_code == 200
    assert calls == []


def test_webhook_transport_failures_do_not_log_provider_secrets(monkeypatch, capsys, caplog) -> None:
    caplog.set_level("INFO", logger=ai_agent_webhooks.__name__)
    sensitive = "https://api.telegram.org/bot111:synthetic-token/sendMessage?phone=79990001122&body=private-body"
    monkeypatch.setattr(ai_agent_webhooks.requests, "post", lambda *_args, **_kwargs: (_ for _ in ()).throw(requests.HTTPError(sensitive)))

    assert ai_agent_webhooks.send_telegram_message("111:synthetic-token", "79990001122", "private-body") is False
    assert ai_agent_webhooks.send_whatsapp_message("phone-id", "wa-access-token", "79990001122", "private-body") is False

    output = capsys.readouterr()
    for value in ("111:synthetic-token", "79990001122", "private-body", "wa-access-token"):
        assert value not in output.out + output.err + caplog.text
    assert "telegram_message_send_failed error_type=HTTPError" in caplog.text
    assert "whatsapp_message_send_failed error_type=HTTPError" in caplog.text


def test_webhook_outer_failures_keep_json_error_and_logs_secret_free(monkeypatch, capsys, caplog) -> None:
    caplog.set_level("INFO", logger=ai_agent_webhooks.__name__)
    secret = "https://api.telegram.org/bot111:synthetic-token/sendMessage"
    database = _TelegramDatabase({"id": BUSINESS_A, "telegram_bot_token": BOT_TOKEN_A})
    monkeypatch.setattr(ai_agent_webhooks, "DatabaseManager", lambda: database)
    monkeypatch.setattr(ai_agent_webhooks, "business_agent_enabled_for_channel", lambda *_args: {"enabled": True})
    monkeypatch.setattr(
        ai_agent_webhooks,
        "dispatch_telegram_message_to_agent_blueprints",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError(secret)),
    )

    response = _client().post(
        _telegram_url(BUSINESS_A), json=_telegram_update(), headers=_telegram_headers(BUSINESS_A, BOT_TOKEN_A)
    )

    output = capsys.readouterr()
    assert response.status_code == 500
    assert response.get_json() == {"error": "Webhook processing failed"}
    assert "111:synthetic-token" not in output.out + output.err + caplog.text
    assert "telegram_webhook_failed error_type=RuntimeError" in caplog.text


def test_telegram_disabled_business_does_not_dispatch_or_send(monkeypatch) -> None:
    database = _TelegramDatabase({"id": BUSINESS_A, "telegram_bot_token": BOT_TOKEN_A})
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(ai_agent_webhooks, "DatabaseManager", lambda: database)
    monkeypatch.setattr(ai_agent_webhooks, "business_agent_enabled_for_channel", lambda *_args: {"enabled": False})
    monkeypatch.setattr(
        ai_agent_webhooks,
        "dispatch_telegram_message_to_agent_blueprints",
        lambda *_args, **_kwargs: calls.append(("dispatch", _args)),
    )

    response = _client().post(
        _telegram_url(BUSINESS_A), json=_telegram_update(), headers=_telegram_headers(BUSINESS_A, BOT_TOKEN_A)
    )

    assert response.status_code == 200
    assert calls == []
    assert database.closed is True


def test_telegram_authenticated_malformed_json_does_not_dispatch(monkeypatch) -> None:
    database = _TelegramDatabase({"id": BUSINESS_A, "telegram_bot_token": BOT_TOKEN_A})
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(ai_agent_webhooks, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        ai_agent_webhooks,
        "dispatch_telegram_message_to_agent_blueprints",
        lambda *_args, **_kwargs: calls.append(("dispatch", _args)),
    )

    response = _client().post(
        _telegram_url(BUSINESS_A),
        data=b'{"message":',
        content_type="application/json",
        headers=_telegram_headers(BUSINESS_A, BOT_TOKEN_A),
    )

    assert response.status_code == 400
    assert calls == []
    assert database.closed is True


def test_telegram_authenticated_invalid_message_shape_does_not_dispatch(monkeypatch) -> None:
    database = _TelegramDatabase({"id": BUSINESS_A, "telegram_bot_token": BOT_TOKEN_A})
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(ai_agent_webhooks, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        ai_agent_webhooks,
        "dispatch_telegram_message_to_agent_blueprints",
        lambda *_args, **_kwargs: calls.append(("dispatch", _args)),
    )

    response = _client().post(
        _telegram_url(BUSINESS_A),
        json={"message": []},
        headers=_telegram_headers(BUSINESS_A, BOT_TOKEN_A),
    )

    assert response.status_code == 400
    assert calls == []
    assert database.closed is True


def test_telegram_authenticated_unsupported_update_is_a_noop(monkeypatch) -> None:
    database = _TelegramDatabase({"id": BUSINESS_A, "telegram_bot_token": BOT_TOKEN_A})
    calls: list[tuple[str, object]] = []
    monkeypatch.setattr(ai_agent_webhooks, "DatabaseManager", lambda: database)
    monkeypatch.setattr(
        ai_agent_webhooks,
        "dispatch_telegram_message_to_agent_blueprints",
        lambda *_args, **_kwargs: calls.append(("dispatch", _args)),
    )

    response = _client().post(
        _telegram_url(BUSINESS_A),
        json={"update_id": 10002, "callback_query": {"id": "ignored"}},
        headers=_telegram_headers(BUSINESS_A, BOT_TOKEN_A),
    )

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}
    assert calls == []
    assert database.closed is True


def test_telegram_revoked_bot_token_is_denied(monkeypatch) -> None:
    database = _TelegramDatabase({"id": BUSINESS_A, "telegram_bot_token": ""})
    monkeypatch.setattr(ai_agent_webhooks, "DatabaseManager", lambda: database)

    response = _client().post(
        _telegram_url(BUSINESS_A),
        json=_telegram_update(),
        headers={"X-Telegram-Bot-Api-Secret-Token": "0" * 64},
    )

    assert response.status_code == 403
    assert database.closed is True


def test_telegram_raw_token_url_is_retired_without_database_access(monkeypatch) -> None:
    monkeypatch.setattr(
        ai_agent_webhooks,
        "DatabaseManager",
        lambda: (_ for _ in ()).throw(AssertionError("retired endpoint queried the database")),
    )

    response = _client().post(f"/api/webhooks/telegram/{BOT_TOKEN_A}", json=_telegram_update())

    assert response.status_code == 410
