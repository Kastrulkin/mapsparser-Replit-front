"""MAX control identities, isolated preferences and durable transport receipts."""
from alembic import op

revision = '20261015_max_control'
down_revision = '20261012_business_knowledge'
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""CREATE TABLE IF NOT EXISTS max_identities (
        max_id TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
        linked_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), revoked_at TIMESTAMPTZ,
        notifications_enabled BOOLEAN NOT NULL DEFAULT FALSE,
        UNIQUE(user_id))""")
    op.execute("""CREATE TABLE IF NOT EXISTS max_link_tokens (
        token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES users(id),
        expires_at TIMESTAMPTZ NOT NULL, consumed_at TIMESTAMPTZ,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    op.execute("""CREATE TABLE IF NOT EXISTS maxcontrolpreferences (
        user_id TEXT PRIMARY KEY REFERENCES users(id), max_id TEXT NOT NULL UNIQUE,
        scope_type TEXT CHECK(scope_type IN ('business','network','platform')), scope_id TEXT,
        recent_scopes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        favorite_scopes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
        last_business_by_network_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        notification_preferences_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    op.execute("""CREATE TABLE IF NOT EXISTS max_webhook_events (
        event_key TEXT PRIMARY KEY, payload_json JSONB NOT NULL,
        status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN
            ('pending','processing','completed','failed','needs_attention')),
        attempts INTEGER NOT NULL DEFAULT 0, result_json JSONB,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), started_at TIMESTAMPTZ,
        completed_at TIMESTAMPTZ, error_code TEXT)""")
    op.execute("ALTER TABLE max_webhook_events ADD COLUMN IF NOT EXISTS available_at TIMESTAMPTZ NOT NULL DEFAULT NOW()")
    op.execute("CREATE INDEX IF NOT EXISTS idx_max_events_pending ON max_webhook_events(status,created_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_max_link_tokens_user ON max_link_tokens(user_id)")
    op.execute("""CREATE TABLE IF NOT EXISTS max_bot_states (
        user_id TEXT PRIMARY KEY REFERENCES users(id), business_id TEXT NOT NULL,
        state_json JSONB NOT NULL DEFAULT '{}'::jsonb,updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    op.execute("""CREATE TABLE IF NOT EXISTS max_dialogue_states (
        max_id TEXT PRIMARY KEY, user_id TEXT REFERENCES users(id), state_json JSONB NOT NULL DEFAULT '{}'::jsonb,
        scope_fingerprint TEXT NOT NULL DEFAULT '', updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    op.execute("ALTER TABLE max_dialogue_states ADD COLUMN IF NOT EXISTS revision INTEGER NOT NULL DEFAULT 0")
    op.execute("""CREATE TABLE IF NOT EXISTS max_dialogue_buttons (
        token TEXT PRIMARY KEY,max_id TEXT NOT NULL,revision INTEGER NOT NULL,
        scope_fingerprint TEXT NOT NULL,callback_data TEXT NOT NULL,consumed_at TIMESTAMPTZ,
        expires_at TIMESTAMPTZ NOT NULL)""")
    op.execute("CREATE INDEX IF NOT EXISTS idx_max_dialogue_buttons_expiry ON max_dialogue_buttons(expires_at)")
    op.execute("""CREATE TABLE IF NOT EXISTS max_guest_audits (
        event_key TEXT PRIMARY KEY,max_id TEXT NOT NULL,slug TEXT NOT NULL,public_url TEXT NOT NULL,
        created_at TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
    op.execute("ALTER TABLE max_guest_audits ADD COLUMN IF NOT EXISTS notifications_enabled BOOLEAN NOT NULL DEFAULT TRUE")
    op.execute("CREATE INDEX IF NOT EXISTS idx_max_guest_audits_identity ON max_guest_audits(max_id,created_at)")
    op.execute("""DO $$ BEGIN IF to_regclass('botfeaturerequests') IS NOT NULL THEN
        ALTER TABLE botfeaturerequests ADD COLUMN IF NOT EXISTS max_id TEXT;
        ALTER TABLE botfeaturerequests ALTER COLUMN telegram_id DROP NOT NULL;
        END IF; END $$""")
    op.execute("ALTER TABLE product_analytics_events DROP CONSTRAINT IF EXISTS chk_product_analytics_channel")
    op.execute("ALTER TABLE product_analytics_events ADD CONSTRAINT chk_product_analytics_channel CHECK(channel IN ('web','telegram_mini_app','max_mini_app','max_bot'))")


def downgrade():
    # Disable MAX before application rollback. Preserve identities and delivery evidence.
    pass
