from pathlib import Path

import pytest
from flask import Flask

from api import admin_knowledge_api, knowledge_api
from database_manager import DBConnectionWrapper
from core.knowledge_policy import (
    KnowledgePolicyError,
    deidentify_shared_payload,
    detect_pii_flags,
    prepare_external_model_text,
)
from services.knowledge_ingestion import (
    BELESHKO_CHANNEL_KEY,
    BELESHKO_MESSAGE_ID,
    BELESHKO_PRIMARY_TOPIC,
    analyze_facets,
    iter_telegram_archive,
    telegram_archive_dry_run,
)
from services.knowledge_graph_service import diff_external_card_snapshot
from services.knowledge_learning_service import create_aggregate_claim_candidate
from services.knowledge_public_telegram import parse_public_channel_html


def test_public_source_and_pii_are_independent_characteristics():
    text = "Публичный отзыв. Напишите owner@example.com или +7 999 123-45-67."

    flags = detect_pii_flags(text)
    payload = prepare_external_model_text(
        text,
        sensitivity_class="public",
        pii_flags=[],
        allowed_uses=["market"],
        purpose="market",
    )

    assert set(flags) == {"email", "phone"}
    assert payload["sensitivity_class"] == "public"
    assert "owner@example.com" not in payload["text"]
    assert "+7 999 123-45-67" not in payload["text"]
    assert payload["redacted"] is True


def test_database_connection_wrapper_forwards_psycopg_cursor_options():
    received = {}

    class RawCursor:
        pass

    class RawConnection:
        def cursor(self, *args, **kwargs):
            received["args"] = args
            received["kwargs"] = kwargs
            return RawCursor()

    wrapper = DBConnectionWrapper(RawConnection())
    wrapper.cursor("named", cursor_factory="factory")

    assert received == {
        "args": ("named",),
        "kwargs": {"cursor_factory": "factory"},
    }


@pytest.mark.parametrize("visibility", ["private", "invite"])
def test_private_telegram_is_never_sent_to_external_model(visibility):
    with pytest.raises(KnowledgePolicyError):
        prepare_external_model_text(
            "Закрытый отраслевой пост",
            sensitivity_class="public",
            allowed_uses=["market"],
            purpose="market",
            source_visibility=visibility,
        )


def test_external_model_requires_explicit_allowed_use():
    with pytest.raises(KnowledgePolicyError):
        prepare_external_model_text(
            "Публичный материал",
            sensitivity_class="public",
            allowed_uses=["localos_content"],
            purpose="outreach",
        )


def test_shared_payload_removes_business_identifiers_and_free_text():
    payload = deidentify_shared_payload(
        {
            "business_id": "business-1",
            "business_name": "Салон Север",
            "content_text": "Исходный отзыв",
            "sample_businesses": 8,
            "summary": "Связаться: owner@example.com",
        }
    )

    assert "business_id" not in payload
    assert "business_name" not in payload
    assert "content_text" not in payload
    assert payload["sample_businesses"] == 8
    assert "owner@example.com" not in payload["summary"]


def _archive_message(message_id: str, text: str) -> str:
    return (
        "Источник: Telegram export\n\n---\n"
        f"[2026-07-04 10:00:00+00:00 | Канал | id={message_id}]\n"
        f"{text}\n"
    )


def test_telegram_archive_deduplicates_split_files(tmp_path: Path):
    folder = tmp_path / "Канал"
    folder.mkdir()
    content = _archive_message("42", "Как вернуть клиентов и стабилизировать запись")
    (folder / "part-1.txt").write_text(content, encoding="utf-8")
    (folder / "part-2.txt").write_text(content, encoding="utf-8")

    messages = list(iter_telegram_archive(tmp_path))
    report = telegram_archive_dry_run(tmp_path, {"Канал": "https://t.me/example_channel"})

    assert len(messages) == 1
    assert report["sources_count"] == 1
    assert report["messages_count"] == 1
    assert report["sources"][0]["visibility"] == "public"


def test_telegram_analysis_keeps_independent_facets():
    facets = analyze_facets(
        "Показываем кейс: как салон вернул клиентов через CRM. Напишите, если нужен разбор.",
        channel_key="expert",
        message_id="12",
    )
    facet_types = {item["concept_type"] for item in facets}

    assert {"topic", "format", "cta", "offer"}.issubset(facet_types)


def test_beleshko_2950_keeps_primary_meaning_instead_of_maps_keyword():
    facets = analyze_facets(
        "Карты меняются, но вот что не изменится в салонном бизнесе в ближайшие 10 лет.",
        channel_key=BELESHKO_CHANNEL_KEY,
        message_id=BELESHKO_MESSAGE_ID,
    )
    topics = [item["label"] for item in facets if item["concept_type"] == "topic"]

    assert topics == [BELESHKO_PRIMARY_TOPIC]


def test_card_snapshot_change_is_observation_and_ignores_sparse_deletions():
    changes = diff_external_card_snapshot(
        {
            "title": "Салон Север",
            "phone": "+7 900 000-00-00",
            "site": "https://old.example",
        },
        {
            "title": "Салон Север",
            "phone": None,
            "site": "https://new.example",
        },
    )

    assert changes == {
        "before": {"site": "https://old.example"},
        "after": {"site": "https://new.example"},
    }


def test_public_telegram_html_parser_reads_messages_without_browser_automation():
    html = """
    <div class="tgme_widget_message" data-post="beauty/101">
      <div class="tgme_widget_message_text">Новый отраслевой сигнал</div>
      <a class="tgme_widget_message_date" href="https://t.me/beauty/101">
        <time datetime="2026-07-15T10:00:00+00:00"></time>
      </a>
    </div>
    """

    messages = parse_public_channel_html(html)

    assert messages == [
        {
            "external_id": "101",
            "content_text": "Новый отраслевой сигнал",
            "published_at": messages[0]["published_at"],
            "permalink": "https://t.me/beauty/101",
        }
    ]
    assert messages[0]["published_at"].isoformat() == "2026-07-15T10:00:00+00:00"


def test_small_sample_blocks_shared_claim_before_database_write():
    result = create_aggregate_claim_candidate(
        None,
        claim_type="service_change",
        title="Проверяемый вывод",
        statement_text="После изменения наблюдалась связь с метрикой.",
        industry="beauty",
        segment=None,
        evidence_level="associated_with",
        business_ids=["one", "two", "three", "four"],
        evidence_ids=["evidence-1"],
        limitations=[],
    )

    assert result["status"] == "blocked"
    assert result["required_businesses"] == 5


def test_migration_contains_graph_projection_and_privacy_tables():
    migration_path = Path(__file__).resolve().parents[1] / "alembic_migrations" / "versions" / "20260716_add_knowledge_layer.py"
    migration = migration_path.read_text(encoding="utf-8")

    for required_name in (
        "knowledge_sources",
        "knowledge_documents",
        "knowledge_assertions",
        "knowledge_evidence",
        "business_action_events",
        "learning_claims",
        "privacy_release_reviews",
        "knowledge_nodes_v",
        "knowledge_edges_v",
        "metric_observations_v",
    ):
        assert required_name in migration


def test_domain_imports_exclude_orphaned_business_rows():
    ingestion_path = Path(__file__).resolve().parents[1] / "src" / "services" / "knowledge_ingestion.py"
    ingestion = ingestion_path.read_text(encoding="utf-8")

    assert "JOIN businesses b ON b.id = u.business_id" in ingestion
    assert "JOIN businesses b ON b.id = c.business_id" in ingestion
    assert "adminprospectingleadpublicoffers" in ingestion
    assert "not_prevalence_evidence" in ingestion


class _FakeCursor:
    def execute(self, *_args, **_kwargs):
        return None


class _FakeConnection:
    def cursor(self):
        return _FakeCursor()


class _FakeDatabase:
    def __init__(self):
        self.conn = _FakeConnection()

    def close(self):
        return None


def test_business_knowledge_endpoint_rejects_cross_tenant_access(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(knowledge_api.knowledge_bp)
    monkeypatch.setattr(knowledge_api, "require_auth_from_request", lambda: {"user_id": "owner-1"})
    monkeypatch.setattr(knowledge_api, "knowledge_layer_enabled", lambda: True)
    monkeypatch.setattr(knowledge_api, "verify_business_access", lambda cursor, business_id, user_data: (False, "owner-2"))
    monkeypatch.setattr(knowledge_api, "DatabaseManager", _FakeDatabase)

    response = app.test_client().get("/api/business/business-2/knowledge/content-foundations")

    assert response.status_code == 403
    assert response.get_json()["error"] == "Нет доступа к бизнесу"


def test_admin_knowledge_endpoint_requires_superadmin(monkeypatch):
    app = Flask(__name__)
    app.register_blueprint(admin_knowledge_api.admin_knowledge_bp)
    monkeypatch.setattr(admin_knowledge_api, "verify_session", lambda token: {"user_id": "user-1", "is_superadmin": False})

    response = app.test_client().get(
        "/api/admin/knowledge/overview",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 403


def test_knowledge_schema_applies_on_postgres(run_migrations, postgres_container):
    import psycopg2

    raw_url = postgres_container.get_connection_url()
    dsn = raw_url.replace("postgresql+psycopg2://", "postgresql://", 1)
    conn = psycopg2.connect(dsn)
    cursor = conn.cursor()
    try:
        for relation in (
            "knowledge_sources",
            "knowledge_documents",
            "knowledge_assertions",
            "knowledge_evidence",
            "business_action_events",
            "learning_claims",
            "privacy_release_reviews",
            "knowledge_nodes_v",
            "knowledge_edges_v",
            "metric_observations_v",
        ):
            cursor.execute("SELECT to_regclass(%s)", (f"public.{relation}",))
            assert cursor.fetchone()[0] == relation
    finally:
        cursor.close()
        conn.close()
