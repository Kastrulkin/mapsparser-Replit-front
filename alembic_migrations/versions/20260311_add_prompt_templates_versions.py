"""add prompt templates versioning tables

Revision ID: 20260311_001
Revises: 20260310_004
Create Date: 2026-03-11 16:20:00.000000
"""

from alembic import op


revision = "20260311_001"
down_revision = "20260308_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS prompttemplates (
            id TEXT PRIMARY KEY,
            prompt_key TEXT UNIQUE NOT NULL,
            description TEXT,
            current_version INTEGER NOT NULL DEFAULT 1,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_by TEXT
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS prompttemplateversions (
            id TEXT PRIMARY KEY,
            template_id TEXT NOT NULL REFERENCES prompttemplates(id) ON DELETE CASCADE,
            prompt_key TEXT NOT NULL,
            version INTEGER NOT NULL,
            prompt_text TEXT NOT NULL,
            description TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_by TEXT,
            UNIQUE (prompt_key, version)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_prompttemplateversions_prompt_key ON prompttemplateversions(prompt_key, version DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_prompttemplates_active ON prompttemplates(is_active)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_prompttemplates_active")
    op.execute("DROP INDEX IF EXISTS idx_prompttemplateversions_prompt_key")
    op.execute("DROP TABLE IF EXISTS prompttemplateversions")
    op.execute("DROP TABLE IF EXISTS prompttemplates")
