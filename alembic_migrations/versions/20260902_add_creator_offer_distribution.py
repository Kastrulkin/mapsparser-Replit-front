"""add creator offer distribution

Revision ID: 20260902_002
Revises: 20260902_001
Create Date: 2026-09-02
"""

from alembic import op


revision = "20260902_002"
down_revision = "20260902_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_business_preferences (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            creator_profile_id UUID NOT NULL REFERENCES creator_profiles(id) ON DELETE CASCADE,
            disposition TEXT NOT NULL DEFAULT 'available',
            reason TEXT,
            updated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_business_disposition
                CHECK (disposition IN ('available', 'shortlisted', 'excluded')),
            UNIQUE (business_id, creator_profile_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_business_preferences "
        "ON creator_business_preferences(business_id, disposition, updated_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_offer_preferences (
            creator_profile_id UUID PRIMARY KEY REFERENCES creator_profiles(id) ON DELETE CASCADE,
            paused_until TIMESTAMPTZ,
            paused_indefinitely BOOLEAN NOT NULL DEFAULT FALSE,
            excluded_categories_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_offer_distribution_runs (
            id UUID PRIMARY KEY,
            campaign_id UUID NOT NULL REFERENCES creator_campaigns(id) ON DELETE CASCADE,
            terms_version INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            filters_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            counts_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            progress_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_offer_distribution_status
                CHECK (status IN ('queued', 'running', 'completed', 'failed')),
            UNIQUE (campaign_id, terms_version)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_offer_distribution_due "
        "ON creator_offer_distribution_runs(status, created_at)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_offer_recipients (
            id UUID PRIMARY KEY,
            campaign_id UUID NOT NULL REFERENCES creator_campaigns(id) ON DELETE CASCADE,
            distribution_run_id UUID REFERENCES creator_offer_distribution_runs(id) ON DELETE SET NULL,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            creator_profile_id UUID NOT NULL REFERENCES creator_profiles(id) ON DELETE CASCADE,
            collaboration_id UUID REFERENCES creator_collaborations(id) ON DELETE SET NULL,
            status TEXT NOT NULL DEFAULT 'pending_account',
            terms_version INTEGER NOT NULL,
            match_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            offer_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            response_text TEXT,
            responded_at TIMESTAMPTZ,
            selected_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_offer_recipient_status CHECK (
                status IN ('pending_account', 'available', 'interested', 'needs_details',
                           'declined', 'selected', 'not_selected', 'expired')
            ),
            UNIQUE (campaign_id, creator_profile_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_offer_recipient_profile "
        "ON creator_offer_recipients(creator_profile_id, status, updated_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_offer_recipient_campaign "
        "ON creator_offer_recipients(campaign_id, status)"
    )
    op.execute(
        """
        ALTER TABLE creator_campaigns
            ADD COLUMN IF NOT EXISTS reviewed_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            ADD COLUMN IF NOT EXISTS reviewed_at TIMESTAMPTZ,
            ADD COLUMN IF NOT EXISTS distribution_locked_at TIMESTAMPTZ
        """
    )
    op.execute(
        """
        ALTER TABLE creator_offer_messages
            ADD COLUMN IF NOT EXISTS offer_recipient_id UUID
                REFERENCES creator_offer_recipients(id) ON DELETE CASCADE
        """
    )
    op.execute("ALTER TABLE creator_offer_messages ALTER COLUMN collaboration_id DROP NOT NULL")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_offer_messages_recipient "
        "ON creator_offer_messages(offer_recipient_id, created_at)"
    )
    op.execute(
        """
        ALTER TABLE creator_notification_outbox
            ADD COLUMN IF NOT EXISTS offer_recipient_id UUID
                REFERENCES creator_offer_recipients(id) ON DELETE CASCADE
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_notification_recipient "
        "ON creator_notification_outbox(offer_recipient_id, status)"
    )
    op.execute(
        """
        INSERT INTO creator_offer_recipients (
            id, campaign_id, business_id, creator_profile_id, collaboration_id,
            status, terms_version, match_snapshot_json, offer_snapshot_json,
            responded_at, selected_at, created_at, updated_at
        )
        SELECT
            gen_random_uuid(), collaboration.campaign_id, collaboration.business_id,
            collaboration.creator_profile_id, collaboration.id,
            CASE
                WHEN collaboration.status IN ('declined', 'stopped', 'no_reply') THEN 'declined'
                WHEN collaboration.status IN ('draft', 'invited') THEN 'available'
                WHEN collaboration.status IN ('replied', 'negotiating') THEN 'interested'
                ELSE 'selected'
            END,
            collaboration.terms_version,
            jsonb_build_object('backfilled', TRUE),
            jsonb_build_object(
                'title', campaign.title,
                'goal', campaign.goal,
                'offer', campaign.offer_json,
                'period', campaign.period_json,
                'formats', campaign.formats_json,
                'constraints', campaign.constraints_json,
                'business_name', business.name,
                'city', business.city,
                'address', business.address
            ),
            CASE WHEN collaboration.status IN ('replied', 'negotiating', 'declined')
                 THEN collaboration.updated_at END,
            CASE WHEN collaboration.status IN ('agreed', 'visit_scheduled', 'awaiting_content',
                                                'published', 'measuring', 'completed')
                 THEN collaboration.updated_at END,
            collaboration.created_at,
            collaboration.updated_at
        FROM creator_collaborations collaboration
        JOIN creator_campaigns campaign ON campaign.id = collaboration.campaign_id
        JOIN businesses business ON business.id = collaboration.business_id
        WHERE collaboration.review_status = 'approved'
        ON CONFLICT (campaign_id, creator_profile_id) DO NOTHING
        """
    )


def downgrade():
    # Distribution records and author preferences are operational history.
    pass
