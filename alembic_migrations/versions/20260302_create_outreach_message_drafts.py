"""create outreach message drafts and learning examples

Revision ID: 20260302_004
Revises: 20260302_003
Create Date: 2026-03-02 21:10:00.000000
"""

from alembic import op


# revision identifiers, used by Alembic.
revision = "20260302_004"
down_revision = "20260302_003"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreachmessagedrafts (
            id TEXT PRIMARY KEY,
            lead_id TEXT NOT NULL REFERENCES prospectingleads(id) ON DELETE CASCADE,
            channel TEXT NOT NULL,
            angle_type TEXT,
            tone TEXT,
            status TEXT NOT NULL DEFAULT 'generated',
            generated_text TEXT NOT NULL,
            edited_text TEXT,
            approved_text TEXT,
            learning_note_json JSONB,
            created_by TEXT,
            approved_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_outreachmessagedrafts_lead_id ON outreachmessagedrafts(lead_id)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_outreachmessagedrafts_status ON outreachmessagedrafts(status)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS outreachlearningexamples (
            id TEXT PRIMARY KEY,
            example_type TEXT NOT NULL,
            lead_id TEXT REFERENCES prospectingleads(id) ON DELETE SET NULL,
            input_text TEXT,
            output_text TEXT,
            metadata_json JSONB,
            created_by TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_outreachlearningexamples_type ON outreachlearningexamples(example_type)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_outreachlearningexamples_type")
    op.execute("DROP TABLE IF EXISTS outreachlearningexamples")
    op.execute("DROP INDEX IF EXISTS idx_outreachmessagedrafts_status")
    op.execute("DROP INDEX IF EXISTS idx_outreachmessagedrafts_lead_id")
    op.execute("DROP TABLE IF EXISTS outreachmessagedrafts")
