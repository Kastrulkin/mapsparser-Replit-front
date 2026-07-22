"""add provider-aware LLM routing observability

Revision ID: 20260722_001
Revises: 20260720_002
Create Date: 2026-07-22 10:00:00.000000
"""

from alembic import op


revision = "20260722_001"
down_revision = "20260720_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE tokenusage ADD COLUMN IF NOT EXISTS provider TEXT")
    op.execute("ALTER TABLE tokenusage ADD COLUMN IF NOT EXISTS provider_request_id TEXT")
    op.execute("ALTER TABLE tokenusage ADD COLUMN IF NOT EXISTS latency_ms INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE tokenusage ADD COLUMN IF NOT EXISTS request_status TEXT NOT NULL DEFAULT 'completed'")
    op.execute("ALTER TABLE tokenusage ADD COLUMN IF NOT EXISTS prompt_version TEXT")
    op.execute("ALTER TABLE tokenusage ADD COLUMN IF NOT EXISTS shadow BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE tokenusage ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("UPDATE tokenusage SET provider = 'gigachat' WHERE provider IS NULL")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tokenusage_provider_task_created
        ON tokenusage(provider, task_type, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_tokenusage_shadow_created
        ON tokenusage(shadow, created_at DESC)
        WHERE shadow = TRUE
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_tokenusage_shadow_created")
    op.execute("DROP INDEX IF EXISTS idx_tokenusage_provider_task_created")
    op.execute("ALTER TABLE tokenusage DROP COLUMN IF EXISTS metadata_json")
    op.execute("ALTER TABLE tokenusage DROP COLUMN IF EXISTS shadow")
    op.execute("ALTER TABLE tokenusage DROP COLUMN IF EXISTS prompt_version")
    op.execute("ALTER TABLE tokenusage DROP COLUMN IF EXISTS request_status")
    op.execute("ALTER TABLE tokenusage DROP COLUMN IF EXISTS latency_ms")
    op.execute("ALTER TABLE tokenusage DROP COLUMN IF EXISTS provider_request_id")
    op.execute("ALTER TABLE tokenusage DROP COLUMN IF EXISTS provider")
