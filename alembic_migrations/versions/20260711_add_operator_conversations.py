"""add operator conversations and governed pending actions

Revision ID: 20260711_001
Revises: 20260710_001
Create Date: 2026-07-11
"""

from alembic import op


revision = "20260711_001"
down_revision = "20260710_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS operatorconversations (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            channel TEXT NOT NULL DEFAULT 'web',
            transport_key TEXT,
            status TEXT NOT NULL DEFAULT 'active',
            pending_context JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operatorconversations_actor
        ON operatorconversations(business_id, user_id, channel, updated_at DESC)
        """
    )
    op.execute(
        """
        CREATE UNIQUE INDEX IF NOT EXISTS uq_operatorconversations_transport
        ON operatorconversations(business_id, user_id, channel, transport_key)
        WHERE transport_key IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS operatormessages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES operatorconversations(id) ON DELETE CASCADE,
            business_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            capability TEXT,
            status TEXT,
            result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operatormessages_conversation
        ON operatormessages(conversation_id, created_at)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS operatoractions (
            id TEXT PRIMARY KEY,
            conversation_id TEXT REFERENCES operatorconversations(id) ON DELETE SET NULL,
            business_id TEXT NOT NULL,
            user_id TEXT NOT NULL,
            capability TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending_approval',
            idempotency_key TEXT NOT NULL,
            envelope_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            result_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            confirmed_at TIMESTAMPTZ,
            executed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            UNIQUE (business_id, idempotency_key)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_operatoractions_actor_status
        ON operatoractions(business_id, user_id, status, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS operatoractions")
    op.execute("DROP TABLE IF EXISTS operatormessages")
    op.execute("DROP TABLE IF EXISTS operatorconversations")
