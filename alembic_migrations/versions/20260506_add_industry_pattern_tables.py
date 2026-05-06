"""add industry pattern proposal tables

Revision ID: 20260506_001
Revises: 20260505_002
Create Date: 2026-05-06
"""

from alembic import op


revision = "20260506_001"
down_revision = "20260505_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS industry_pattern_versions (
            id TEXT PRIMARY KEY,
            industry_key TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            pattern_text TEXT NOT NULL,
            examples_json JSONB,
            source_proposal_id TEXT,
            version TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            activated_by TEXT,
            activated_at TIMESTAMPTZ DEFAULT NOW(),
            disabled_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS industry_pattern_proposals (
            id TEXT PRIMARY KEY,
            industry_key TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            proposed_pattern TEXT NOT NULL,
            examples_json JSONB,
            source_period_start DATE NOT NULL,
            source_period_end DATE NOT NULL,
            source_counts_json JSONB,
            confidence NUMERIC(5, 2) NOT NULL DEFAULT 0,
            risk_level TEXT NOT NULL DEFAULT 'medium',
            status TEXT NOT NULL DEFAULT 'pending_review',
            reviewed_by TEXT,
            reviewed_at TIMESTAMPTZ,
            decision_comment TEXT,
            activated_version_id TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS industry_pattern_decisions (
            id TEXT PRIMARY KEY,
            proposal_id TEXT NOT NULL,
            decision TEXT NOT NULL,
            decided_by TEXT,
            decision_comment TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_industry_pattern_proposals_status ON industry_pattern_proposals(status, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_industry_pattern_proposals_industry ON industry_pattern_proposals(industry_key, pattern_type)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_industry_pattern_versions_active ON industry_pattern_versions(industry_key, pattern_type, status)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_industry_pattern_versions_active")
    op.execute("DROP INDEX IF EXISTS idx_industry_pattern_proposals_industry")
    op.execute("DROP INDEX IF EXISTS idx_industry_pattern_proposals_status")
    op.execute("DROP TABLE IF EXISTS industry_pattern_decisions")
    op.execute("DROP TABLE IF EXISTS industry_pattern_proposals")
    op.execute("DROP TABLE IF EXISTS industry_pattern_versions")
