"""add contact intelligence and grounded outreach preparation

Revision ID: 20260715_002
Revises: 20260715_001
Create Date: 2026-07-15 16:00:00.000000
"""

from alembic import op


revision = "20260715_002"
down_revision = "20260715_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_contact_points (
            id UUID PRIMARY KEY,
            lead_id TEXT NOT NULL REFERENCES prospectingleads(id) ON DELETE CASCADE,
            contact_type TEXT NOT NULL,
            value TEXT NOT NULL,
            normalized_value TEXT NOT NULL,
            owner_type TEXT NOT NULL DEFAULT 'company',
            person_name TEXT,
            role_title TEXT,
            source_url TEXT,
            source_type TEXT NOT NULL DEFAULT 'legacy',
            provider TEXT NOT NULL DEFAULT 'public',
            confidence NUMERIC(5, 4) NOT NULL DEFAULT 0,
            verification_status TEXT NOT NULL DEFAULT 'found',
            observed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            verified_at TIMESTAMPTZ,
            stale_after TIMESTAMPTZ,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_lead_contact_points_type CHECK (
                contact_type IN (
                    'phone', 'email', 'telegram', 'whatsapp', 'vk', 'instagram',
                    'max', 'website_form', 'website', 'other'
                )
            ),
            CONSTRAINT ck_lead_contact_points_owner CHECK (owner_type IN ('company', 'person')),
            CONSTRAINT ck_lead_contact_points_confidence CHECK (confidence BETWEEN 0 AND 1),
            CONSTRAINT ck_lead_contact_points_verification CHECK (
                verification_status IN (
                    'found', 'valid_format', 'confirmed_source', 'verified',
                    'accept_all', 'unknown', 'invalid', 'stale'
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_lead_contact_points_value
        ON lead_contact_points(lead_id, contact_type, normalized_value)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_contact_points_lead_quality
        ON lead_contact_points(lead_id, verification_status, confidence DESC, updated_at DESC)
        """
    )
    op.execute(
        """
        ALTER TABLE lead_workstreams
        ADD COLUMN IF NOT EXISTS selected_contact_point_id UUID
            REFERENCES lead_contact_points(id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_sender_profiles (
            id UUID PRIMARY KEY,
            workstream_type TEXT NOT NULL,
            client_business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            display_name TEXT NOT NULL,
            role_title TEXT NOT NULL,
            company_name TEXT NOT NULL,
            competence_story TEXT,
            proof_points_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            verified_cases_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            signature_text TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            confirmed_at TIMESTAMPTZ,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_outreach_sender_profiles_type CHECK (
                workstream_type IN ('localos_sales', 'client_partnership')
            ),
            CONSTRAINT ck_outreach_sender_profiles_client CHECK (
                (workstream_type = 'localos_sales' AND client_business_id IS NULL)
                OR (workstream_type = 'client_partnership' AND client_business_id IS NOT NULL)
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_outreach_sender_profiles_active
        ON outreach_sender_profiles(workstream_type, COALESCE(client_business_id, ''))
        WHERE is_active = TRUE
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_enrichment_jobs (
            id UUID PRIMARY KEY,
            workstream_id UUID NOT NULL REFERENCES lead_workstreams(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'queued',
            current_phase TEXT NOT NULL DEFAULT 'collecting',
            attempt_count INTEGER NOT NULL DEFAULT 0,
            max_attempts INTEGER NOT NULL DEFAULT 2,
            next_attempt_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            started_at TIMESTAMPTZ,
            completed_at TIMESTAMPTZ,
            error_code TEXT,
            error_message TEXT,
            hunter_requests_used INTEGER NOT NULL DEFAULT 0,
            allow_paid_enrichment BOOLEAN NOT NULL DEFAULT FALSE,
            message_brief_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            readiness_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_lead_enrichment_jobs_status CHECK (
                status IN (
                    'queued', 'collecting', 'verifying', 'researching', 'drafting',
                    'ready', 'needs_input', 'retry_wait', 'failed'
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_lead_enrichment_jobs_active
        ON lead_enrichment_jobs(workstream_id)
        WHERE status IN (
            'queued', 'collecting', 'verifying', 'researching', 'drafting', 'retry_wait'
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_enrichment_jobs_queue
        ON lead_enrichment_jobs(status, next_attempt_at, created_at)
        """
    )
    op.execute(
        """
        ALTER TABLE lead_workstream_research
        ADD COLUMN IF NOT EXISTS message_brief_json JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute(
        """
        ALTER TABLE lead_workstream_research
        ADD COLUMN IF NOT EXISTS message_readiness_json JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute(
        """
        ALTER TABLE outreachmessagedrafts
        ADD COLUMN IF NOT EXISTS research_id UUID REFERENCES lead_workstream_research(id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        ALTER TABLE outreachmessagedrafts
        ADD COLUMN IF NOT EXISTS contact_point_id UUID REFERENCES lead_contact_points(id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        ALTER TABLE outreachmessagedrafts
        ADD COLUMN IF NOT EXISTS sender_profile_id UUID REFERENCES outreach_sender_profiles(id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        ALTER TABLE outreachmessagedrafts
        ADD COLUMN IF NOT EXISTS enrichment_job_id UUID REFERENCES lead_enrichment_jobs(id) ON DELETE SET NULL
        """
    )
    op.execute(
        """
        ALTER TABLE outreachmessagedrafts
        ADD COLUMN IF NOT EXISTS message_brief_json JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute(
        """
        ALTER TABLE outreachmessagedrafts
        ADD COLUMN IF NOT EXISTS quality_gate_json JSONB NOT NULL DEFAULT '{}'::jsonb
        """
    )
    op.execute(
        """
        ALTER TABLE outreachmessagedrafts
        ADD COLUMN IF NOT EXISTS include_room_link BOOLEAN NOT NULL DEFAULT FALSE
        """
    )


def downgrade():
    op.execute("ALTER TABLE outreachmessagedrafts DROP COLUMN IF EXISTS include_room_link")
    op.execute("ALTER TABLE outreachmessagedrafts DROP COLUMN IF EXISTS quality_gate_json")
    op.execute("ALTER TABLE outreachmessagedrafts DROP COLUMN IF EXISTS message_brief_json")
    op.execute("ALTER TABLE outreachmessagedrafts DROP COLUMN IF EXISTS enrichment_job_id")
    op.execute("ALTER TABLE outreachmessagedrafts DROP COLUMN IF EXISTS sender_profile_id")
    op.execute("ALTER TABLE outreachmessagedrafts DROP COLUMN IF EXISTS contact_point_id")
    op.execute("ALTER TABLE outreachmessagedrafts DROP COLUMN IF EXISTS research_id")
    op.execute("ALTER TABLE lead_workstream_research DROP COLUMN IF EXISTS message_readiness_json")
    op.execute("ALTER TABLE lead_workstream_research DROP COLUMN IF EXISTS message_brief_json")
    op.execute("DROP INDEX IF EXISTS idx_lead_enrichment_jobs_queue")
    op.execute("DROP INDEX IF EXISTS uq_lead_enrichment_jobs_active")
    op.execute("DROP TABLE IF EXISTS lead_enrichment_jobs")
    op.execute("DROP INDEX IF EXISTS uq_outreach_sender_profiles_active")
    op.execute("DROP TABLE IF EXISTS outreach_sender_profiles")
    op.execute("ALTER TABLE lead_workstreams DROP COLUMN IF EXISTS selected_contact_point_id")
    op.execute("DROP INDEX IF EXISTS idx_lead_contact_points_lead_quality")
    op.execute("DROP INDEX IF EXISTS uq_lead_contact_points_value")
    op.execute("DROP TABLE IF EXISTS lead_contact_points")
