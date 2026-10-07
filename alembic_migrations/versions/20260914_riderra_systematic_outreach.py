"""track systematic Riderra outreach runs and shortage notifications

Revision ID: 20260914_riderra_runs
Revises: 20260914_business_input_city
Create Date: 2026-09-14 15:00:00.000000
"""

from alembic import op


revision = "20260914_riderra_runs"
down_revision = "20260914_business_input_city"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE riderra_outreach_runs (
            id UUID PRIMARY KEY,
            local_date DATE NOT NULL,
            status TEXT NOT NULL,
            target_count INTEGER NOT NULL DEFAULT 0,
            eligible_count INTEGER NOT NULL DEFAULT 0,
            selected_count INTEGER NOT NULL DEFAULT 0,
            queued_count INTEGER NOT NULL DEFAULT 0,
            remaining_daily_capacity INTEGER NOT NULL DEFAULT 0,
            standing_authorization_id UUID,
            batch_authorization_id UUID,
            pricebook_attestation_id UUID,
            exclusion_counts_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            missing_routes_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_code TEXT,
            fingerprint TEXT NOT NULL,
            notification_required BOOLEAN NOT NULL DEFAULT FALSE,
            notified_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_riderra_outreach_run_status CHECK (
                status IN ('ready', 'shortage', 'daily_limit_reached', 'blocked', 'failed')
            ),
            CONSTRAINT ck_riderra_outreach_run_counts CHECK (
                target_count >= 0 AND eligible_count >= 0 AND selected_count >= 0
                AND queued_count >= 0 AND remaining_daily_capacity >= 0
            )
        )
        """
    )
    op.execute("CREATE UNIQUE INDEX uq_riderra_outreach_runs_fingerprint ON riderra_outreach_runs(fingerprint)")
    op.execute("CREATE INDEX idx_riderra_outreach_runs_pending_notice ON riderra_outreach_runs(created_at) WHERE notification_required AND notified_at IS NULL")


def downgrade():
    op.execute("DROP TABLE IF EXISTS riderra_outreach_runs")
