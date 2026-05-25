"""add agent builder sessions

Revision ID: 20260525_001
Revises: 20260523_001
Create Date: 2026-05-25
"""

from alembic import op


revision = "20260525_001"
down_revision = "20260523_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS agent_builder_sessions (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            created_by_user_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            initial_prompt TEXT NOT NULL DEFAULT '',
            category TEXT NOT NULL DEFAULT 'custom',
            messages_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            preview_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            missing_questions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            blueprint_id TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_builder_sessions_business_created ON agent_builder_sessions(business_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_agent_builder_sessions_user_status ON agent_builder_sessions(created_by_user_id, status)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_agent_builder_sessions_user_status")
    op.execute("DROP INDEX IF EXISTS idx_agent_builder_sessions_business_created")
    op.execute("DROP TABLE IF EXISTS agent_builder_sessions")
