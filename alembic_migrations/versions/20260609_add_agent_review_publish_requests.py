"""add agent review publish requests

Revision ID: 20260609_005
Revises: 20260609_004
Create Date: 2026-06-09
"""

from alembic import op


revision = "20260609_005"
down_revision = "20260609_004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_review_publish_requests (
            id TEXT PRIMARY KEY,
            draft_id TEXT NOT NULL,
            review_id TEXT NOT NULL,
            business_id TEXT NOT NULL,
            run_id TEXT,
            user_id TEXT,
            source TEXT,
            reply_text TEXT NOT NULL,
            status TEXT NOT NULL,
            publish_state TEXT NOT NULL,
            provider_request_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            audit_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            provider_write_performed BOOLEAN NOT NULL DEFAULT FALSE,
            error_text TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_agent_review_publish_requests_draft
        ON agent_review_publish_requests(draft_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_agent_review_publish_requests_business_state
        ON agent_review_publish_requests(business_id, publish_state, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_agent_review_publish_requests_business_state")
    op.execute("DROP INDEX IF EXISTS uq_agent_review_publish_requests_draft")
    op.execute("DROP TABLE IF EXISTS agent_review_publish_requests")
