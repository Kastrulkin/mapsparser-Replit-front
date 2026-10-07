"""Record retirement of sales-room runtime DDL.

Revision ID: 20260906_012
Revises: 20260906_011
"""


revision = "20260906_012"
down_revision = "20260906_011"
branch_labels = None
depends_on = None


def upgrade():
    # The tables and compatibility columns are already owned by the preceding
    # sales-room Alembic migrations. This revision marks the read-only cutover.
    pass


def downgrade():
    pass
