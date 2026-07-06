import hashlib
import hmac
import json
import sys


if "src" not in sys.path:
    sys.path.insert(0, "src")


def test_score_message_detects_owner_pain():
    from services.telegram_opportunity_radar import score_message

    result = score_message("Коллеги, налоги и НДС с 2026 съедают прибыль, уже не понимаю что делать")

    assert result is not None
    assert result["signal_type"] == "owner_pain"
    assert result["score"] >= 65


def test_score_message_ignores_short_noise():
    from services.telegram_opportunity_radar import score_message

    assert score_message("ок") is None


def test_openclaw_signature_accepts_raw_body(monkeypatch):
    from flask import Flask
    from api.telegram_opportunity_radar_api import _verify_openclaw_signature

    app = Flask(__name__)
    body = json.dumps({"message": "hello"}, separators=(",", ":"), sort_keys=True).encode("utf-8")
    secret = "secret"
    signature = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    monkeypatch.setenv("OPENCLAW_WEBHOOK_SECRET", secret)

    with app.test_request_context(
        "/api/telegram-opportunity-radar/ingest",
        method="POST",
        data=body,
        headers={"X-OpenClaw-Signature": signature, "Content-Type": "application/json"},
    ):
        assert _verify_openclaw_signature(body) is True


def test_openclaw_signature_rejects_wrong_secret(monkeypatch):
    from flask import Flask
    from api.telegram_opportunity_radar_api import _verify_openclaw_signature

    app = Flask(__name__)
    body = b'{"message":"hello"}'
    monkeypatch.setenv("OPENCLAW_WEBHOOK_SECRET", "secret")

    with app.test_request_context(
        "/api/telegram-opportunity-radar/ingest",
        method="POST",
        data=body,
        headers={"X-OpenClaw-Signature": "bad", "Content-Type": "application/json"},
    ):
        assert _verify_openclaw_signature(body) is False
