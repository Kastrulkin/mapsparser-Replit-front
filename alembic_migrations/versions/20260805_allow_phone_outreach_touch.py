"""allow phone and manual VK outreach touches

Revision ID: 20260805_002
Revises: 20260805_001
Create Date: 2026-08-05
"""

from alembic import op


revision = "20260805_002"
down_revision = "20260805_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE outreach_campaign_touches "
        "DROP CONSTRAINT IF EXISTS ck_outreach_campaign_touch_channel"
    )
    op.execute(
        """
        ALTER TABLE outreach_campaign_touches
        ADD CONSTRAINT ck_outreach_campaign_touch_channel CHECK (
            channel IN (
                'telegram', 'email', 'whatsapp', 'max', 'vk', 'vk_manual',
                'sms', 'phone', 'manual'
            )
        )
        """
    )


def downgrade():
    op.execute(
        "ALTER TABLE outreach_campaign_touches "
        "DROP CONSTRAINT IF EXISTS ck_outreach_campaign_touch_channel"
    )
    op.execute(
        """
        ALTER TABLE outreach_campaign_touches
        ADD CONSTRAINT ck_outreach_campaign_touch_channel CHECK (
            channel IN ('telegram', 'email', 'whatsapp', 'max', 'vk', 'sms', 'manual')
        )
        """
    )
