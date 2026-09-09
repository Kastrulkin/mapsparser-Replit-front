"""allow Riderra provider-verified pricebook snapshot events

Revision ID: 20260909_001
Revises: 20260908_001
Create Date: 2026-09-09 12:30:00.000000
"""

from alembic import op


revision = "20260909_001"
down_revision = "20260908_001"
branch_labels = None
depends_on = None


EVENT_TYPE_CHECK_WITH_PRICEBOOK_SNAPSHOT = """
    ALTER TABLE outreach_sender_account_events
    ADD CONSTRAINT ck_outreach_sender_account_event_type CHECK (
        event_type IN (
            'connected', 'permission_changed', 'preflight_succeeded',
            'preflight_failed', 'reply_sync_succeeded', 'reply_sync_failed',
            'disconnected', 'provider_snapshot_verified'
        )
    ) NOT VALID
"""


EVENT_TYPE_CHECK_BEFORE_PRICEBOOK_SNAPSHOT = """
    ALTER TABLE outreach_sender_account_events
    ADD CONSTRAINT ck_outreach_sender_account_event_type CHECK (
        event_type IN (
            'connected', 'permission_changed', 'preflight_succeeded',
            'preflight_failed', 'reply_sync_succeeded', 'reply_sync_failed',
            'disconnected'
        )
    ) NOT VALID
"""


def upgrade():
    op.execute(
        "ALTER TABLE outreach_sender_account_events "
        "DROP CONSTRAINT IF EXISTS ck_outreach_sender_account_event_type"
    )
    op.execute(EVENT_TYPE_CHECK_WITH_PRICEBOOK_SNAPSHOT)
    op.execute(
        "ALTER TABLE outreach_sender_account_events "
        "VALIDATE CONSTRAINT ck_outreach_sender_account_event_type"
    )


def downgrade():
    op.execute(
        "ALTER TABLE outreach_sender_account_events "
        "DROP CONSTRAINT IF EXISTS ck_outreach_sender_account_event_type"
    )
    # Snapshot events are immutable audit evidence. NOT VALID retains existing
    # rows while restoring the former allowlist for every new event.
    op.execute(EVENT_TYPE_CHECK_BEFORE_PRICEBOOK_SNAPSHOT)
