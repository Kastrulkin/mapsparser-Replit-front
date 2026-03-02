"""add selected channel to prospecting leads

Revision ID: 20260302_add_prospecting_selected_channel
Revises: 20260302_add_outreach_search_jobs
Create Date: 2026-03-02 18:05:00.000000
"""

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "20260302_002"
down_revision = "20260302_001"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    has_table = bool(
        bind.execute(
            text("SELECT to_regclass(:tbl) IS NOT NULL"),
            {"tbl": "public.prospectingleads"},
        ).scalar()
    )
    if has_table:
        op.execute(
            """
            ALTER TABLE prospectingleads
            ADD COLUMN IF NOT EXISTS selected_channel VARCHAR(32)
            """
        )


def downgrade():
    bind = op.get_bind()
    has_table = bool(
        bind.execute(
            text("SELECT to_regclass(:tbl) IS NOT NULL"),
            {"tbl": "public.prospectingleads"},
        ).scalar()
    )
    if has_table:
        op.execute(
            """
            ALTER TABLE prospectingleads
            DROP COLUMN IF EXISTS selected_channel
            """
        )
