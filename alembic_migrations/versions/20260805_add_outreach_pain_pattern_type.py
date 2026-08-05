"""allow versioned outreach pain libraries

Revision ID: 20260805_003
Revises: 20260805_002
Create Date: 2026-08-05
"""

from alembic import op


revision = "20260805_003"
down_revision = "20260805_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE outreach_knowledge_patterns DROP CONSTRAINT IF EXISTS chk_outreach_pattern_type")
    op.execute(
        "ALTER TABLE outreach_knowledge_patterns ADD CONSTRAINT chk_outreach_pattern_type "
        "CHECK (pattern_type IN ('signal', 'bridge', 'offer', 'sequence', 'pain'))"
    )


def downgrade():
    op.execute("DELETE FROM outreach_knowledge_patterns WHERE pattern_type = 'pain'")
    op.execute("ALTER TABLE outreach_knowledge_patterns DROP CONSTRAINT IF EXISTS chk_outreach_pattern_type")
    op.execute(
        "ALTER TABLE outreach_knowledge_patterns ADD CONSTRAINT chk_outreach_pattern_type "
        "CHECK (pattern_type IN ('signal', 'bridge', 'offer', 'sequence'))"
    )
