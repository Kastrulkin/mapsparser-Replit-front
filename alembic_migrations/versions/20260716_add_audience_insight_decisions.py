"""add tenant-scoped audience insight decisions

Revision ID: 20260716_003
Revises: 20260716_002
Create Date: 2026-07-16 17:15:00.000000
"""

from alembic import op


revision = "20260716_003"
down_revision = "20260716_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS business_audience_insight_decisions (
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            concept_id UUID NOT NULL REFERENCES knowledge_concepts(id) ON DELETE CASCADE,
            decision TEXT NOT NULL,
            decided_by TEXT,
            decided_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (business_id, concept_id),
            CONSTRAINT ck_business_audience_insight_decision
            CHECK (decision IN ('use_in_plan', 'save_as_rule', 'ignored'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_business_audience_insight_decisions_concept
        ON business_audience_insight_decisions(concept_id, business_id)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_business_audience_insight_decisions_concept")
    op.execute("DROP TABLE IF EXISTS business_audience_insight_decisions")
