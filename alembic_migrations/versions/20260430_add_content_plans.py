"""add content plans tables

Revision ID: 20260430_001
Revises: 20260422_002
Create Date: 2026-04-30 12:00:00.000000
"""

from alembic import op


revision = "20260430_001"
down_revision = "20260422_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS contentplans (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            network_id TEXT,
            scope_type TEXT NOT NULL DEFAULT 'single_business',
            scope_target_id TEXT,
            title TEXT NOT NULL,
            period_days INTEGER NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            plan_status TEXT NOT NULL DEFAULT 'generated',
            generation_mode TEXT NOT NULL DEFAULT 'manual',
            input_snapshot_json JSONB,
            generated_plan_json JSONB,
            edited_plan_json JSONB,
            published_plan_json JSONB,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_contentplans_scope_type
                CHECK (scope_type IN ('single_business', 'network_parent', 'network_location')),
            CONSTRAINT chk_contentplans_period_days
                CHECK (period_days IN (30, 60, 90)),
            CONSTRAINT chk_contentplans_plan_status
                CHECK (plan_status IN ('draft', 'generated', 'published', 'archived'))
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS contentplanitems (
            id TEXT PRIMARY KEY,
            plan_id TEXT NOT NULL REFERENCES contentplans(id) ON DELETE CASCADE,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            scheduled_for DATE NOT NULL,
            content_type TEXT NOT NULL DEFAULT 'news',
            theme TEXT NOT NULL,
            goal TEXT,
            source_kind TEXT,
            source_ref TEXT,
            seo_keyword TEXT,
            service_id TEXT,
            transaction_id TEXT,
            location_scope TEXT,
            draft_text TEXT,
            status TEXT NOT NULL DEFAULT 'planned',
            usernews_id TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT chk_contentplanitems_status
                CHECK (status IN ('planned', 'draft_generated', 'edited', 'approved', 'published', 'skipped'))
        )
        """
    )

    op.execute("CREATE INDEX IF NOT EXISTS idx_contentplans_business_id ON contentplans(business_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_contentplans_network_id ON contentplans(network_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_contentplans_scope_target_id ON contentplans(scope_target_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_contentplans_plan_status ON contentplans(plan_status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_contentplanitems_plan_id ON contentplanitems(plan_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_contentplanitems_business_id ON contentplanitems(business_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_contentplanitems_scheduled_for ON contentplanitems(scheduled_for)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_contentplanitems_status ON contentplanitems(status)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_contentplanitems_status")
    op.execute("DROP INDEX IF EXISTS idx_contentplanitems_scheduled_for")
    op.execute("DROP INDEX IF EXISTS idx_contentplanitems_business_id")
    op.execute("DROP INDEX IF EXISTS idx_contentplanitems_plan_id")
    op.execute("DROP INDEX IF EXISTS idx_contentplans_plan_status")
    op.execute("DROP INDEX IF EXISTS idx_contentplans_scope_target_id")
    op.execute("DROP INDEX IF EXISTS idx_contentplans_network_id")
    op.execute("DROP INDEX IF EXISTS idx_contentplans_business_id")
    op.execute("DROP TABLE IF EXISTS contentplanitems")
    op.execute("DROP TABLE IF EXISTS contentplans")
