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


def test_localos_platform_aliases():
    from api.telegram_opportunity_radar_api import _is_localos_platform_alias

    assert _is_localos_platform_alias("__localos__") is True
    assert _is_localos_platform_alias("localos") is True
    assert _is_localos_platform_alias("ЛокалОС") is True
    assert _is_localos_platform_alias("business-1") is False


def test_normalize_keywords_deduplicates_and_splits():
    from services.telegram_opportunity_radar import normalize_keywords

    assert normalize_keywords(" KPI, кпи\nсмм; KPI ;  посты ") == ["KPI", "кпи", "смм", "посты"]


def test_collect_keywords_from_sources_handles_json_strings():
    from services.telegram_opportunity_radar import collect_keywords_from_sources

    sources = [
        {"monitor_config_json": {"keywords": ["KPI", "смм"]}},
        {"monitor_config_json": '{"keywords":["kpi","посты"]}'},
        {"monitor_config_json": {}},
    ]

    assert collect_keywords_from_sources(sources) == ["KPI", "смм", "посты"]


def test_monitor_creates_opportunity_for_keyword_match(monkeypatch):
    from services import telegram_opportunity_monitor as monitor

    class FakeCursor:
        description = []

        def __init__(self):
            self.updated = []

        def execute(self, query, params=None):
            if "UPDATE telegram_opportunity_sources" in query:
                self.updated.append(params)

        def fetchall(self):
            return [
                {
                    "id": "source-1",
                    "business_id": "biz-1",
                    "user_id": "user-1",
                    "account_id": None,
                    "source_type": "channel",
                    "title": "Бьюти чат",
                    "telegram_chat_id": "-1001",
                    "telegram_username": None,
                    "monitor_config_json": {"keywords": ["производительность", "kpi"]},
                    "last_message_id": "10",
                    "last_checked_at": None,
                }
            ]

    created_payloads = []
    notified = []

    def fake_fetch(_account, peer, *, after_message_id=None, limit=20):
        assert peer == "-1001"
        assert after_message_id == "10"
        return {
            "status": "ok",
            "messages": [
                {"id": 11, "text": "просто шум", "date": "2026-07-07T10:00:00+00:00"},
                {"id": 12, "text": "Как поднять производительность и KPI администратора?", "date": "2026-07-07T10:01:00+00:00"},
            ],
        }

    def fake_ingest(_cursor, payload):
        created_payloads.append(payload)
        return {"created": True, "opportunity": {"id": "opp-1"}}

    monkeypatch.setattr(monitor, "_resolve_account", lambda _cursor, _source: {"account_id": "acc-1"})
    monkeypatch.setattr(monitor, "ingest_opportunity", fake_ingest)
    monkeypatch.setattr(monitor, "notify_owner_for_opportunity", lambda _cursor, opportunity: notified.append(opportunity) or {"sent": True})

    cursor = FakeCursor()
    result = monitor.run_telegram_opportunity_monitor(cursor, source_limit=1, messages_limit=5, fetch_messages_func=fake_fetch)

    assert result["sources_checked"] == 1
    assert result["messages_seen"] == 2
    assert result["matches"] == 1
    assert result["created"] == 1
    assert result["alerts_sent"] == 1
    assert created_payloads[0]["message"]["id"] == "12"
    assert "производительность" in created_payloads[0]["reason"]
    assert cursor.updated[-1][0] == "12"


def test_monitor_keyword_match_handles_russian_inflection():
    from services.telegram_opportunity_monitor import _match_keywords

    assert _match_keywords("Как добиться роста производительности администратора?", ["производительность"]) == [
        "производительность"
    ]


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
