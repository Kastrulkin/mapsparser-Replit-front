"""allow editorial correction outreach learning events

Revision ID: 20260724_001
Revises: 20260723_002
Create Date: 2026-07-24 19:20:00.000000
"""

from alembic import op


revision = "20260724_001"
down_revision = "20260723_002"
branch_labels = None
depends_on = None


OUTCOME_CHECK_WITH_EDITORIAL_CORRECTION = """
    ALTER TABLE outreach_learning_events
    ADD CONSTRAINT ck_outreach_learning_outcome CHECK (
        outcome_type IN (
            'sent', 'delivered', 'delivery_failed', 'replied',
            'positive_reply', 'question', 'hard_no', 'unsubscribe',
            'complaint', 'meeting_booked', 'converted', 'no_reply',
            'interested', 'call_planned', 'contacts_exchanged',
            'pilot_agreed', 'campaign_launched', 'joint_project',
            'recurring_partnership', 'not_relevant', 'lost',
            'editorial_correction'
        )
    )
"""


OUTCOME_CHECK_BEFORE_EDITORIAL_CORRECTION = """
    ALTER TABLE outreach_learning_events
    ADD CONSTRAINT ck_outreach_learning_outcome CHECK (
        outcome_type IN (
            'sent', 'delivered', 'delivery_failed', 'replied',
            'positive_reply', 'question', 'hard_no', 'unsubscribe',
            'complaint', 'meeting_booked', 'converted', 'no_reply',
            'interested', 'call_planned', 'contacts_exchanged',
            'pilot_agreed', 'campaign_launched', 'joint_project',
            'recurring_partnership', 'not_relevant', 'lost'
        )
    ) NOT VALID
"""


def upgrade():
    op.execute(
        "ALTER TABLE outreach_learning_events "
        "DROP CONSTRAINT IF EXISTS ck_outreach_learning_outcome"
    )
    op.execute(OUTCOME_CHECK_WITH_EDITORIAL_CORRECTION)


def downgrade():
    op.execute(
        "ALTER TABLE outreach_learning_events "
        "DROP CONSTRAINT IF EXISTS ck_outreach_learning_outcome"
    )
    # Historical editorial corrections are audit data and must not be deleted on
    # downgrade. NOT VALID keeps those rows while restoring the previous rule for
    # new records.
    op.execute(OUTCOME_CHECK_BEFORE_EDITORIAL_CORRECTION)
