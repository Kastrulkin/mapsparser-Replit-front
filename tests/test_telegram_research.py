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


def test_market_sync_rolls_back_only_failed_source(monkeypatch):
    from services import telegram_research_service as service

    source = {
        "id": "source-failed",
        "business_id": "business-1",
        "account_id": "account-1",
        "metadata_json": {"telegram_chat_id": "-1001", "industry_key": "travel"},
        "cursor_json": {},
        "backfill_days": 90,
        "backfill_completed_at": None,
    }
    statements = []

    class Cursor:
        def execute(self, query, _params=None):
            statements.append(" ".join(str(query).split()))

        def close(self):
            return None

    class Connection:
        def cursor(self, *args, **kwargs):
            return Cursor()

    finished = []
    monkeypatch.setattr(service, "_load_due_userbot_sources", lambda _conn, _limit: [source])
    monkeypatch.setattr(service, "load_userbot_account", lambda _cursor, **_kwargs: {"session_string": "ready"})
    monkeypatch.setattr(service, "_ingest_message", lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("broken source")))
    monkeypatch.setattr(service, "_finish_source", lambda *args, **kwargs: finished.append((args, kwargs)))

    result = service.run_userbot_market_sync(
        Connection(),
        fetch_page_func=lambda *_args, **_kwargs: {
            "status": "ok",
            "messages": [{"id": 20, "text": "Fresh question", "date": datetime.now(timezone.utc).isoformat()}],
        },
        fetch_recent_func=lambda *_args, **_kwargs: {"status": "ok", "messages": []},
    )

    assert result["errors"][0]["message"] == "RuntimeError: broken source"
    assert "SAVEPOINT telegram_source_sync" in statements
    assert "ROLLBACK TO SAVEPOINT telegram_source_sync" in statements
    assert "RELEASE SAVEPOINT telegram_source_sync" in statements
    assert finished[-1][1]["minutes"] == service.RETRY_INTERVAL_MINUTES


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


def test_migration_allows_question_market_concepts():
    migration = Path("alembic_migrations/versions/20260716_allow_question_knowledge_concepts.py").read_text(encoding="utf-8")

    assert "'question'" in migration
    assert "DROP CONSTRAINT IF EXISTS ck_knowledge_concepts_type" in migration


def test_shared_audience_decision_does_not_leak_between_businesses(run_migrations, postgres_container):
    import uuid

    import psycopg2

    from services.telegram_research_service import decide_audience_insight, list_audience_insights

    raw_url = postgres_container.get_connection_url()
    dsn = raw_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    conn = psycopg2.connect(dsn)
    source_id = str(uuid.uuid4())
    document_id = str(uuid.uuid4())
    concept_id = str(uuid.uuid4())
    assertion_id = str(uuid.uuid4())
    evidence_id = str(uuid.uuid4())
    cursor = conn.cursor()
    try:
        cursor.execute(
            """
            INSERT INTO businesses (id, owner_id, name)
            VALUES ('business-a', 'owner-a', 'Business A'),
                   ('business-b', 'owner-b', 'Business B')
            ON CONFLICT (id) DO NOTHING
            """
        )
        cursor.execute(
            """
            INSERT INTO knowledge_sources (
                id, source_type, external_key, title, source_role, visibility,
                sensitivity_class, allowed_uses, status
            ) VALUES (%s, 'telegram', %s, 'Public market source', 'community',
                      'public', 'public', '["client_content"]'::jsonb, 'active')
            """,
            (source_id, f"test-shared-decision:{source_id}"),
        )
        cursor.execute(
            """
            INSERT INTO knowledge_documents (
                id, source_id, external_id, document_type, content_text,
                content_hash, sensitivity_class, allowed_uses
            ) VALUES (%s, %s, 'message-1', 'telegram_message', 'Shared market signal',
                      'hash-1', 'public', '["client_content"]'::jsonb)
            """,
            (document_id, source_id),
        )
        cursor.execute(
            """
            INSERT INTO knowledge_concepts (
                id, concept_type, canonical_key, label, industry, business_id,
                sensitivity_class, allowed_uses
            ) VALUES (%s, 'pain', %s, 'Shared audience pain', 'beauty', NULL,
                      'public', '["client_content"]'::jsonb)
            """,
            (concept_id, f"shared-audience-pain-{concept_id}"),
        )
        cursor.execute(
            """
            INSERT INTO knowledge_assertions (
                id, assertion_type, subject_type, subject_id, predicate,
                object_type, object_id, business_id, industry, confidence,
                allowed_uses, sensitivity_class, analysis_version
            ) VALUES (%s, 'audience_signal', 'document', %s, 'expresses',
                      'concept', %s, NULL, 'beauty', 0.9,
                      '["client_content"]'::jsonb, 'public', 'test-v1')
            """,
            (assertion_id, document_id, concept_id),
        )
        cursor.execute(
            """
            INSERT INTO knowledge_evidence (
                id, assertion_id, document_id, source_id, excerpt, confidence,
                analysis_version, allowed_uses, sensitivity_class
            ) VALUES (%s, %s, %s, %s, 'Shared market signal', 0.9,
                      'test-v1', '["client_content"]'::jsonb, 'public')
            """,
            (evidence_id, assertion_id, document_id, source_id),
        )

        before = list_audience_insights(conn, business_id="business-a", industry="beauty")
        assert before[0]["decision"] == ""

        decide_audience_insight(
            conn,
            business_id="business-a",
            insight_id=concept_id,
            decision="ignored",
            user_id="user-a",
        )

        business_b_items = list_audience_insights(conn, business_id="business-b", industry="beauty")
        assert business_b_items[0]["decision"] == ""
    finally:
        conn.rollback()
        cursor.close()
        conn.close()


def test_private_dialog_cannot_be_promoted_to_public_by_payload(monkeypatch):
    from flask import Flask

    from api import telegram_research_api

    captured = {}

    class FakeConnection:
        def commit(self):
            return None

        def rollback(self):
            return None

    class FakeCursor:
        def execute(self, _query, _params=None):
            return None

    class FakeDatabase:
        def __init__(self):
            self.conn = FakeConnection()

        def close(self):
            return None

    database = FakeDatabase()
    cursor = FakeCursor()

    monkeypatch.setattr(
        telegram_research_api,
        "_require_business",
        lambda _business_id: (database, cursor, {"user_id": "user-a"}, None),
    )
    monkeypatch.setattr(
        telegram_research_api,
        "_account_for_business",
        lambda _cursor, _business_id: {"account_id": "account-a", "session_string": "ready"},
    )
    monkeypatch.setattr(
        telegram_research_api,
        "_business_knowledge_context",
        lambda _cursor, _business_id: {"industry_key": "beauty", "audience": "customers"},
    )

    def capture_knowledge_source(_conn, **payload):
        captured.update(payload)
        return {"id": "knowledge-source-a", "title": payload["title"]}

    monkeypatch.setattr(telegram_research_api, "upsert_knowledge_source", capture_knowledge_source)
    monkeypatch.setattr(
        telegram_research_api,
        "upsert_radar_source",
        lambda _cursor, _payload: {"id": "radar-source-a"},
    )

    app = Flask(__name__)
    app.register_blueprint(telegram_research_api.telegram_research_bp)
    response = app.test_client().put(
        "/api/business/business-a/telegram-research/sources",
        json={
            "sources": [
                {
                    "telegram_chat_id": "-100-private",
                    "telegram_username": None,
                    "title": "Private customer chat",
                    "visibility": "public",
                    "source_type": "chat",
                }
            ]
        },
    )

    if response.status_code < 400:
        assert captured["visibility"] == "private"
        assert captured["sensitivity_class"] == "tenant_confidential"
        assert captured["allowed_uses"] == ["localos_content"]


def test_private_message_retention_qualifies_document_metadata_column():
    source = Path("src/services/telegram_research_service.py").read_text(encoding="utf-8")

    assert "metadata_json = d.metadata_json - 'reactions'" in source
