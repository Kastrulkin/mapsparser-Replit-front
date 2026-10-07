"""add content to canonical lead journey flows

Revision ID: 20260827_002
Revises: 20260827_001
Create Date: 2026-08-27
"""

from alembic import op


revision = "20260827_002"
down_revision = "20260827_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE lead_journeys DROP CONSTRAINT IF EXISTS ck_lead_journeys_flow")
    op.execute(
        """
        ALTER TABLE lead_journeys
        ADD CONSTRAINT ck_lead_journeys_flow
        CHECK (selected_flow IS NULL OR selected_flow IN ('influencer', 'partnership', 'maps', 'content'))
        """
    )
    op.execute("ALTER TABLE journey_actions DROP CONSTRAINT IF EXISTS ck_journey_actions_flow")
    op.execute(
        """
        ALTER TABLE journey_actions
        ADD CONSTRAINT ck_journey_actions_flow
        CHECK (flow_type IN ('influencer', 'partnership', 'maps', 'content', 'upgrade'))
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_journeys_flow_status
        ON lead_journeys(selected_flow, status, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_lead_journeys_flow_status")
    op.execute("ALTER TABLE journey_actions DROP CONSTRAINT IF EXISTS ck_journey_actions_flow")
    op.execute(
        """
        ALTER TABLE journey_actions
        ADD CONSTRAINT ck_journey_actions_flow
        CHECK (flow_type IN ('influencer', 'partnership', 'maps', 'upgrade'))
        NOT VALID
        """
    )
    op.execute("ALTER TABLE lead_journeys DROP CONSTRAINT IF EXISTS ck_lead_journeys_flow")
    op.execute(
        """
        ALTER TABLE lead_journeys
        ADD CONSTRAINT ck_lead_journeys_flow
        CHECK (selected_flow IS NULL OR selected_flow IN ('influencer', 'partnership', 'maps'))
        NOT VALID
        """
    )
