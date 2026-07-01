"""add service catalog compression requests

Revision ID: 20260701_001
Revises: 20260629_001
Create Date: 2026-07-01
"""

from alembic import op


revision = "20260701_001"
down_revision = "20260629_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS service_catalog_compression_requests (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            user_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft_ready',
            before_count INTEGER NOT NULL DEFAULT 0,
            after_count INTEGER NOT NULL DEFAULT 0,
            groups_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            diff_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_service_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            archived_service_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            applied_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_service_catalog_compression_business_status
        ON service_catalog_compression_requests (business_id, status, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_service_catalog_compression_business_status")
    op.execute("DROP TABLE IF EXISTS service_catalog_compression_requests")
