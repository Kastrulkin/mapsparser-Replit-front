"""add creator promotion workspace

Revision ID: 20260820_001
Revises: 20260816_001
Create Date: 2026-08-20 18:00:00.000000
"""

from alembic import op


revision = "20260820_001"
down_revision = "20260816_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE lead_workstreams DROP CONSTRAINT IF EXISTS ck_lead_workstreams_type")
    op.execute("ALTER TABLE lead_workstreams DROP CONSTRAINT IF EXISTS ck_lead_workstreams_client")
    op.execute(
        """
        ALTER TABLE lead_workstreams
        ADD CONSTRAINT ck_lead_workstreams_type
            CHECK (workstream_type IN ('localos_sales', 'client_partnership', 'creator_collaboration')),
        ADD CONSTRAINT ck_lead_workstreams_client
            CHECK (
                (workstream_type = 'localos_sales' AND client_business_id IS NULL)
                OR (workstream_type IN ('client_partnership', 'creator_collaboration') AND client_business_id IS NOT NULL)
            )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_lead_workstreams_creator
        ON lead_workstreams (lead_id, client_business_id)
        WHERE workstream_type = 'creator_collaboration'
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_profiles (
            id UUID PRIMARY KEY,
            profile_type TEXT NOT NULL DEFAULT 'author',
            display_name TEXT NOT NULL,
            description TEXT,
            primary_city TEXT,
            primary_area TEXT,
            languages_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            topics_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            verification_status TEXT NOT NULL DEFAULT 'candidate',
            brand_safety_status TEXT NOT NULL DEFAULT 'unknown',
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_profiles_type CHECK (
                profile_type IN ('author', 'channel', 'community', 'media', 'aggregator')
            ),
            CONSTRAINT ck_creator_profiles_verification CHECK (
                verification_status IN ('candidate', 'observed', 'verified', 'rejected')
            ),
            CONSTRAINT ck_creator_profiles_brand_safety CHECK (
                brand_safety_status IN ('unknown', 'clear', 'review', 'blocked')
            )
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_channels (
            id UUID PRIMARY KEY,
            creator_profile_id UUID NOT NULL REFERENCES creator_profiles(id) ON DELETE CASCADE,
            platform TEXT NOT NULL,
            canonical_url TEXT NOT NULL,
            username TEXT,
            knowledge_source_id UUID REFERENCES knowledge_sources(id) ON DELETE SET NULL,
            contactability TEXT NOT NULL DEFAULT 'unknown',
            public_metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            last_observed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_channels_platform CHECK (
                platform IN ('telegram', 'vk', 'website', 'instagram', 'tiktok', 'youtube', 'other')
            ),
            CONSTRAINT ck_creator_channels_contactability CHECK (
                contactability IN ('unknown', 'public_contact', 'advertising_contact', 'manual_only', 'not_contactable')
            ),
            UNIQUE (platform, canonical_url)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_channels_profile ON creator_channels(creator_profile_id, platform)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_channels_source ON creator_channels(knowledge_source_id)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_evidence (
            id UUID PRIMARY KEY,
            creator_profile_id UUID NOT NULL REFERENCES creator_profiles(id) ON DELETE CASCADE,
            evidence_type TEXT NOT NULL,
            source_url TEXT,
            source_id UUID REFERENCES knowledge_sources(id) ON DELETE SET NULL,
            summary_text TEXT NOT NULL,
            confidence NUMERIC(5, 4) NOT NULL DEFAULT 0,
            observed_at TIMESTAMPTZ,
            stale_after TIMESTAMPTZ,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_evidence_confidence CHECK (confidence BETWEEN 0 AND 1)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_evidence_profile ON creator_evidence(creator_profile_id, evidence_type, observed_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_commercial_profiles (
            id UUID PRIMARY KEY,
            creator_profile_id UUID NOT NULL UNIQUE REFERENCES creator_profiles(id) ON DELETE CASCADE,
            formats_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            accepts_barter BOOLEAN,
            price_min NUMERIC,
            price_max NUMERIC,
            currency TEXT NOT NULL DEFAULT 'RUB',
            media_kit_url TEXT,
            preferred_contact TEXT,
            availability_text TEXT,
            confirmation_status TEXT NOT NULL DEFAULT 'observed',
            confirmed_at TIMESTAMPTZ,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_commercial_confirmation CHECK (
                confirmation_status IN ('observed', 'creator_confirmed', 'business_confirmed', 'expired')
            )
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_search_jobs (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            status TEXT NOT NULL DEFAULT 'created',
            phase TEXT NOT NULL DEFAULT 'setup',
            brief_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            progress_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            scoring_version TEXT NOT NULL DEFAULT 'creator-fit-v1',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_search_status CHECK (
                status IN ('created', 'searching', 'enriching', 'checking', 'ready', 'partial', 'failed')
            )
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_search_business ON creator_search_jobs(business_id, created_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_search_results (
            id UUID PRIMARY KEY,
            search_job_id UUID NOT NULL REFERENCES creator_search_jobs(id) ON DELETE CASCADE,
            creator_profile_id UUID NOT NULL REFERENCES creator_profiles(id) ON DELETE CASCADE,
            score INTEGER NOT NULL DEFAULT 0,
            score_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            reasons_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            gates_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            result_group TEXT NOT NULL DEFAULT 'needs_review',
            shortlist_status TEXT NOT NULL DEFAULT 'suggested',
            scoring_version TEXT NOT NULL DEFAULT 'creator-fit-v1',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_search_score CHECK (score BETWEEN 0 AND 100),
            CONSTRAINT ck_creator_search_shortlist CHECK (
                shortlist_status IN ('suggested', 'shortlisted', 'rejected')
            ),
            UNIQUE (search_job_id, creator_profile_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_search_results_rank ON creator_search_results(search_job_id, score DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_campaigns (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            search_job_id UUID REFERENCES creator_search_jobs(id) ON DELETE SET NULL,
            title TEXT NOT NULL,
            goal TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            sender_mode TEXT NOT NULL DEFAULT 'partner_business',
            audience_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            geography_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            formats_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            offer_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            budget_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            period_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            constraints_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            terms_version INTEGER NOT NULL DEFAULT 1,
            approved_terms_version INTEGER,
            approved_at TIMESTAMPTZ,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_campaign_status CHECK (
                status IN ('draft', 'needs_review', 'approved', 'active', 'paused', 'completed', 'cancelled')
            ),
            CONSTRAINT ck_creator_campaign_sender CHECK (
                sender_mode IN ('partner_business', 'localos_for_partner')
            )
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_campaign_business ON creator_campaigns(business_id, status, updated_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_campaign_candidates (
            id UUID PRIMARY KEY,
            campaign_id UUID NOT NULL REFERENCES creator_campaigns(id) ON DELETE CASCADE,
            creator_profile_id UUID NOT NULL REFERENCES creator_profiles(id) ON DELETE CASCADE,
            search_result_id UUID REFERENCES creator_search_results(id) ON DELETE SET NULL,
            lead_id TEXT REFERENCES prospectingleads(id) ON DELETE SET NULL,
            workstream_id UUID REFERENCES lead_workstreams(id) ON DELETE SET NULL,
            outreach_campaign_id UUID,
            score_snapshot_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            selection_reason TEXT,
            status TEXT NOT NULL DEFAULT 'shortlisted',
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_candidate_status CHECK (
                status IN ('shortlisted', 'invitation_ready', 'invited', 'replied', 'negotiating', 'agreed', 'declined', 'no_reply', 'removed')
            ),
            UNIQUE (campaign_id, creator_profile_id)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_candidates_campaign ON creator_campaign_candidates(campaign_id, status)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_collaborations (
            id UUID PRIMARY KEY,
            campaign_id UUID NOT NULL REFERENCES creator_campaigns(id) ON DELETE CASCADE,
            campaign_candidate_id UUID NOT NULL UNIQUE REFERENCES creator_campaign_candidates(id) ON DELETE CASCADE,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            creator_profile_id UUID NOT NULL REFERENCES creator_profiles(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'draft',
            agreed_terms_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            terms_version INTEGER NOT NULL DEFAULT 1,
            approved_terms_version INTEGER,
            scheduled_visit_at TIMESTAMPTZ,
            owner_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            public_token_hash TEXT,
            public_token_expires_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_collaboration_status CHECK (
                status IN ('draft', 'invited', 'replied', 'negotiating', 'agreed', 'visit_scheduled', 'awaiting_content', 'published', 'measuring', 'completed', 'declined', 'no_reply', 'rescheduled', 'overdue', 'disputed', 'stopped')
            )
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_collab_business ON creator_collaborations(business_id, status, updated_at DESC)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_deliverables (
            id UUID PRIMARY KEY,
            collaboration_id UUID NOT NULL REFERENCES creator_collaborations(id) ON DELETE CASCADE,
            platform TEXT NOT NULL,
            deliverable_type TEXT NOT NULL,
            due_at TIMESTAMPTZ,
            required_elements_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            publication_url TEXT,
            proof_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            verification_status TEXT NOT NULL DEFAULT 'expected',
            usage_rights_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            published_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_deliverable_verification CHECK (
                verification_status IN ('expected', 'submitted', 'verified', 'rejected', 'overdue')
            )
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_deliverables_collab ON creator_deliverables(collaboration_id, due_at)")

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_placement_metrics (
            id UUID PRIMARY KEY,
            deliverable_id UUID NOT NULL REFERENCES creator_deliverables(id) ON DELETE CASCADE,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            metric_date DATE NOT NULL,
            views INTEGER NOT NULL DEFAULT 0,
            reach INTEGER NOT NULL DEFAULT 0,
            reactions INTEGER NOT NULL DEFAULT 0,
            comments INTEGER NOT NULL DEFAULT 0,
            saves INTEGER NOT NULL DEFAULT 0,
            clicks INTEGER NOT NULL DEFAULT 0,
            promo_uses INTEGER NOT NULL DEFAULT 0,
            inquiries INTEGER NOT NULL DEFAULT 0,
            bookings INTEGER NOT NULL DEFAULT 0,
            confirmed_revenue NUMERIC,
            placement_cost NUMERIC,
            source_type TEXT NOT NULL DEFAULT 'manual',
            confidence NUMERIC(5, 4) NOT NULL DEFAULT 0,
            raw_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_metrics_confidence CHECK (confidence BETWEEN 0 AND 1),
            CONSTRAINT ck_creator_metrics_source CHECK (
                source_type IN ('public', 'creator_reported', 'business_reported', 'utm', 'promo_code', 'website_tracker', 'crm_import', 'manual')
            ),
            UNIQUE (deliverable_id, metric_date, source_type)
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_creator_metrics_business ON creator_placement_metrics(business_id, metric_date DESC)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS creator_placement_metrics")
    op.execute("DROP TABLE IF EXISTS creator_deliverables")
    op.execute("DROP TABLE IF EXISTS creator_collaborations")
    op.execute("DROP TABLE IF EXISTS creator_campaign_candidates")
    op.execute("DROP TABLE IF EXISTS creator_campaigns")
    op.execute("DROP TABLE IF EXISTS creator_search_results")
    op.execute("DROP TABLE IF EXISTS creator_search_jobs")
    op.execute("DROP TABLE IF EXISTS creator_commercial_profiles")
    op.execute("DROP TABLE IF EXISTS creator_evidence")
    op.execute("DROP TABLE IF EXISTS creator_channels")
    op.execute("DROP TABLE IF EXISTS creator_profiles")
    op.execute("DROP INDEX IF EXISTS uq_lead_workstreams_creator")
    op.execute("ALTER TABLE lead_workstreams DROP CONSTRAINT IF EXISTS ck_lead_workstreams_type")
    op.execute("ALTER TABLE lead_workstreams DROP CONSTRAINT IF EXISTS ck_lead_workstreams_client")
    op.execute(
        """
        ALTER TABLE lead_workstreams
        ADD CONSTRAINT ck_lead_workstreams_type
            CHECK (workstream_type IN ('localos_sales', 'client_partnership')),
        ADD CONSTRAINT ck_lead_workstreams_client
            CHECK (
                (workstream_type = 'localos_sales' AND client_business_id IS NULL)
                OR (workstream_type = 'client_partnership' AND client_business_id IS NOT NULL)
            )
        """
    )
