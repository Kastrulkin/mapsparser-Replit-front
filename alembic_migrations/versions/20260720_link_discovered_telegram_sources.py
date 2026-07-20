"""link Telegram sources discovered while parsing leads

Revision ID: 20260720_002
Revises: 20260720_001
Create Date: 2026-07-20 15:30:00.000000
"""

from alembic import op


revision = "20260720_002"
down_revision = "20260720_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE lead_signal_links DROP CONSTRAINT IF EXISTS ck_lead_signal_link_source"
    )
    op.execute(
        """
        ALTER TABLE lead_signal_links
        ADD CONSTRAINT ck_lead_signal_link_source CHECK (
            source_type IN (
                'telegram_opportunity',
                'telegram_knowledge_source',
                'manual_public_signal'
            )
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_lead_signal_links_telegram_source
        ON lead_signal_links(source_id, workstream_id)
        WHERE source_type = 'telegram_knowledge_source'
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_lead_signal_links_telegram_source")
    op.execute(
        "ALTER TABLE lead_signal_links DROP CONSTRAINT IF EXISTS ck_lead_signal_link_source"
    )
    op.execute(
        """
        ALTER TABLE lead_signal_links
        ADD CONSTRAINT ck_lead_signal_link_source CHECK (
            source_type IN ('telegram_opportunity', 'manual_public_signal')
        )
        """
    )
