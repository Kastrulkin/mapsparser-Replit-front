from datetime import datetime, timedelta, timezone
from pathlib import Path


def test_travel_signal_uses_specific_audience_pain():
    from services.telegram_research_service import classify_market_signal

    signal = classify_market_signal(
        "Трансфер до сих пор не подтвердили, а клиент уже недоволен и пишет турагенту.",
        "travel",
    )

    assert signal is not None
    assert signal["concept_type"] == "pain"
    assert signal["label"] == "Трансфер не подтверждён вовремя"
    assert signal["relevance_score"] >= 78


def test_generic_industry_still_detects_questions_and_pains():
    from services.telegram_research_service import classify_market_signal

    question = classify_market_signal("Подскажите, как выбрать программу занятий для ребёнка?", "school")
    pain = classify_market_signal("Очень сложно выбрать мастера, не понимаю, кому доверять.", "beauty")

    assert question is not None
    assert question["concept_type"] == "question"
    assert pain is not None
    assert pain["concept_type"] == "pain"


def test_priority_uses_relevance_when_telegram_has_no_metrics():
    from services.telegram_research_service import priority_score

    assert priority_score(73, 0) == 73
    assert priority_score(80, 60) == 73


def test_private_sources_are_tenant_only():
    from services.telegram_research_service import _source_policy

    sensitivity, allowed_uses = _source_policy({"visibility": "private"})

    assert sensitivity == "tenant_confidential"
    assert allowed_uses == ["localos_content"]


def test_market_sync_backfills_90_days_then_schedules_daily_refresh(monkeypatch):
    from services import telegram_research_service as service

    now = datetime.now(timezone.utc)
    source = {
        "id": "source-1",
        "business_id": "business-1",
        "account_id": "account-1",
        "title": "Тестовый рынок",
        "metadata_json": {"telegram_chat_id": "-1001", "industry_key": "school"},
        "cursor_json": {},
        "backfill_days": 90,
        "backfill_completed_at": None,
    }

    class Cursor:
        def execute(self, _query, _params=None):
            return None

        def close(self):
            return None

    class Connection:
        def cursor(self, *args, **kwargs):
            return Cursor()

    ingested = []
    finished = []
    monkeypatch.setattr(service, "_load_due_userbot_sources", lambda _conn, _limit: [source])
    monkeypatch.setattr(service, "load_userbot_account", lambda _cursor, **_kwargs: {"session_string": "ready"})
    monkeypatch.setattr(service, "_ingest_message", lambda _conn, _source, message: ingested.append(message) or {"stored": True, "inserted": True, "signal": False})
    monkeypatch.setattr(service, "_recalculate_source_engagement", lambda _conn, _source_id: None)
    monkeypatch.setattr(service, "_finish_source", lambda *args, **kwargs: finished.append((args, kwargs)))

    def fetch_page(_account, _peer, **_kwargs):
        return {
            "status": "ok",
            "messages": [
                {"id": 20, "text": "Свежий вопрос", "date": now.isoformat()},
                {"id": 10, "text": "Старое сообщение", "date": (now - timedelta(days=120)).isoformat()},
            ],
        }

    result = service.run_userbot_market_sync(
        Connection(),
        fetch_page_func=fetch_page,
        fetch_recent_func=lambda *_args, **_kwargs: {"status": "ok", "messages": []},
    )

    assert result["sources_checked"] == 1
    assert [message["id"] for message in ingested] == [20]
    assert finished[-1][1]["backfill_completed"] is True
    assert finished[-1][1]["minutes"] == 24 * 60


def test_market_sync_queries_all_due_sources_without_business_filter():
    source = Path("src/services/telegram_research_service.py").read_text(encoding="utf-8")

    query = source[source.index("def _load_due_userbot_sources"):source.index("FetchPage =")]
    assert "sync_mode = 'telegram_userbot'" in query
    assert "next_sync_at IS NULL OR next_sync_at <= NOW()" in query
    assert "business_id =" not in query


def test_public_preview_and_userbot_collection_do_not_overlap():
    source = Path("src/services/knowledge_public_telegram.py").read_text(encoding="utf-8")

    assert "sync_mode = 'public_preview'" in source
    assert "canonical_url LIKE %s" in source
    assert '("https://t.me/%", interval_seconds' in source
    assert 'os.getenv("TELEGRAM_HTTP_PROXY")' in source
    assert 'os.getenv("OUTBOUND_HTTP_PROXY")' in source
    assert "request.ProxyHandler" in source


def test_migration_adds_generic_market_source_lifecycle():
    migration = Path("alembic_migrations/versions/20260716_add_telegram_research.py").read_text(encoding="utf-8")

    for column in (
        "business_id",
        "account_id",
        "sync_mode",
        "sync_status",
        "backfill_days",
        "backfill_completed_at",
        "next_sync_at",
        "last_sync_error",
    ):
        assert column in migration
    assert "DEFAULT 90" in migration
    assert "telegram_userbot" in migration
