"""add canonical lead journeys and next actions

Revision ID: 20260826_003
Revises: 20260826_002
Create Date: 2026-08-26
"""

from alembic import op


revision = "20260826_003"
down_revision = "20260826_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS lead_journeys (
            id UUID PRIMARY KEY,
            prospect_lead_id TEXT REFERENCES prospectingleads(id) ON DELETE SET NULL,
            source_offer_type TEXT NOT NULL DEFAULT 'lead_offer',
            source_offer_id TEXT,
            public_token_hash TEXT NOT NULL UNIQUE,
            status TEXT NOT NULL DEFAULT 'preview',
            source TEXT NOT NULL DEFAULT 'outreach',
            preview_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            selected_flow TEXT,
            selected_entity_type TEXT,
            selected_entity_id TEXT,
            claimed_user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            claimed_business_id TEXT REFERENCES businesses(id) ON DELETE SET NULL,
            expires_at TIMESTAMPTZ NOT NULL,
            revoked_at TIMESTAMPTZ,
            claimed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_lead_journeys_status CHECK (
                status IN ('preview', 'registration_pending', 'claimed', 'expired', 'revoked')
            ),
            CONSTRAINT ck_lead_journeys_flow CHECK (
                selected_flow IS NULL OR selected_flow IN ('influencer', 'partnership', 'maps')
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_lead_journeys_lead ON lead_journeys(prospect_lead_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_lead_journeys_claim ON lead_journeys(claimed_business_id, status, updated_at DESC)"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS journey_actions (
            id UUID PRIMARY KEY,
            journey_id UUID REFERENCES lead_journeys(id) ON DELETE CASCADE,
            business_id TEXT REFERENCES businesses(id) ON DELETE CASCADE,
            user_id TEXT REFERENCES users(id) ON DELETE SET NULL,
            lead_id TEXT REFERENCES prospectingleads(id) ON DELETE SET NULL,
            flow_type TEXT NOT NULL,
            entity_type TEXT NOT NULL,
            entity_id TEXT,
            action_type TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'ready',
            priority INTEGER NOT NULL DEFAULT 50,
            due_at TIMESTAMPTZ,
            title TEXT NOT NULL,
            description TEXT NOT NULL DEFAULT '',
            cta_label TEXT NOT NULL,
            cta_target_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            source_action_id UUID REFERENCES journey_actions(id) ON DELETE SET NULL,
            dedupe_key TEXT NOT NULL,
            version INTEGER NOT NULL DEFAULT 1,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_journey_actions_flow CHECK (flow_type IN ('influencer', 'partnership', 'maps', 'upgrade')),
            CONSTRAINT ck_journey_actions_status CHECK (
                status IN ('ready', 'in_progress', 'waiting', 'blocked', 'completed', 'superseded', 'cancelled')
            )
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_journey_actions_business_queue "
        "ON journey_actions(business_id, status, priority DESC, due_at, created_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_journey_actions_journey ON journey_actions(journey_id, created_at)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_journey_actions_active_dedupe "
        "ON journey_actions(dedupe_key) WHERE status IN ('ready', 'in_progress', 'waiting', 'blocked')"
    )

    op.execute(
        """
        CREATE TABLE IF NOT EXISTS journey_action_events (
            id UUID PRIMARY KEY,
            action_id UUID NOT NULL REFERENCES journey_actions(id) ON DELETE CASCADE,
            event_type TEXT NOT NULL,
            command TEXT,
            from_status TEXT,
            to_status TEXT,
            actor_type TEXT NOT NULL DEFAULT 'user',
            actor_id TEXT,
            surface TEXT NOT NULL DEFAULT 'web',
            idempotency_key TEXT NOT NULL,
            payload_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            occurred_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_journey_action_event_surface CHECK (surface IN ('web', 'telegram_mini_app', 'system')),
            UNIQUE (action_id, idempotency_key)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_journey_action_events_action ON journey_action_events(action_id, occurred_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS journey_action_notification_deliveries (
            dedupe_key TEXT PRIMARY KEY,
            action_id UUID NOT NULL REFERENCES journey_actions(id) ON DELETE CASCADE,
            action_version INTEGER NOT NULL,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            telegram_id TEXT NOT NULL,
            message_text TEXT NOT NULL,
            reply_markup_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            sent_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_journey_action_notifications_pending "
        "ON journey_action_notification_deliveries(created_at) WHERE sent_at IS NULL"
    )

    for statement in (
        "ALTER TABLE product_analytics_events ADD COLUMN IF NOT EXISTS lead_id TEXT REFERENCES prospectingleads(id) ON DELETE SET NULL",
        "ALTER TABLE product_analytics_events ADD COLUMN IF NOT EXISTS journey_id UUID REFERENCES lead_journeys(id) ON DELETE SET NULL",
        "ALTER TABLE product_analytics_events ADD COLUMN IF NOT EXISTS action_id UUID REFERENCES journey_actions(id) ON DELETE SET NULL",
        "ALTER TABLE product_analytics_events ADD COLUMN IF NOT EXISTS flow_type TEXT",
        "ALTER TABLE product_analytics_events ADD COLUMN IF NOT EXISTS entity_type TEXT",
        "ALTER TABLE product_analytics_events ADD COLUMN IF NOT EXISTS entity_id TEXT",
        "ALTER TABLE lead_workstreams ADD COLUMN IF NOT EXISTS partnership_outcome_json JSONB NOT NULL DEFAULT '{}'::jsonb",
        "ALTER TABLE lead_workstreams ADD COLUMN IF NOT EXISTS partnership_launched_at TIMESTAMPTZ",
    ):
        op.execute(statement)
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_analytics_journey_funnel "
        "ON product_analytics_events(journey_id, event_name, occurred_at)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_product_analytics_action_time "
        "ON product_analytics_events(action_id, occurred_at DESC)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_product_analytics_action_time")
    op.execute("DROP INDEX IF EXISTS idx_product_analytics_journey_funnel")
    op.execute("ALTER TABLE lead_workstreams DROP COLUMN IF EXISTS partnership_launched_at")
    op.execute("ALTER TABLE lead_workstreams DROP COLUMN IF EXISTS partnership_outcome_json")
    for column in ("entity_id", "entity_type", "flow_type", "action_id", "journey_id", "lead_id"):
        op.execute(f"ALTER TABLE product_analytics_events DROP COLUMN IF EXISTS {column}")
    op.execute("DROP TABLE IF EXISTS journey_action_notification_deliveries")
    op.execute("DROP TABLE IF EXISTS journey_action_events")
    op.execute("DROP TABLE IF EXISTS journey_actions")
    op.execute("DROP TABLE IF EXISTS lead_journeys")
