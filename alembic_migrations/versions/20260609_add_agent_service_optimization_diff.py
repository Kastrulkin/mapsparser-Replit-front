"""add agent service optimization diff

Revision ID: 20260609_003
Revises: 20260609_002
Create Date: 2026-06-09
"""

from alembic import op


revision = "20260609_003"
down_revision = "20260609_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        ALTER TABLE agent_service_optimization_requests
        ADD COLUMN IF NOT EXISTS diff_json JSONB NOT NULL DEFAULT '[]'::jsonb
        """
    )


def downgrade():
    op.execute(
        """
        ALTER TABLE agent_service_optimization_requests
        DROP COLUMN IF EXISTS diff_json
        """
    )
