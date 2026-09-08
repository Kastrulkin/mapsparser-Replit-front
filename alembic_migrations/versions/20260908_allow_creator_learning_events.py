"""allow creator collaboration learning events

Revision ID: 20260908_001
Revises: 20260906_012
Create Date: 2026-09-08 16:25:00.000000
"""

from alembic import op


revision = "20260908_001"
down_revision = "20260906_012"
branch_labels = None
depends_on = None


WORKSTREAM_CHECK_WITH_CREATORS = """
    ALTER TABLE outreach_learning_events
    ADD CONSTRAINT ck_outreach_learning_workstream CHECK (
        workstream_type IN (
            'localos_sales', 'client_partnership', 'creator_collaboration'
        )
    ) NOT VALID
"""


WORKSTREAM_CHECK_BEFORE_CREATORS = """
    ALTER TABLE outreach_learning_events
    ADD CONSTRAINT ck_outreach_learning_workstream CHECK (
        workstream_type IN ('localos_sales', 'client_partnership')
    ) NOT VALID
"""


def upgrade():
    op.execute(
        "ALTER TABLE outreach_learning_events "
        "DROP CONSTRAINT IF EXISTS ck_outreach_learning_workstream"
    )
    op.execute(WORKSTREAM_CHECK_WITH_CREATORS)
    op.execute(
        "ALTER TABLE outreach_learning_events "
        "VALIDATE CONSTRAINT ck_outreach_learning_workstream"
    )


def downgrade():
    op.execute(
        "ALTER TABLE outreach_learning_events "
        "DROP CONSTRAINT IF EXISTS ck_outreach_learning_workstream"
    )
    # Creator learning events are audit data. Keep existing rows while restoring
    # the previous rule for new records.
    op.execute(WORKSTREAM_CHECK_BEFORE_CREATORS)
