"""Add website goals, confirmed outcomes and change annotations.

Revision ID: 20260822_001
Revises: 20260821_001
"""

from alembic import op


revision = "20260822_001"
down_revision = "20260821_001"
branch_labels = None
depends_on = None


_EVENT_TYPES = (
    "'session_start', 'page_view', 'scroll_depth', 'click', 'outbound_click', "
    "'form_start', 'form_submit', 'heartbeat', 'page_leave', 'section_view', "
    "'section_engagement', 'cta_impression', 'cta_click', 'form_submit_attempt', "
    "'form_validation_error', 'form_submit_success', 'form_submit_error'"
)


def upgrade():
    op.execute(
        "ALTER TABLE business_web_trackers "
        "ADD COLUMN IF NOT EXISTS conversion_key_hash TEXT, "
        "ADD COLUMN IF NOT EXISTS conversion_key_created_at TIMESTAMPTZ"
    )
    op.execute(
        "ALTER TABLE web_sessions "
        "ADD COLUMN IF NOT EXISTS utm_term TEXT, "
        "ADD COLUMN IF NOT EXISTS utm_content TEXT"
    )
    op.execute(
        "ALTER TABLE web_tracking_deletion_audits "
        "ADD COLUMN IF NOT EXISTS page_groups BIGINT NOT NULL DEFAULT 0, "
        "ADD COLUMN IF NOT EXISTS goals BIGINT NOT NULL DEFAULT 0, "
        "ADD COLUMN IF NOT EXISTS confirmed_conversions BIGINT NOT NULL DEFAULT 0, "
        "ADD COLUMN IF NOT EXISTS campaign_costs BIGINT NOT NULL DEFAULT 0, "
        "ADD COLUMN IF NOT EXISTS change_annotations BIGINT NOT NULL DEFAULT 0"
    )
    op.execute("ALTER TABLE web_events DROP CONSTRAINT IF EXISTS chk_web_event_type")
    op.execute(
        "ALTER TABLE web_events ADD CONSTRAINT chk_web_event_type "
        f"CHECK (event_type IN ({_EVENT_TYPES}))"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS web_page_groups (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            group_type TEXT NOT NULL DEFAULT 'custom',
            match_type TEXT NOT NULL DEFAULT 'prefix',
            include_patterns JSONB NOT NULL DEFAULT '[]'::jsonb,
            exclude_patterns JSONB NOT NULL DEFAULT '[]'::jsonb,
            is_draft BOOLEAN NOT NULL DEFAULT FALSE,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_web_page_group_type CHECK (
                group_type IN ('service', 'pricing', 'contact', 'success', 'custom')
            ),
            CONSTRAINT chk_web_page_group_match_type CHECK (
                match_type IN ('exact', 'prefix', 'contains', 'list')
            ),
            CONSTRAINT uq_web_page_group_name UNIQUE (business_id, name)
        );
        CREATE INDEX IF NOT EXISTS idx_web_page_groups_business
            ON web_page_groups (business_id, enabled, updated_at DESC);

        CREATE TABLE IF NOT EXISTS web_goals (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            goal_type TEXT NOT NULL,
            matcher_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            is_draft BOOLEAN NOT NULL DEFAULT FALSE,
            enabled BOOLEAN NOT NULL DEFAULT TRUE,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_web_goal_type CHECK (goal_type IN (
                'page_view', 'section_view', 'cta_click', 'form_submit', 'booking_click',
                'lead_created', 'message_started', 'message_lead', 'call_connected',
                'call_answered', 'call_qualified', 'booking_created', 'booking_confirmed',
                'booking_cancelled', 'visit_completed', 'payment_completed'
            )),
            CONSTRAINT uq_web_goal_name UNIQUE (business_id, name)
        );
        CREATE INDEX IF NOT EXISTS idx_web_goals_business
            ON web_goals (business_id, enabled, updated_at DESC);

        CREATE TABLE IF NOT EXISTS web_confirmed_conversions (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            tracker_id UUID REFERENCES business_web_trackers(id) ON DELETE SET NULL,
            source TEXT NOT NULL,
            external_id TEXT NOT NULL,
            event_type TEXT NOT NULL,
            occurred_at TIMESTAMPTZ NOT NULL,
            attribution_session_key TEXT,
            cta_id TEXT,
            amount NUMERIC(14, 2),
            currency TEXT,
            metadata_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_web_confirmed_conversion_type CHECK (event_type IN (
                'lead_created', 'message_started', 'message_lead', 'call_connected',
                'call_answered', 'call_qualified', 'booking_created', 'booking_confirmed',
                'booking_cancelled', 'visit_completed', 'payment_completed'
            )),
            CONSTRAINT chk_web_confirmed_conversion_amount CHECK (amount IS NULL OR amount >= 0),
            CONSTRAINT uq_web_confirmed_conversion UNIQUE (business_id, source, external_id, event_type)
        );
        CREATE INDEX IF NOT EXISTS idx_web_confirmed_conversions_business_time
            ON web_confirmed_conversions (business_id, occurred_at DESC);
        CREATE INDEX IF NOT EXISTS idx_web_confirmed_conversions_session
            ON web_confirmed_conversions (business_id, attribution_session_key)
            WHERE attribution_session_key IS NOT NULL;

        CREATE TABLE IF NOT EXISTS web_campaign_costs (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            source TEXT NOT NULL,
            medium TEXT NOT NULL DEFAULT '',
            campaign TEXT NOT NULL DEFAULT '',
            content TEXT NOT NULL DEFAULT '',
            term TEXT NOT NULL DEFAULT '',
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            cost NUMERIC(14, 2) NOT NULL,
            currency TEXT NOT NULL,
            external_id TEXT,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_web_campaign_cost CHECK (cost >= 0),
            CONSTRAINT chk_web_campaign_period CHECK (period_end >= period_start)
        );
        CREATE UNIQUE INDEX IF NOT EXISTS uq_web_campaign_cost_external
            ON web_campaign_costs (business_id, source, external_id)
            WHERE external_id IS NOT NULL;
        CREATE INDEX IF NOT EXISTS idx_web_campaign_costs_business_period
            ON web_campaign_costs (business_id, period_start, period_end);

        CREATE TABLE IF NOT EXISTS web_change_annotations (
            id UUID PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            occurred_at TIMESTAMPTZ NOT NULL,
            change_type TEXT NOT NULL,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            page_path TEXT NOT NULL DEFAULT '',
            expected_impact TEXT NOT NULL DEFAULT '',
            source TEXT NOT NULL DEFAULT 'manual',
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT chk_web_change_type CHECK (change_type IN (
                'page', 'price', 'headline', 'cta', 'form', 'campaign', 'promotion',
                'incident', 'tracker', 'other'
            )),
            CONSTRAINT chk_web_change_source CHECK (source IN ('manual', 'system'))
        );
        CREATE INDEX IF NOT EXISTS idx_web_change_annotations_business_time
            ON web_change_annotations (business_id, occurred_at DESC);
        """
    )


def downgrade():
    op.execute(
        """
        DROP TABLE IF EXISTS web_change_annotations;
        DROP TABLE IF EXISTS web_campaign_costs;
        DROP TABLE IF EXISTS web_confirmed_conversions;
        DROP TABLE IF EXISTS web_goals;
        DROP TABLE IF EXISTS web_page_groups;
        """
    )
    op.execute("ALTER TABLE web_sessions DROP COLUMN IF EXISTS utm_content")
    op.execute("ALTER TABLE web_sessions DROP COLUMN IF EXISTS utm_term")
    op.execute("ALTER TABLE business_web_trackers DROP COLUMN IF EXISTS conversion_key_created_at")
    op.execute("ALTER TABLE business_web_trackers DROP COLUMN IF EXISTS conversion_key_hash")
    op.execute("ALTER TABLE web_tracking_deletion_audits DROP COLUMN IF EXISTS change_annotations")
    op.execute("ALTER TABLE web_tracking_deletion_audits DROP COLUMN IF EXISTS campaign_costs")
    op.execute("ALTER TABLE web_tracking_deletion_audits DROP COLUMN IF EXISTS confirmed_conversions")
    op.execute("ALTER TABLE web_tracking_deletion_audits DROP COLUMN IF EXISTS goals")
    op.execute("ALTER TABLE web_tracking_deletion_audits DROP COLUMN IF EXISTS page_groups")
    op.execute("ALTER TABLE web_events DROP CONSTRAINT IF EXISTS chk_web_event_type")
    op.execute(
        "ALTER TABLE web_events ADD CONSTRAINT chk_web_event_type CHECK (event_type IN ("
        "'session_start', 'page_view', 'scroll_depth', 'click', 'outbound_click', "
        "'form_start', 'form_submit', 'heartbeat', 'page_leave', 'section_view', "
        "'section_engagement')) NOT VALID"
    )
