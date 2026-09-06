"""Move the bounded second slice of runtime DDL into Alembic.

Revision ID: 20260906_004
Revises: 20260906_003
"""

from alembic import op


revision = "20260906_004"
down_revision = "20260906_003"
branch_labels = None
depends_on = None


def upgrade():
    # This table was previously created by parsing request and worker paths.
    # The other tables retired in this slice already have complete migrations;
    # their application helpers now only assert that schema contract.
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS parsingruntimeconfig (
            key TEXT PRIMARY KEY,
            value TEXT NOT NULL,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def downgrade():
    # Keep an administrator's parsing preference on code rollback.
    pass
