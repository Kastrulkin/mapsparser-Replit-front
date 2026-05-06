"""add service regeneration jobs

Revision ID: 20260505_002
Revises: 20260505_001
Create Date: 2026-05-05 21:05:00.000000
"""

from alembic import op


revision = "20260505_002"
down_revision = "20260505_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS serviceregenerationjobs (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL,
            business_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'awaiting_confirmation',
            requested_by TEXT NOT NULL DEFAULT 'ui',
            limit_count INTEGER NOT NULL DEFAULT 10,
            total_problem_count INTEGER NOT NULL DEFAULT 0,
            selected_count INTEGER NOT NULL DEFAULT 0,
            fixed_count INTEGER NOT NULL DEFAULT 0,
            failed_count INTEGER NOT NULL DEFAULT 0,
            manual_review_count INTEGER NOT NULL DEFAULT 0,
            remaining_count INTEGER,
            remaining_after_batch INTEGER NOT NULL DEFAULT 0,
            confirmation_required BOOLEAN NOT NULL DEFAULT TRUE,
            cooldown_until TIMESTAMPTZ,
            message TEXT,
            summary_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            started_at TIMESTAMPTZ,
            finished_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS serviceregenerationjobitems (
            id TEXT PRIMARY KEY,
            job_id TEXT NOT NULL REFERENCES serviceregenerationjobs(id) ON DELETE CASCADE,
            service_id TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'queued',
            attempt_no INTEGER NOT NULL DEFAULT 0,
            issue_codes_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            issue_labels_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            keyword_score_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            instructions TEXT,
            before_optimized_name TEXT,
            before_optimized_description TEXT,
            after_optimized_name TEXT,
            after_optimized_description TEXT,
            after_issue_labels_json JSONB NOT NULL DEFAULT '[]'::jsonb,
            error TEXT,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
        )
        """
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_serviceregenerationjobs_business_status ON serviceregenerationjobs (business_id, status, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_serviceregenerationjobs_user_created ON serviceregenerationjobs (user_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_serviceregenerationjobitems_job ON serviceregenerationjobitems (job_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_serviceregenerationjobitems_service_created ON serviceregenerationjobitems (service_id, created_at DESC)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS serviceregenerationjobitems")
    op.execute("DROP TABLE IF EXISTS serviceregenerationjobs")
