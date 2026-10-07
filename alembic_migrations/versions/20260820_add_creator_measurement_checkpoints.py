"""add creator tracking plans and measurement checkpoints

Revision ID: 20260820_002
Revises: 20260820_001
Create Date: 2026-08-20 23:30:00.000000
"""

from alembic import op


revision = "20260820_002"
down_revision = "20260820_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        "ALTER TABLE creator_deliverables ADD COLUMN IF NOT EXISTS tracking_json JSONB NOT NULL DEFAULT '{}'::jsonb"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS creator_measurement_checkpoints (
            id UUID PRIMARY KEY,
            deliverable_id UUID NOT NULL REFERENCES creator_deliverables(id) ON DELETE CASCADE,
            checkpoint TEXT NOT NULL,
            due_at TIMESTAMPTZ NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            completed_metric_id UUID REFERENCES creator_placement_metrics(id) ON DELETE SET NULL,
            completed_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_creator_measurement_checkpoint CHECK (checkpoint IN ('24h', '7d', '14d')),
            CONSTRAINT ck_creator_measurement_status CHECK (status IN ('pending', 'completed', 'skipped')),
            UNIQUE (deliverable_id, checkpoint)
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_creator_measurement_due ON creator_measurement_checkpoints(status, due_at)"
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS creator_measurement_checkpoints")
    op.execute("ALTER TABLE creator_deliverables DROP COLUMN IF EXISTS tracking_json")
