"""Scoped Today preferences and trustworthy activity signals.

Revision ID: 20260905_003
Revises: 20260905_002
"""
from alembic import op

revision = "20260905_003"
down_revision = "20260905_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS today_preferences (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            scope_type TEXT NOT NULL CHECK (scope_type IN ('business', 'network')),
            scope_id TEXT NOT NULL,
            primary_flow TEXT NOT NULL DEFAULT 'overview' CHECK (primary_flow IN
                ('overview', 'content', 'influencers', 'partnerships', 'maps', 'upsells', 'automation')),
            suggestions_enabled BOOLEAN NOT NULL DEFAULT TRUE,
            revision INTEGER NOT NULL DEFAULT 1 CHECK (revision > 0),
            previous_flow TEXT,
            undo_until TIMESTAMPTZ,
            proposal_json JSONB,
            candidate_flow TEXT,
            candidate_since DATE,
            evaluated_on DATE,
            next_offer_at TIMESTAMPTZ,
            dismissed_flows_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            PRIMARY KEY (user_id, scope_type, scope_id)
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_today_preferences_candidates ON today_preferences(evaluated_on) WHERE suggestions_enabled")
    op.execute("ALTER TABLE product_analytics_events ADD COLUMN IF NOT EXISTS signal_source TEXT NOT NULL DEFAULT 'legacy'")
    op.execute("ALTER TABLE product_analytics_events ADD COLUMN IF NOT EXISTS deduplication_key TEXT")
    op.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_product_event_dedup ON product_analytics_events(user_id, business_id, deduplication_key) WHERE deduplication_key IS NOT NULL")
    op.execute("CREATE INDEX IF NOT EXISTS idx_product_event_confirmed_activity ON product_analytics_events(user_id, business_id, occurred_at) WHERE signal_source = 'confirmed_user_action'")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_product_event_confirmed_activity")
    op.execute("DROP INDEX IF EXISTS idx_product_event_dedup")
    op.execute("ALTER TABLE product_analytics_events DROP COLUMN IF EXISTS deduplication_key")
    op.execute("ALTER TABLE product_analytics_events DROP COLUMN IF EXISTS signal_source")
    op.execute("DROP TABLE IF EXISTS today_preferences")
