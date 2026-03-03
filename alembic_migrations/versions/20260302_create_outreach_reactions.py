"""create outreach reactions

Revision ID: 20260302_006
Revises: 20260302_005
Create Date: 2026-03-02 23:58:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260302_006"
down_revision = "20260302_005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreachreactions (
            id TEXT PRIMARY KEY,
            queue_id TEXT NOT NULL REFERENCES outreachsendqueue(id) ON DELETE CASCADE,
            lead_id TEXT NOT NULL REFERENCES prospectingleads(id) ON DELETE CASCADE,
            raw_reply TEXT,
            classified_outcome TEXT NOT NULL,
            confidence DOUBLE PRECISION,
            human_confirmed_outcome TEXT,
            note TEXT,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_outreachreactions_queue_created ON outreachreactions(queue_id, created_at DESC)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_outreachreactions_outcome ON outreachreactions(classified_outcome)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_outreachreactions_outcome")
    op.execute("DROP INDEX IF EXISTS idx_outreachreactions_queue_created")
    op.execute("DROP TABLE IF EXISTS outreachreactions")
