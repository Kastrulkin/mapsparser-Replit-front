"""add persistent Telegram control scope preferences

Revision ID: 20260723_001
Revises: 20260722_003
Create Date: 2026-07-23 12:00:00.000000
"""

from alembic import op


revision = "20260723_001"
down_revision = "20260722_003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS telegramcontrolpreferences (
            user_id TEXT PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
            telegram_id TEXT NOT NULL UNIQUE,
            scope_type TEXT NOT NULL DEFAULT 'business',
            scope_id TEXT,
            recent_scopes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            favorite_scopes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            last_business_by_network_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            notification_preferences_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT telegramcontrolpreferences_scope_type_check
                CHECK (scope_type IN ('platform', 'network', 'business'))
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_telegramcontrolpreferences_scope
        ON telegramcontrolpreferences(scope_type, scope_id)
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS telegramcontrolpreferences")
