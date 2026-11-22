"""add parallel Cloud.ru embedding vectors

Revision ID: 20261122_cloudru_vectors
Revises: 20261122_initial_business_setup
Create Date: 2026-11-22 14:30:00.000000
"""

from alembic import op


revision = "20261122_cloudru_vectors"
down_revision = "20261122_initial_business_setup"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS knowledge_embedding_vectors (
            id UUID PRIMARY KEY,
            chunk_id UUID NOT NULL REFERENCES knowledge_embedding_chunks(id) ON DELETE CASCADE,
            provider TEXT NOT NULL,
            model TEXT NOT NULL,
            embedding_version TEXT NOT NULL,
            dimensions INTEGER NOT NULL,
            embedding_2048 HALFVEC(2048),
            status TEXT NOT NULL DEFAULT 'pending',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            locked_at TIMESTAMPTZ,
            locked_by TEXT,
            provider_request_id TEXT,
            error_code TEXT,
            embedded_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_knowledge_embedding_vectors_dimensions CHECK (dimensions = 2048),
            CONSTRAINT ck_knowledge_embedding_vectors_status CHECK (
                status IN ('pending', 'running', 'ready', 'retry', 'failed', 'stale')
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_knowledge_embedding_vectors_space
        ON knowledge_embedding_vectors(chunk_id, provider, model, embedding_version)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_embedding_vectors_due
        ON knowledge_embedding_vectors(status, next_attempt_at, created_at)
        WHERE status IN ('pending', 'retry')
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_knowledge_embedding_vectors_cloudru_hnsw
        ON knowledge_embedding_vectors
        USING hnsw (embedding_2048 halfvec_cosine_ops)
        WITH (m = 16, ef_construction = 96)
        WHERE status = 'ready'
          AND provider = 'cloudru'
          AND dimensions = 2048
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS knowledge_embedding_vectors")
