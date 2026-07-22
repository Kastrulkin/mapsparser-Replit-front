"""add pgvector semantic memory

Revision ID: 20260722_002
Revises: 20260722_001
Create Date: 2026-07-22 12:00:00.000000
"""

from alembic import op


revision = "20260722_002"
down_revision = "20260722_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_embedding_chunks (
            id UUID PRIMARY KEY,
            chunk_hash TEXT NOT NULL,
            content_text TEXT NOT NULL,
            token_count INTEGER NOT NULL DEFAULT 0,
            embedding_model TEXT NOT NULL,
            embedding_version TEXT NOT NULL DEFAULT 'v1',
            dimensions INTEGER NOT NULL DEFAULT 2560,
            embedding HALFVEC(2560),
            status TEXT NOT NULL DEFAULT 'pending',
            provider_request_id TEXT,
            error_code TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            embedded_at TIMESTAMPTZ,
            stale_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_knowledge_embedding_chunks_status CHECK (
                status IN ('pending', 'ready', 'retry', 'blocked', 'failed', 'stale')
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_embedding_chunk_version
        ON knowledge_embedding_chunks(chunk_hash, embedding_model, embedding_version)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_embedding_chunks_ready
        ON knowledge_embedding_chunks(status, updated_at)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_embedding_chunks_hnsw
        ON knowledge_embedding_chunks
        USING hnsw (embedding halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 96)
        WHERE status = 'ready' AND stale_at IS NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_embedding_chunks_fts
        ON knowledge_embedding_chunks
        USING gin (to_tsvector('russian', content_text))
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_document_chunk_links (
            document_id UUID NOT NULL REFERENCES knowledge_documents(id) ON DELETE CASCADE,
            chunk_id UUID NOT NULL REFERENCES knowledge_embedding_chunks(id) ON DELETE CASCADE,
            document_content_hash TEXT NOT NULL,
            chunk_ordinal INTEGER NOT NULL,
            char_start INTEGER NOT NULL DEFAULT 0,
            char_end INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (document_id, chunk_id, chunk_ordinal)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_document_chunk_links_chunk
        ON knowledge_document_chunk_links(chunk_id, document_id)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_embedding_jobs (
            id UUID PRIMARY KEY,
            chunk_id UUID NOT NULL REFERENCES knowledge_embedding_chunks(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'queued',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 4,
            next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            locked_at TIMESTAMPTZ,
            locked_by TEXT,
            error_code TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_knowledge_embedding_jobs_status CHECK (
                status IN ('queued', 'running', 'retry', 'completed', 'blocked', 'dead_letter')
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_embedding_jobs_active
        ON knowledge_embedding_jobs(chunk_id)
        WHERE status IN ('queued', 'running', 'retry')
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_embedding_jobs_due
        ON knowledge_embedding_jobs(status, next_attempt_at)
        WHERE status IN ('queued', 'retry')
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_retrieval_events (
            id UUID PRIMARY KEY,
            pipeline_id TEXT,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            consumer TEXT NOT NULL,
            purpose TEXT NOT NULL,
            query_hash TEXT NOT NULL,
            retrieval_mode TEXT NOT NULL,
            result_chunk_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            selected_evidence_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            latency_ms INTEGER NOT NULL DEFAULT 0,
            outcome TEXT NOT NULL DEFAULT 'shown',
            edit_ratio NUMERIC(6, 5),
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_knowledge_retrieval_events_mode CHECK (
                retrieval_mode IN ('hybrid', 'vector', 'lexical', 'graph', 'none')
            ),
            CONSTRAINT ck_knowledge_retrieval_events_outcome CHECK (
                outcome IN ('shown', 'accepted', 'edited', 'rejected', 'published', 'applied', 'reverted', 'stale')
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_retrieval_events_business
        ON knowledge_retrieval_events(business_id, consumer, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE OR REPLACE FUNCTION sync_knowledge_document_embedding_links()
        RETURNS trigger AS $$
        BEGIN
            IF NEW.invalidated_at IS NOT NULL
               OR NEW.content_hash IS DISTINCT FROM OLD.content_hash THEN
                DELETE FROM knowledge_document_chunk_links WHERE document_id = NEW.id;
                UPDATE knowledge_embedding_chunks chunk
                SET status = 'stale', stale_at = NOW(), updated_at = NOW()
                WHERE chunk.stale_at IS NULL
                  AND NOT EXISTS (
                      SELECT 1 FROM knowledge_document_chunk_links link WHERE link.chunk_id = chunk.id
                  );
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql
        """
    )
    op.execute("DROP TRIGGER IF EXISTS trg_knowledge_document_embedding_links ON knowledge_documents")
    op.execute(
        """
        CREATE TRIGGER trg_knowledge_document_embedding_links
        AFTER UPDATE OF content_hash, invalidated_at ON knowledge_documents
        FOR EACH ROW EXECUTE FUNCTION sync_knowledge_document_embedding_links()
        """
    )


def downgrade():
    op.execute("DROP TRIGGER IF EXISTS trg_knowledge_document_embedding_links ON knowledge_documents")
    op.execute("DROP FUNCTION IF EXISTS sync_knowledge_document_embedding_links()")
    op.execute("DROP TABLE IF EXISTS knowledge_retrieval_events")
    op.execute("DROP TABLE IF EXISTS knowledge_embedding_jobs")
    op.execute("DROP TABLE IF EXISTS knowledge_document_chunk_links")
    op.execute("DROP TABLE IF EXISTS knowledge_embedding_chunks")
