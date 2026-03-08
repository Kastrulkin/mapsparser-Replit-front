"""add business linkage to prospecting leads

Revision ID: 20260305_001
Revises: 20260302_006
Create Date: 2026-03-05 18:15:00.000000
"""

from alembic import op
from sqlalchemy import text


# revision identifiers, used by Alembic.
revision = "20260305_001"
down_revision = "20260302_006"
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
    if not has_table:
        return

    op.execute(
        """
        ALTER TABLE prospectingleads
        ADD COLUMN IF NOT EXISTS business_id TEXT
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_prospectingleads_business_id
        ON prospectingleads(business_id)
        """
    )
    business_columns = {
        row[0]
        for row in bind.execute(
            text(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = 'businesses'
                """
            )
        ).fetchall()
    }

    if "yandex_org_id" in business_columns:
        op.execute(
            """
            UPDATE prospectingleads l
            SET business_id = b.id
            FROM businesses b
            WHERE l.business_id IS NULL
              AND l.source_external_id IS NOT NULL
              AND NULLIF(TRIM(l.source_external_id), '') IS NOT NULL
              AND b.yandex_org_id = l.source_external_id
            """
        )

    if "yandex_url" in business_columns:
        op.execute(
            """
            UPDATE prospectingleads l
            SET business_id = b.id
            FROM businesses b
            WHERE l.business_id IS NULL
              AND l.source_url IS NOT NULL
              AND NULLIF(TRIM(l.source_url), '') IS NOT NULL
              AND b.yandex_url = l.source_url
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
    if not has_table:
        return

    op.execute("DROP INDEX IF EXISTS idx_prospectingleads_business_id")
    op.execute("ALTER TABLE prospectingleads DROP COLUMN IF EXISTS business_id")
