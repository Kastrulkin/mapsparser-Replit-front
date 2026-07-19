"""add outreach safety, inbound classification, sender health and learning

Revision ID: 20260717_001
Revises: 20260716_006
Create Date: 2026-07-17 12:00:00.000000
"""

from alembic import op


revision = "20260717_001"
down_revision = "20260716_006"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE lead_enrichment_jobs DROP CONSTRAINT IF EXISTS ck_lead_enrichment_jobs_status")
    op.execute(
        """
        ALTER TABLE lead_enrichment_jobs
        ADD CONSTRAINT ck_lead_enrichment_jobs_status CHECK (
            status IN (
                'queued', 'collecting', 'verifying', 'researching', 'drafting',
                'ready', 'needs_input', 'needs_contact', 'needs_evidence',
                'suppressed', 'retry_wait', 'failed'
            )
        )
        """
    )
    op.execute(
        """
        ALTER TABLE lead_workstreams
        ADD COLUMN IF NOT EXISTS lifecycle_status TEXT NOT NULL DEFAULT 'discovered',
        ADD COLUMN IF NOT EXISTS status_reason TEXT,
        ADD COLUMN IF NOT EXISTS next_step TEXT,
        ADD COLUMN IF NOT EXISTS state_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        """
    )
    op.execute(
        """
        UPDATE lead_workstreams
        SET lifecycle_status = CASE
            WHEN status IN ('replied', 'converted', 'closed_lost') THEN status
            WHEN status IN ('sent', 'waiting_reply', 'second_message_sent') THEN 'waiting_reply'
            WHEN status IN ('approved') THEN 'approved'
            WHEN status IN ('qualified', 'selected_for_outreach') THEN 'qualified'
            WHEN status IN ('not_relevant') THEN 'not_relevant'
            ELSE lifecycle_status
        END
        WHERE lifecycle_status = 'discovered'
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_lead_workstreams_lifecycle_status'
            ) THEN
                ALTER TABLE lead_workstreams
                ADD CONSTRAINT ck_lead_workstreams_lifecycle_status CHECK (
                    lifecycle_status IN (
                        'discovered', 'qualifying', 'not_relevant', 'qualified',
                        'enriching', 'needs_contact', 'needs_evidence', 'ready_for_draft',
                        'draft', 'needs_review', 'approved', 'campaign_active',
                        'waiting_reply', 'replied', 'converted', 'closed_lost',
                        'suppressed', 'needs_attention'
                    )
                );
            END IF;
        END $$
        """
    )

    op.execute(
        """
        ALTER TABLE outreach_sender_accounts
        ADD COLUMN IF NOT EXISTS health_status TEXT NOT NULL DEFAULT 'healthy',
        ADD COLUMN IF NOT EXISTS health_score SMALLINT NOT NULL DEFAULT 100,
        ADD COLUMN IF NOT EXISTS health_reason TEXT,
        ADD COLUMN IF NOT EXISTS health_metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        ADD COLUMN IF NOT EXISTS health_changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        ADD COLUMN IF NOT EXISTS last_health_event_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS sender_identity TEXT,
        ADD COLUMN IF NOT EXISTS display_name TEXT,
        ADD COLUMN IF NOT EXISTS auth_data_encrypted TEXT,
        ADD COLUMN IF NOT EXISTS outreach_enabled BOOLEAN NOT NULL DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS permission_changed_by TEXT REFERENCES users(id) ON DELETE SET NULL,
        ADD COLUMN IF NOT EXISTS permission_changed_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS last_reply_sync_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS reply_sync_error TEXT
        """
    )
    op.execute(
        """
        UPDATE outreach_sender_accounts sender
        SET outreach_enabled = permission.outreach_enabled,
            permission_changed_at = COALESCE(permission.updated_at, sender.updated_at)
        FROM telegram_account_permissions permission
        WHERE sender.channel = 'telegram'
          AND sender.external_account_id = permission.account_id
        """
    )
    op.execute("DROP INDEX IF EXISTS uq_outreach_sender_account_binding")
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_outreach_sender_account_binding
        ON outreach_sender_accounts(
            scope_type, COALESCE(business_id, ''), channel,
            COALESCE(external_account_id, sender_identity, '')
        )
        """
    )
    op.execute("ALTER TABLE outreach_sender_accounts DROP CONSTRAINT IF EXISTS ck_outreach_sender_account_channel")
    op.execute(
        """
        ALTER TABLE outreach_sender_accounts
        ADD CONSTRAINT ck_outreach_sender_account_channel CHECK (
            channel IN ('telegram', 'email', 'whatsapp', 'max', 'vk', 'sms', 'manual')
        )
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_outreach_sender_health_status'
            ) THEN
                ALTER TABLE outreach_sender_accounts
                ADD CONSTRAINT ck_outreach_sender_health_status CHECK (
                    health_status IN ('healthy', 'warning', 'degraded', 'paused', 'blocked')
                );
            END IF;
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_outreach_sender_health_score'
            ) THEN
                ALTER TABLE outreach_sender_accounts
                ADD CONSTRAINT ck_outreach_sender_health_score CHECK (health_score BETWEEN 0 AND 100);
            END IF;
        END $$
        """
    )

    op.execute(
        """
        ALTER TABLE outreach_campaigns
        ADD COLUMN IF NOT EXISTS recipient_key TEXT,
        ADD COLUMN IF NOT EXISTS approved_snapshot_hash TEXT,
        ADD COLUMN IF NOT EXISTS last_reply_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS needs_attention_reason TEXT
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreach_campaigns_recipient_active
        ON outreach_campaigns(scope_type, COALESCE(business_id, ''), recipient_key, status, updated_at DESC)
        """
    )

    op.execute(
        """
        ALTER TABLE outreach_campaign_touches
        ADD COLUMN IF NOT EXISTS strategy_fingerprint TEXT,
        ADD COLUMN IF NOT EXISTS strategy_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        ADD COLUMN IF NOT EXISTS manual_due_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS preflight_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS preflight_reason TEXT
        """
    )
    op.execute("ALTER TABLE outreach_campaign_touches DROP CONSTRAINT IF EXISTS ck_outreach_campaign_touch_channel")
    op.execute(
        """
        ALTER TABLE outreach_campaign_touches
        ADD CONSTRAINT ck_outreach_campaign_touch_channel CHECK (
            channel IN ('telegram', 'email', 'whatsapp', 'max', 'vk', 'sms', 'manual')
        )
        """
    )
    op.execute("ALTER TABLE outreach_campaign_touches DROP CONSTRAINT IF EXISTS ck_outreach_campaign_touch_status")
    op.execute(
        """
        ALTER TABLE outreach_campaign_touches
        ADD CONSTRAINT ck_outreach_campaign_touch_status CHECK (
            status IN (
                'draft', 'approved', 'scheduled', 'queued', 'sent', 'delivered',
                'manual', 'awaiting_manual_send', 'manual_sent', 'manual_skipped',
                'manual_expired', 'needs_attention', 'paused', 'cancelled',
                'failed', 'skipped', 'reply_cancelled'
            )
        )
        """
    )

    op.execute("ALTER TABLE outreach_suppressions ALTER COLUMN lead_id DROP NOT NULL")
    op.execute(
        """
        ALTER TABLE outreach_suppressions
        ADD COLUMN IF NOT EXISTS scope_type TEXT NOT NULL DEFAULT 'business',
        ADD COLUMN IF NOT EXISTS business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
        ADD COLUMN IF NOT EXISTS normalized_contact_hash TEXT,
        ADD COLUMN IF NOT EXISTS recipient_key TEXT,
        ADD COLUMN IF NOT EXISTS note TEXT,
        ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        """
    )
    op.execute(
        """
        UPDATE outreach_suppressions suppression
        SET scope_type = CASE WHEN workstream.workstream_type = 'localos_sales' THEN 'platform' ELSE 'business' END,
            business_id = workstream.client_business_id
        FROM lead_workstreams workstream
        WHERE workstream.id = suppression.workstream_id
          AND suppression.business_id IS NULL
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1 FROM pg_constraint WHERE conname = 'ck_outreach_suppression_scope'
            ) THEN
                ALTER TABLE outreach_suppressions
                ADD CONSTRAINT ck_outreach_suppression_scope CHECK (
                    scope_type IN ('platform', 'business', 'platform_safety')
                );
            END IF;
        END $$
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreach_suppressions_scope_recipient
        ON outreach_suppressions(
            scope_type, COALESCE(business_id, ''), recipient_key,
            normalized_contact_hash, expires_at
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_suppression_events (
            id UUID PRIMARY KEY,
            suppression_id UUID REFERENCES outreach_suppressions(id) ON DELETE SET NULL,
            action TEXT NOT NULL,
            scope_type TEXT NOT NULL,
            business_id TEXT REFERENCES businesses(id) ON DELETE SET NULL,
            actor_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_outreach_suppression_event_action CHECK (
                action IN ('created', 'imported', 'deleted', 'expired')
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_outreach_suppression_events_scope ON outreach_suppression_events(scope_type, COALESCE(business_id, ''), created_at DESC)"
    )

    op.execute(
        """
        ALTER TABLE outreachsendqueue
        ADD COLUMN IF NOT EXISTS recipient_key TEXT,
        ADD COLUMN IF NOT EXISTS idempotency_key TEXT,
        ADD COLUMN IF NOT EXISTS dispatch_started_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS preflight_at TIMESTAMPTZ,
        ADD COLUMN IF NOT EXISTS preflight_reason TEXT
        """
    )
    op.execute(
        "UPDATE outreachsendqueue SET idempotency_key = 'outreach:' || id::text WHERE idempotency_key IS NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_outreachsendqueue_idempotency ON outreachsendqueue(idempotency_key) WHERE idempotency_key IS NOT NULL"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_sender_account_events (
            id UUID PRIMARY KEY,
            sender_account_id UUID NOT NULL REFERENCES outreach_sender_accounts(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            actor_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_outreach_sender_account_event_type CHECK (
                event_type IN (
                    'connected', 'permission_changed', 'preflight_succeeded',
                    'preflight_failed', 'reply_sync_succeeded',
                    'reply_sync_failed', 'disconnected'
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreach_sender_account_events_account
        ON outreach_sender_account_events(sender_account_id, created_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_sender_health_events (
            id UUID PRIMARY KEY,
            sender_account_id UUID NOT NULL REFERENCES outreach_sender_accounts(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            severity TEXT NOT NULL DEFAULT 'info',
            provider_code TEXT,
            campaign_id UUID REFERENCES outreach_campaigns(id) ON DELETE SET NULL,
            touch_id UUID REFERENCES outreach_campaign_touches(id) ON DELETE SET NULL,
            metrics_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_outreach_sender_health_event_severity CHECK (
                severity IN ('info', 'warning', 'degraded', 'critical')
            )
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_signal_links (
            id UUID PRIMARY KEY,
            workstream_id UUID NOT NULL REFERENCES lead_workstreams(id) ON DELETE CASCADE,
            source_type TEXT NOT NULL,
            source_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'selected',
            linked_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_lead_signal_link_source CHECK (
                source_type IN ('telegram_opportunity', 'manual_public_signal')
            ),
            CONSTRAINT ck_lead_signal_link_status CHECK (
                status IN ('selected', 'rejected')
            ),
            UNIQUE(workstream_id, source_type, source_id)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_lead_signal_links_workstream ON lead_signal_links(workstream_id, status, updated_at DESC)"
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreach_sender_health_events_account
        ON outreach_sender_health_events(sender_account_id, occurred_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_inbound_events (
            id UUID PRIMARY KEY,
            campaign_id UUID REFERENCES outreach_campaigns(id) ON DELETE SET NULL,
            touch_id UUID REFERENCES outreach_campaign_touches(id) ON DELETE SET NULL,
            lead_id TEXT REFERENCES prospectingleads(id) ON DELETE SET NULL,
            workstream_id UUID REFERENCES lead_workstreams(id) ON DELETE SET NULL,
            sender_account_id UUID REFERENCES outreach_sender_accounts(id) ON DELETE SET NULL,
            channel TEXT NOT NULL,
            provider_event_id TEXT,
            event_type TEXT NOT NULL,
            classification TEXT NOT NULL,
            is_human BOOLEAN NOT NULL DEFAULT FALSE,
            stops_campaign BOOLEAN NOT NULL DEFAULT FALSE,
            confidence NUMERIC(5, 4) NOT NULL DEFAULT 0,
            raw_payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            classified_by TEXT NOT NULL DEFAULT 'system',
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_outreach_inbound_classification CHECK (
                classification IN (
                    'interested', 'question', 'not_interested', 'unsubscribe',
                    'complaint', 'human_unknown', 'out_of_office', 'bounce',
                    'temporary_delivery_failure', 'permanent_delivery_failure',
                    'system_acknowledgement'
                )
            ),
            CONSTRAINT ck_outreach_inbound_confidence CHECK (confidence BETWEEN 0 AND 1)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_outreach_inbound_provider_event
        ON outreach_inbound_events(channel, provider_event_id)
        WHERE provider_event_id IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreach_inbound_lead_time
        ON outreach_inbound_events(lead_id, occurred_at DESC)
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_learning_events (
            id UUID PRIMARY KEY,
            scope_type TEXT NOT NULL,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            workstream_type TEXT NOT NULL,
            campaign_id UUID REFERENCES outreach_campaigns(id) ON DELETE SET NULL,
            touch_id UUID REFERENCES outreach_campaign_touches(id) ON DELETE SET NULL,
            strategy_fingerprint TEXT NOT NULL,
            outcome_type TEXT NOT NULL,
            dimensions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_outreach_learning_scope CHECK (scope_type IN ('platform', 'business')),
            CONSTRAINT ck_outreach_learning_workstream CHECK (
                workstream_type IN ('localos_sales', 'client_partnership')
            ),
            CONSTRAINT ck_outreach_learning_outcome CHECK (
                outcome_type IN (
                    'sent', 'delivered', 'delivery_failed', 'replied',
                    'positive_reply', 'question', 'hard_no', 'unsubscribe',
                    'complaint', 'meeting_booked', 'converted', 'no_reply'
                )
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_outreach_learning_events_strategy
        ON outreach_learning_events(
            scope_type, COALESCE(business_id, ''), workstream_type,
            strategy_fingerprint, occurred_at DESC
        )
        """
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreach_strategy_stats (
            id UUID PRIMARY KEY,
            scope_type TEXT NOT NULL,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            workstream_type TEXT NOT NULL,
            strategy_fingerprint TEXT NOT NULL,
            dimensions_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            sent_count INTEGER NOT NULL DEFAULT 0,
            delivered_count INTEGER NOT NULL DEFAULT 0,
            reply_count INTEGER NOT NULL DEFAULT 0,
            positive_reply_count INTEGER NOT NULL DEFAULT 0,
            question_count INTEGER NOT NULL DEFAULT 0,
            hard_no_count INTEGER NOT NULL DEFAULT 0,
            unsubscribe_count INTEGER NOT NULL DEFAULT 0,
            complaint_count INTEGER NOT NULL DEFAULT 0,
            meeting_count INTEGER NOT NULL DEFAULT 0,
            converted_count INTEGER NOT NULL DEFAULT 0,
            sample_status TEXT NOT NULL DEFAULT 'insufficient_data',
            confidence NUMERIC(5, 4) NOT NULL DEFAULT 0,
            first_event_at TIMESTAMPTZ,
            last_event_at TIMESTAMPTZ,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_outreach_strategy_stats_scope CHECK (scope_type IN ('platform', 'business')),
            CONSTRAINT ck_outreach_strategy_stats_sample CHECK (
                sample_status IN ('insufficient_data', 'preliminary', 'reliable')
            ),
            CONSTRAINT ck_outreach_strategy_stats_confidence CHECK (confidence BETWEEN 0 AND 1)
        )
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_outreach_strategy_stats_scope
        ON outreach_strategy_stats(
            scope_type, COALESCE(business_id, ''), workstream_type, strategy_fingerprint
        )
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_outreach_strategy_stats_scope")
    op.execute("DROP TABLE IF EXISTS outreach_strategy_stats")
    op.execute("DROP INDEX IF EXISTS idx_outreach_learning_events_strategy")
    op.execute("DROP TABLE IF EXISTS outreach_learning_events")
    op.execute("DROP INDEX IF EXISTS idx_outreach_inbound_lead_time")
    op.execute("DROP INDEX IF EXISTS uq_outreach_inbound_provider_event")
    op.execute("DROP TABLE IF EXISTS outreach_inbound_events")
    op.execute("DROP INDEX IF EXISTS idx_outreach_sender_account_events_account")
    op.execute("DROP TABLE IF EXISTS outreach_sender_account_events")
    op.execute("DROP INDEX IF EXISTS idx_outreach_sender_health_events_account")
    op.execute("DROP TABLE IF EXISTS outreach_sender_health_events")
    op.execute("DROP INDEX IF EXISTS idx_lead_signal_links_workstream")
    op.execute("DROP TABLE IF EXISTS lead_signal_links")
    op.execute("DROP INDEX IF EXISTS uq_outreachsendqueue_idempotency")
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS preflight_reason")
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS preflight_at")
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS dispatch_started_at")
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS idempotency_key")
    op.execute("ALTER TABLE outreachsendqueue DROP COLUMN IF EXISTS recipient_key")
    op.execute("DROP INDEX IF EXISTS idx_outreach_suppression_events_scope")
    op.execute("DROP TABLE IF EXISTS outreach_suppression_events")
    op.execute("DROP INDEX IF EXISTS idx_outreach_suppressions_scope_recipient")
    op.execute("ALTER TABLE outreach_suppressions DROP CONSTRAINT IF EXISTS ck_outreach_suppression_scope")
    op.execute("ALTER TABLE outreach_suppressions DROP COLUMN IF EXISTS updated_at")
    op.execute("ALTER TABLE outreach_suppressions DROP COLUMN IF EXISTS note")
    op.execute("ALTER TABLE outreach_suppressions DROP COLUMN IF EXISTS recipient_key")
    op.execute("ALTER TABLE outreach_suppressions DROP COLUMN IF EXISTS normalized_contact_hash")
    op.execute("ALTER TABLE outreach_suppressions DROP COLUMN IF EXISTS business_id")
    op.execute("ALTER TABLE outreach_suppressions DROP COLUMN IF EXISTS scope_type")
    op.execute("ALTER TABLE outreach_suppressions ALTER COLUMN lead_id SET NOT NULL")
    op.execute("ALTER TABLE outreach_campaign_touches DROP CONSTRAINT IF EXISTS ck_outreach_campaign_touch_status")
    op.execute(
        """
        ALTER TABLE outreach_campaign_touches
        ADD CONSTRAINT ck_outreach_campaign_touch_status CHECK (
            status IN (
                'draft', 'approved', 'scheduled', 'queued', 'sent', 'delivered',
                'manual', 'paused', 'cancelled', 'failed', 'skipped'
            )
        )
        """
    )
    op.execute("ALTER TABLE outreach_campaign_touches DROP CONSTRAINT IF EXISTS ck_outreach_campaign_touch_channel")
    op.execute(
        """
        ALTER TABLE outreach_campaign_touches
        ADD CONSTRAINT ck_outreach_campaign_touch_channel CHECK (
            channel IN ('telegram', 'email', 'whatsapp', 'max', 'vk', 'manual')
        )
        """
    )
    op.execute("ALTER TABLE outreach_campaign_touches DROP COLUMN IF EXISTS preflight_reason")
    op.execute("ALTER TABLE outreach_campaign_touches DROP COLUMN IF EXISTS preflight_at")
    op.execute("ALTER TABLE outreach_campaign_touches DROP COLUMN IF EXISTS manual_due_at")
    op.execute("ALTER TABLE outreach_campaign_touches DROP COLUMN IF EXISTS strategy_json")
    op.execute("ALTER TABLE outreach_campaign_touches DROP COLUMN IF EXISTS strategy_fingerprint")
    op.execute("DROP INDEX IF EXISTS idx_outreach_campaigns_recipient_active")
    op.execute("ALTER TABLE outreach_campaigns DROP COLUMN IF EXISTS needs_attention_reason")
    op.execute("ALTER TABLE outreach_campaigns DROP COLUMN IF EXISTS last_reply_at")
    op.execute("ALTER TABLE outreach_campaigns DROP COLUMN IF EXISTS approved_snapshot_hash")
    op.execute("ALTER TABLE outreach_campaigns DROP COLUMN IF EXISTS recipient_key")
    op.execute("ALTER TABLE outreach_sender_accounts DROP CONSTRAINT IF EXISTS ck_outreach_sender_health_score")
    op.execute("ALTER TABLE outreach_sender_accounts DROP CONSTRAINT IF EXISTS ck_outreach_sender_health_status")
    op.execute("ALTER TABLE outreach_sender_accounts DROP CONSTRAINT IF EXISTS ck_outreach_sender_account_channel")
    op.execute("DROP INDEX IF EXISTS uq_outreach_sender_account_binding")
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
        ALTER TABLE outreach_sender_accounts
        ADD CONSTRAINT ck_outreach_sender_account_channel CHECK (
            channel IN ('telegram', 'email', 'whatsapp', 'max', 'vk', 'manual')
        )
        """
    )
    op.execute("ALTER TABLE outreach_sender_accounts DROP COLUMN IF EXISTS last_health_event_at")
    op.execute("ALTER TABLE outreach_sender_accounts DROP COLUMN IF EXISTS reply_sync_error")
    op.execute("ALTER TABLE outreach_sender_accounts DROP COLUMN IF EXISTS last_reply_sync_at")
    op.execute("ALTER TABLE outreach_sender_accounts DROP COLUMN IF EXISTS permission_changed_at")
    op.execute("ALTER TABLE outreach_sender_accounts DROP COLUMN IF EXISTS permission_changed_by")
    op.execute("ALTER TABLE outreach_sender_accounts DROP COLUMN IF EXISTS outreach_enabled")
    op.execute("ALTER TABLE outreach_sender_accounts DROP COLUMN IF EXISTS auth_data_encrypted")
    op.execute("ALTER TABLE outreach_sender_accounts DROP COLUMN IF EXISTS display_name")
    op.execute("ALTER TABLE outreach_sender_accounts DROP COLUMN IF EXISTS sender_identity")
    op.execute("ALTER TABLE outreach_sender_accounts DROP COLUMN IF EXISTS health_changed_at")
    op.execute("ALTER TABLE outreach_sender_accounts DROP COLUMN IF EXISTS health_metrics_json")
    op.execute("ALTER TABLE outreach_sender_accounts DROP COLUMN IF EXISTS health_reason")
    op.execute("ALTER TABLE outreach_sender_accounts DROP COLUMN IF EXISTS health_score")
    op.execute("ALTER TABLE outreach_sender_accounts DROP COLUMN IF EXISTS health_status")
    op.execute("ALTER TABLE lead_workstreams DROP CONSTRAINT IF EXISTS ck_lead_workstreams_lifecycle_status")
    op.execute("ALTER TABLE lead_workstreams DROP COLUMN IF EXISTS state_changed_at")
    op.execute("ALTER TABLE lead_workstreams DROP COLUMN IF EXISTS next_step")
    op.execute("ALTER TABLE lead_workstreams DROP COLUMN IF EXISTS status_reason")
    op.execute("ALTER TABLE lead_workstreams DROP COLUMN IF EXISTS lifecycle_status")
    op.execute("ALTER TABLE lead_enrichment_jobs DROP CONSTRAINT IF EXISTS ck_lead_enrichment_jobs_status")
    op.execute("UPDATE lead_enrichment_jobs SET status = 'needs_input' WHERE status IN ('needs_contact', 'needs_evidence', 'suppressed')")
    op.execute(
        """
        ALTER TABLE lead_enrichment_jobs
        ADD CONSTRAINT ck_lead_enrichment_jobs_status CHECK (
            status IN (
                'queued', 'collecting', 'verifying', 'researching', 'drafting',
                'ready', 'needs_input', 'retry_wait', 'failed'
            )
        )
        """
    )
