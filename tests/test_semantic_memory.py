from pathlib import Path

import pytest

from core.knowledge_policy import KnowledgePolicyError, prepare_external_model_text
from services.knowledge_embeddings import (
    _find_embedding_balance,
    _vector_literal,
    split_text,
)
from services.knowledge_retrieval import KnowledgeSearchRequest, _filters, _rrf


ROOT = Path(__file__).resolve().parents[1]


def test_chunking_is_stable_and_overlapping():
    text = ("Первое предложение. Второе предложение.\n\n" * 180).strip()

    first = split_text(text, target_chars=1200, overlap_chars=120)
    second = split_text(text, target_chars=1200, overlap_chars=120)

    assert len(first) > 1
    assert [item.chunk_hash for item in first] == [item.chunk_hash for item in second]
    assert all(item.text and item.token_count > 0 for item in first)
    assert first[1].char_start < first[0].char_end


def test_embedding_dimension_fails_closed():
    with pytest.raises(ValueError, match="EMBEDDING_DIMENSION_MISMATCH"):
        _vector_literal([0.1] * 10)

    assert _vector_literal([0.0] * 2560).startswith("[0.0,0.0")


def test_embedding_balance_sums_embedding_packages_only():
    payload = {
        "balances": [
            {"name": "Embeddings", "remaining_tokens": 50_000_000},
            {"model": "EmbeddingsGigaR", "balance": 10_000_000},
            {"name": "GigaChat Max", "remaining_tokens": 3_000_000},
        ]
    }

    assert _find_embedding_balance(payload) == 60_000_000


def test_private_telegram_never_reaches_external_model():
    with pytest.raises(KnowledgePolicyError, match="Private or invite-only"):
        prepare_external_model_text(
            "Закрытое сообщение",
            sensitivity_class="shared_deidentified",
            allowed_uses=["industry_recommendations"],
            purpose="industry_recommendations",
            source_visibility="private",
        )


def test_retrieval_filter_is_tenant_and_purpose_scoped():
    sql, params = _filters(
        KnowledgeSearchRequest(
            business_id="business-one",
            query="спрос на услуги",
            purpose="industry_recommendations",
            source_types=("public_review",),
        )
    )

    assert "document.allowed_uses @> jsonb_build_array(%s::text)" in sql
    assert "document.business_id = %s" in sql
    assert "document.business_id IS NULL" in sql
    assert params[:2] == ["industry_recommendations", "business-one"]
    assert "business-two" not in params


def test_rrf_rewards_agreement_without_losing_provenance():
    vector = [
        {"chunk_id": "both", "similarity": 0.91, "source_confidence": 0.8},
        {"chunk_id": "vector-only", "similarity": 0.95, "source_confidence": 0.8},
    ]
    lexical = [
        {"chunk_id": "both", "similarity": 0.8, "source_confidence": 0.8},
        {"chunk_id": "lexical-only", "similarity": 0.7, "source_confidence": 0.8},
    ]

    ranked = _rrf(vector, lexical)

    assert ranked[0]["chunk_id"] == "both"
    assert ranked[0]["modes"] == ["vector", "lexical"]


def test_schema_and_runtime_use_pgvector_halfvec_and_safety_tables():
    migration = (ROOT / "alembic_migrations/versions/20260722_add_semantic_memory.py").read_text()
    compose = (ROOT / "docker-compose.yml").read_text()

    assert "pgvector/pgvector:0.8.0-pg16-trixie" in compose
    assert "CREATE EXTENSION IF NOT EXISTS vector" in migration
    assert "HALFVEC(2560)" in migration
    assert "halfvec_cosine_ops" in migration
    for table in (
        "knowledge_embedding_chunks",
        "knowledge_document_chunk_links",
        "knowledge_embedding_jobs",
        "knowledge_retrieval_events",
    ):
        assert table in migration


def test_ingestion_excludes_raw_private_chat_and_unapproved_drafts():
    source = (ROOT / "src/services/knowledge_embedding_ingestion.py").read_text()

    assert "private_chat_aggregate" in source
    assert "raw_messages_included\": False" in source
    assert "COALESCE(n.approved, 0) = 1" in source
    assert "author_removed\": True" in source
    assert "raw_payload" not in source
