"""add automation to canonical lead journey flows

Revision ID: 20260829_001
Revises: 20260828_001
Create Date: 2026-08-29
"""

from alembic import op


revision = "20260829_001"
down_revision = "20260828_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE lead_journeys DROP CONSTRAINT IF EXISTS ck_lead_journeys_flow")
    op.execute(
        """
        ALTER TABLE lead_journeys
        ADD CONSTRAINT ck_lead_journeys_flow
        CHECK (selected_flow IS NULL OR selected_flow IN (
            'influencer', 'partnership', 'maps', 'content', 'automation'
        ))
        """
    )
    op.execute("ALTER TABLE journey_actions DROP CONSTRAINT IF EXISTS ck_journey_actions_flow")
    op.execute(
        """
        ALTER TABLE journey_actions
        ADD CONSTRAINT ck_journey_actions_flow
        CHECK (flow_type IN (
            'influencer', 'partnership', 'maps', 'content', 'automation', 'upgrade'
        ))
        """
    )


def downgrade():
    op.execute(
        """
        DO $$
        BEGIN
            IF EXISTS (SELECT 1 FROM journey_actions WHERE flow_type = 'automation')
               OR EXISTS (SELECT 1 FROM lead_journeys WHERE selected_flow = 'automation') THEN
                RAISE EXCEPTION 'Cannot remove automation journey flow while automation journeys exist';
            END IF;
        END
        $$
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
    op.execute("ALTER TABLE lead_journeys DROP CONSTRAINT IF EXISTS ck_lead_journeys_flow")
    op.execute(
        """
        ALTER TABLE lead_journeys
        ADD CONSTRAINT ck_lead_journeys_flow
        CHECK (selected_flow IS NULL OR selected_flow IN (
            'influencer', 'partnership', 'maps', 'content'
        ))
        """
    )
