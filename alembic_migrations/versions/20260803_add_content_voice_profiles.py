"""add content voice profiles

Revision ID: 20260803_001
Revises: 20260729_002
Create Date: 2026-08-03
"""

from alembic import op


revision = "20260803_001"
down_revision = "20260729_002"
branch_labels = None
depends_on = None


def upgrade():
    # Legacy installations created this table lazily at runtime. New databases
    # must receive the base table from Alembic before the profile columns below.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS userexamples (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            example_type TEXT NOT NULL,
            example_text TEXT NOT NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_user_examples_user_type ON userexamples(user_id, example_type)")
    op.execute("ALTER TABLE userexamples ADD COLUMN IF NOT EXISTS business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE")
    op.execute("ALTER TABLE userexamples ADD COLUMN IF NOT EXISTS platform TEXT")
    op.execute("ALTER TABLE userexamples ADD COLUMN IF NOT EXISTS origin TEXT NOT NULL DEFAULT 'manual'")
    op.execute("ALTER TABLE userexamples ADD COLUMN IF NOT EXISTS quality_status TEXT NOT NULL DEFAULT 'reference'")
    op.execute("ALTER TABLE userexamples ADD COLUMN IF NOT EXISTS metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("CREATE INDEX IF NOT EXISTS idx_userexamples_business_type ON userexamples(business_id, example_type, created_at DESC)")
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS content_voice_profiles (
            business_id TEXT PRIMARY KEY REFERENCES businesses(id) ON DELETE CASCADE,
            summary TEXT NOT NULL DEFAULT '',
            preferences_json JSONB NOT NULL DEFAULT '{}',
            forbidden_phrases_json JSONB NOT NULL DEFAULT '[]',
            typical_ctas_json JSONB NOT NULL DEFAULT '[]',
            reference_example_ids_json JSONB NOT NULL DEFAULT '[]',
            status TEXT NOT NULL DEFAULT 'draft',
            version INTEGER NOT NULL DEFAULT 1,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            confirmed_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            confirmed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_content_voice_profile_status CHECK (status IN ('draft', 'confirmed'))
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS content_voice_profiles")
    op.execute("DROP INDEX IF EXISTS idx_userexamples_business_type")
    op.execute("ALTER TABLE userexamples DROP COLUMN IF EXISTS metadata_json")
    op.execute("ALTER TABLE userexamples DROP COLUMN IF EXISTS quality_status")
    op.execute("ALTER TABLE userexamples DROP COLUMN IF EXISTS origin")
    op.execute("ALTER TABLE userexamples DROP COLUMN IF EXISTS platform")
    op.execute("ALTER TABLE userexamples DROP COLUMN IF EXISTS business_id")
