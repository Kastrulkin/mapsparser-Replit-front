"""add outreach v2 partnership intelligence

Revision ID: 20260722_003
Revises: 20260722_002
Create Date: 2026-07-22 15:30:00.000000
"""

from alembic import op


revision = "20260722_003"
down_revision = "20260722_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE outreach_campaigns
        ADD COLUMN IF NOT EXISTS sender_mode TEXT,
        ADD COLUMN IF NOT EXISTS selected_offer_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        ADD COLUMN IF NOT EXISTS trust_strategy TEXT,
        ADD COLUMN IF NOT EXISTS decision_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        ADD COLUMN IF NOT EXISTS room_id UUID REFERENCES sales_rooms(id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        UPDATE outreach_campaigns campaign
        SET sender_mode = COALESCE(
            NULLIF(campaign.policy_json->>'sender_mode', ''),
            CASE
                WHEN workstream.workstream_type = 'localos_sales' THEN 'localos'
                ELSE 'partner_business'
            END
        )
        FROM lead_workstreams workstream
        WHERE workstream.id = campaign.workstream_id
          AND campaign.sender_mode IS NULL
        """
    )
    op.execute("ALTER TABLE outreach_campaigns ALTER COLUMN sender_mode SET NOT NULL")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_outreach_campaign_sender_mode'
            ) THEN
                ALTER TABLE outreach_campaigns
                ADD CONSTRAINT ck_outreach_campaign_sender_mode CHECK (
                    sender_mode IN ('localos', 'partner_business', 'localos_for_partner')
                );
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_outreach_campaign_trust_strategy'
            ) THEN
                ALTER TABLE outreach_campaigns
                ADD CONSTRAINT ck_outreach_campaign_trust_strategy CHECK (
                    trust_strategy IS NULL OR trust_strategy IN (
                        'founder_story', 'business_reputation', 'matching_authority',
                        'case_study', 'referral', 'neighbour_context'
                    )
                );
            END IF;
        END $$
        """
    )
    op.execute(
        """
        ALTER TABLE lead_workstream_research
        ADD COLUMN IF NOT EXISTS outreach_decision_json JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute("ALTER TABLE outreach_learning_events DROP CONSTRAINT IF EXISTS ck_outreach_learning_outcome")
    op.execute(
        """
        ALTER TABLE outreach_learning_events
        ADD CONSTRAINT ck_outreach_learning_outcome CHECK (
            outcome_type IN (
                'sent', 'delivered', 'delivery_failed', 'replied',
                'positive_reply', 'question', 'hard_no', 'unsubscribe',
                'complaint', 'meeting_booked', 'converted', 'no_reply',
                'interested', 'call_planned', 'contacts_exchanged',
                'pilot_agreed', 'campaign_launched', 'joint_project',
                'recurring_partnership', 'not_relevant', 'lost'
            )
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_relationship_states (
            id UUID PRIMARY KEY,
            workstream_id UUID NOT NULL UNIQUE REFERENCES lead_workstreams(id) ON DELETE CASCADE,
            lead_id TEXT NOT NULL REFERENCES prospectingleads(id) ON DELETE CASCADE,
            scope_type TEXT NOT NULL,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            preferred_channel TEXT,
            follow_up_after TIMESTAMPTZ,
            do_not_call BOOLEAN NOT NULL DEFAULT FALSE,
            interests_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            summary TEXT,
            open_questions_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            next_step TEXT,
            negotiation_stage TEXT NOT NULL DEFAULT 'new',
            proposed_updates_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            provenance_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            confidence NUMERIC(4,3) NOT NULL DEFAULT 0,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_lead_relationship_scope CHECK (scope_type IN ('platform', 'business')),
            CONSTRAINT ck_lead_relationship_confidence CHECK (confidence BETWEEN 0 AND 1)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_relationship_follow_up
        ON lead_relationship_states(follow_up_after, negotiation_stage)
        """
    )
    op.execute(
        """
        ALTER TABLE sales_rooms
        ADD COLUMN IF NOT EXISTS workstream_id UUID REFERENCES lead_workstreams(id) ON DELETE SET NULL,
        ADD COLUMN IF NOT EXISTS campaign_id UUID REFERENCES outreach_campaigns(id) ON DELETE SET NULL,
        ADD COLUMN IF NOT EXISTS visibility TEXT
        """
    )
    op.execute("UPDATE sales_rooms SET visibility = 'shared' WHERE visibility IS NULL")
    op.execute("ALTER TABLE sales_rooms ALTER COLUMN visibility SET DEFAULT 'private'")
    op.execute("ALTER TABLE sales_rooms ALTER COLUMN visibility SET NOT NULL")
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint
                WHERE conname = 'ck_sales_rooms_visibility'
            ) THEN
                ALTER TABLE sales_rooms
                ADD CONSTRAINT ck_sales_rooms_visibility CHECK (
                    visibility IN ('private', 'ready_to_share', 'shared', 'revoked')
                );
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS sales_room_messages (
            id UUID PRIMARY KEY,
            room_id UUID NOT NULL REFERENCES sales_rooms(id) ON DELETE CASCADE,
            author_type TEXT NOT NULL DEFAULT 'visitor',
            author_name TEXT,
            author_contact TEXT,
            body_text TEXT,
            attachments_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        ALTER TABLE sales_room_messages
        ADD COLUMN IF NOT EXISTS direction TEXT NOT NULL DEFAULT 'room',
        ADD COLUMN IF NOT EXISTS source_channel TEXT,
        ADD COLUMN IF NOT EXISTS provider_event_id TEXT,
        ADD COLUMN IF NOT EXISTS campaign_id UUID REFERENCES outreach_campaigns(id) ON DELETE SET NULL,
        ADD COLUMN IF NOT EXISTS campaign_touch_id UUID REFERENCES outreach_campaign_touches(id) ON DELETE SET NULL,
        ADD COLUMN IF NOT EXISTS delivery_status TEXT NOT NULL DEFAULT 'recorded',
        ADD COLUMN IF NOT EXISTS occurred_at TIMESTAMPTZ
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_sales_room_message_provider_event
        ON sales_room_messages(source_channel, provider_event_id)
        WHERE provider_event_id IS NOT NULL
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_sales_room_message_provider_event")
    op.execute("ALTER TABLE sales_room_messages DROP COLUMN IF EXISTS occurred_at")
    op.execute("ALTER TABLE sales_room_messages DROP COLUMN IF EXISTS delivery_status")
    op.execute("ALTER TABLE sales_room_messages DROP COLUMN IF EXISTS campaign_touch_id")
    op.execute("ALTER TABLE sales_room_messages DROP COLUMN IF EXISTS campaign_id")
    op.execute("ALTER TABLE sales_room_messages DROP COLUMN IF EXISTS provider_event_id")
    op.execute("ALTER TABLE sales_room_messages DROP COLUMN IF EXISTS source_channel")
    op.execute("ALTER TABLE sales_room_messages DROP COLUMN IF EXISTS direction")
    op.execute("ALTER TABLE sales_rooms DROP CONSTRAINT IF EXISTS ck_sales_rooms_visibility")
    op.execute("ALTER TABLE sales_rooms DROP COLUMN IF EXISTS visibility")
    op.execute("ALTER TABLE sales_rooms DROP COLUMN IF EXISTS campaign_id")
    op.execute("DROP INDEX IF EXISTS idx_lead_relationship_follow_up")
    op.execute("DROP TABLE IF EXISTS lead_relationship_states")
    op.execute("ALTER TABLE outreach_learning_events DROP CONSTRAINT IF EXISTS ck_outreach_learning_outcome")
    op.execute(
        """
        UPDATE outreach_learning_events
        SET outcome_type = CASE
            WHEN outcome_type IN ('interested', 'call_planned', 'contacts_exchanged', 'pilot_agreed')
                THEN 'positive_reply'
            WHEN outcome_type IN ('campaign_launched', 'joint_project', 'recurring_partnership')
                THEN 'converted'
            WHEN outcome_type IN ('not_relevant', 'lost') THEN 'hard_no'
            ELSE outcome_type
        END
        WHERE outcome_type IN (
            'interested', 'call_planned', 'contacts_exchanged', 'pilot_agreed',
            'campaign_launched', 'joint_project', 'recurring_partnership',
            'not_relevant', 'lost'
        )
        """
    )
    op.execute(
        """
        ALTER TABLE outreach_learning_events
        ADD CONSTRAINT ck_outreach_learning_outcome CHECK (
            outcome_type IN (
                'sent', 'delivered', 'delivery_failed', 'replied',
                'positive_reply', 'question', 'hard_no', 'unsubscribe',
                'complaint', 'meeting_booked', 'converted', 'no_reply'
            )
        )
        """
    )
    op.execute("ALTER TABLE lead_workstream_research DROP COLUMN IF EXISTS outreach_decision_json")
    op.execute("ALTER TABLE outreach_campaigns DROP CONSTRAINT IF EXISTS ck_outreach_campaign_trust_strategy")
    op.execute("ALTER TABLE outreach_campaigns DROP CONSTRAINT IF EXISTS ck_outreach_campaign_sender_mode")
    op.execute("ALTER TABLE outreach_campaigns DROP COLUMN IF EXISTS room_id")
    op.execute("ALTER TABLE outreach_campaigns DROP COLUMN IF EXISTS decision_snapshot_json")
    op.execute("ALTER TABLE outreach_campaigns DROP COLUMN IF EXISTS trust_strategy")
    op.execute("ALTER TABLE outreach_campaigns DROP COLUMN IF EXISTS selected_offer_json")
    op.execute("ALTER TABLE outreach_campaigns DROP COLUMN IF EXISTS sender_mode")
