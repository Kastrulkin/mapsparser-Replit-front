"""add industry pattern impact events

Revision ID: 20260506_002
Revises: 20260506_001
Create Date: 2026-05-06
"""

from alembic import op


revision = "20260506_002"
down_revision = "20260506_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS industry_pattern_impact_events (
            id TEXT PRIMARY KEY,
            version_id TEXT NOT NULL,
            industry_key TEXT NOT NULL,
            pattern_type TEXT NOT NULL,
            business_id TEXT,
            user_id TEXT,
            source TEXT NOT NULL,
            event_type TEXT NOT NULL,
            result_status TEXT,
            metrics_json JSONB,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_industry_pattern_impact_version ON industry_pattern_impact_events(version_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_industry_pattern_impact_industry ON industry_pattern_impact_events(industry_key, pattern_type, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_industry_pattern_impact_event ON industry_pattern_impact_events(event_type, created_at DESC)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_industry_pattern_impact_event")
    op.execute("DROP INDEX IF EXISTS idx_industry_pattern_impact_industry")
    op.execute("DROP INDEX IF EXISTS idx_industry_pattern_impact_version")
    op.execute("DROP TABLE IF EXISTS industry_pattern_impact_events")
