"""Move the first content and learning runtime DDL slice into Alembic.

Revision ID: 20260906_003
Revises: 20260906_002
"""
from alembic import op


revision = "20260906_003"
down_revision = "20260906_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS updated_at TIMESTAMP")
    op.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS original_generated_text TEXT")
    op.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS edited_before_approve BOOLEAN DEFAULT FALSE")
    op.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS prompt_key TEXT")
    op.execute("ALTER TABLE usernews ADD COLUMN IF NOT EXISTS prompt_version TEXT")
    op.execute("""CREATE TABLE IF NOT EXISTS ailearningevents (
        id UUID PRIMARY KEY, intent TEXT NOT NULL DEFAULT 'operations',
        capability TEXT NOT NULL, event_type TEXT NOT NULL, accepted BOOLEAN,
        rejected BOOLEAN, edited_before_accept BOOLEAN, outcome TEXT,
        user_id UUID, business_id UUID, action_id UUID, prompt_key TEXT,
        prompt_version TEXT, draft_text TEXT, final_text TEXT,
        metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ailearningevents_created_at ON ailearningevents (created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ailearningevents_capability_intent ON ailearningevents (capability, intent)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_ailearningevents_user_business ON ailearningevents (user_id, business_id)")


def downgrade():
    # Learning history and legacy user-news columns survive a code rollback.
    pass
