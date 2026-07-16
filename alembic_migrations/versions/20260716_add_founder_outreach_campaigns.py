"""add founder-led multichannel outreach campaigns

Revision ID: 20260716_005
Revises: 20260716_004
Create Date: 2026-07-16 22:40:00.000000
"""

from alembic import op


revision = "20260716_005"
down_revision = "20260716_004"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_account_permissions (
            account_id TEXT PRIMARY KEY REFERENCES externalbusinessaccounts(id) ON DELETE CASCADE,
            radar_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            outreach_enabled BOOLEAN NOT NULL DEFAULT FALSE,
            radar_consented_at TIMESTAMPTZ,
            outreach_consented_at TIMESTAMPTZ,
            changed_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        INSERT INTO telegram_account_permissions (
            account_id, radar_enabled, outreach_enabled, radar_consented_at, created_at, updated_at
        )
        SELECT id, TRUE, FALSE, NOW(), NOW(), NOW()
        FROM externalbusinessaccounts
        WHERE source = 'telegram_app'
        ON CONFLICT (account_id) DO NOTHING
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegram_account_permission_events (
            id UUID PRIMARY KEY,
            account_id TEXT REFERENCES externalbusinessaccounts(id) ON DELETE SET NULL,
            business_id TEXT REFERENCES businesses(id) ON DELETE SET NULL,
            radar_enabled BOOLEAN NOT NULL,
            outreach_enabled BOOLEAN NOT NULL,
            reason_code TEXT NOT NULL,
            changed_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telegram_permission_events_account
        ON telegram_account_permission_events(account_id, created_at DESC)
        """
    )
    op.execute(
        """
        ALTER TABLE outreach_sender_profiles
        ADD COLUMN IF NOT EXISTS outreach_context_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        ADD COLUMN IF NOT EXISTS allowed_offers_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        ADD COLUMN IF NOT EXISTS forbidden_claims_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        ADD COLUMN IF NOT EXISTS voice_examples_json JSONB NOT NULL DEFAULT '[]'::jsonb
        """
    )
    op.execute(
        """
        ALTER TABLE lead_workstream_research
        ADD COLUMN IF NOT EXISTS evidence_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        ADD COLUMN IF NOT EXISTS personalization_candidates_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        ADD COLUMN IF NOT EXISTS selected_personalization_id TEXT
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_sender_accounts (
            id UUID PRIMARY KEY,
            scope_type TEXT NOT NULL,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            owner_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            channel TEXT NOT NULL,
            external_account_id TEXT REFERENCES externalbusinessaccounts(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'connected',
            settings_path TEXT,
            capabilities_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_outreach_sender_account_scope CHECK (scope_type IN ('platform', 'business')),
            CONSTRAINT ck_outreach_sender_account_channel CHECK (
                channel IN ('telegram', 'email', 'whatsapp', 'max', 'vk', 'manual')
            ),
            CONSTRAINT ck_outreach_sender_account_status CHECK (
                status IN ('connected', 'attention', 'disabled')
            ),
            CONSTRAINT ck_outreach_sender_account_owner CHECK (
                (scope_type = 'business' AND business_id IS NOT NULL)
                OR (scope_type = 'platform' AND business_id IS NULL)
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_outreach_sender_account_binding
        ON outreach_sender_accounts(
            scope_type, COALESCE(business_id, ''), channel, COALESCE(external_account_id, '')
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_campaigns (
            id UUID PRIMARY KEY,
            workstream_id UUID NOT NULL REFERENCES lead_workstreams(id) ON DELETE CASCADE,
            lead_id TEXT NOT NULL REFERENCES prospectingleads(id) ON DELETE CASCADE,
            scope_type TEXT NOT NULL,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            sender_profile_id UUID REFERENCES outreach_sender_profiles(id) ON DELETE SET NULL,
            version INTEGER NOT NULL DEFAULT 1,
            status TEXT NOT NULL DEFAULT 'draft',
            policy_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            stop_reason TEXT,
            approved_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            approved_at TIMESTAMPTZ,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_outreach_campaign_scope CHECK (scope_type IN ('platform', 'business')),
            CONSTRAINT ck_outreach_campaign_status CHECK (
                status IN ('draft', 'approved', 'active', 'paused', 'completed', 'cancelled', 'stopped')
            )
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_outreach_campaign_version
        ON outreach_campaigns(workstream_id, version)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_campaign_touches (
            id UUID PRIMARY KEY,
            campaign_id UUID NOT NULL REFERENCES outreach_campaigns(id) ON DELETE CASCADE,
            draft_id TEXT REFERENCES outreachmessagedrafts(id) ON DELETE SET NULL,
            sequence_index INTEGER NOT NULL,
            channel TEXT NOT NULL,
            contact_point_id UUID REFERENCES lead_contact_points(id) ON DELETE SET NULL,
            sender_account_id UUID REFERENCES outreach_sender_accounts(id) ON DELETE SET NULL,
            angle_type TEXT NOT NULL,
            scheduled_at TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL DEFAULT 'draft',
            subject TEXT,
            generated_text TEXT NOT NULL,
            approved_text TEXT,
            message_brief_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            quality_gate_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            delivery_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT uq_outreach_campaign_touch_index UNIQUE (campaign_id, sequence_index),
            CONSTRAINT ck_outreach_campaign_touch_channel CHECK (
                channel IN ('telegram', 'email', 'whatsapp', 'max', 'vk', 'manual')
            ),
            CONSTRAINT ck_outreach_campaign_touch_status CHECK (
                status IN ('draft', 'approved', 'scheduled', 'queued', 'sent', 'delivered', 'manual', 'paused', 'cancelled', 'failed', 'skipped')
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreach_campaign_touches_due
        ON outreach_campaign_touches(status, scheduled_at)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_campaign_events (
            id UUID PRIMARY KEY,
            campaign_id UUID NOT NULL REFERENCES outreach_campaigns(id) ON DELETE CASCADE,
            touch_id UUID REFERENCES outreach_campaign_touches(id) ON DELETE SET NULL,
            event_type TEXT NOT NULL,
            reason_code TEXT,
            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            actor_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreach_campaign_events_journal
        ON outreach_campaign_events(campaign_id, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_suppressions (
            id UUID PRIMARY KEY,
            lead_id TEXT NOT NULL REFERENCES prospectingleads(id) ON DELETE CASCADE,
            workstream_id UUID REFERENCES lead_workstreams(id) ON DELETE CASCADE,
            contact_point_id UUID REFERENCES lead_contact_points(id) ON DELETE SET NULL,
            channel TEXT,
            reason_code TEXT NOT NULL,
            source TEXT NOT NULL DEFAULT 'manual',
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            expires_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreach_suppressions_active
        ON outreach_suppressions(lead_id, workstream_id, expires_at)
        """
    )
    op.execute(
        """
        ALTER TABLE outreachsendqueue
        ADD COLUMN IF NOT EXISTS sender_account_id UUID REFERENCES outreach_sender_accounts(id) ON DELETE SET NULL,
        ADD COLUMN IF NOT EXISTS campaign_touch_id UUID REFERENCES outreach_campaign_touches(id) ON DELETE SET NULL,
        ADD COLUMN IF NOT EXISTS scheduled_at TIMESTAMPTZ
        """
    )


def downgrade():
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS scheduled_at")
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS campaign_touch_id")
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS sender_account_id")
    op.execute("DROP INDEX IF EXISTS idx_outreach_suppressions_active")
    op.execute("DROP TABLE IF EXISTS outreach_suppressions")
    op.execute("DROP INDEX IF EXISTS idx_outreach_campaign_events_journal")
    op.execute("DROP TABLE IF EXISTS outreach_campaign_events")
    op.execute("DROP INDEX IF EXISTS idx_outreach_campaign_touches_due")
    op.execute("DROP TABLE IF EXISTS outreach_campaign_touches")
    op.execute("DROP INDEX IF EXISTS uq_outreach_campaign_version")
    op.execute("DROP TABLE IF EXISTS outreach_campaigns")
    op.execute("DROP INDEX IF EXISTS uq_outreach_sender_account_binding")
    op.execute("DROP TABLE IF EXISTS outreach_sender_accounts")
    op.execute("ALTER TABLE lead_workstream_research DROP COLUMN IF EXISTS selected_personalization_id")
    op.execute("ALTER TABLE lead_workstream_research DROP COLUMN IF EXISTS personalization_candidates_json")
    op.execute("ALTER TABLE lead_workstream_research DROP COLUMN IF EXISTS evidence_json")
    op.execute("ALTER TABLE outreach_sender_profiles DROP COLUMN IF EXISTS voice_examples_json")
    op.execute("ALTER TABLE outreach_sender_profiles DROP COLUMN IF EXISTS forbidden_claims_json")
    op.execute("ALTER TABLE outreach_sender_profiles DROP COLUMN IF EXISTS allowed_offers_json")
    op.execute("ALTER TABLE outreach_sender_profiles DROP COLUMN IF EXISTS outreach_context_json")
    op.execute("DROP INDEX IF EXISTS idx_telegram_permission_events_account")
    op.execute("DROP TABLE IF EXISTS telegram_account_permission_events")
    op.execute("DROP TABLE IF EXISTS telegram_account_permissions")
