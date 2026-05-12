"""add finance first step tables

Revision ID: 20260512_001
Revises: 20260511_001
Create Date: 2026-05-12
"""

from alembic import op


revision = "20260512_001"
down_revision = "20260511_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_entries (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            date DATE NOT NULL,
            type TEXT NOT NULL,
            category TEXT,
            amount NUMERIC(14, 2) NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'manual',
            comment TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_service_metrics (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            service_name TEXT NOT NULL,
            category TEXT,
            revenue NUMERIC(14, 2) NOT NULL DEFAULT 0,
            visits_count INTEGER NOT NULL DEFAULT 0,
            avg_price NUMERIC(14, 2) NOT NULL DEFAULT 0,
            duration_minutes INTEGER NOT NULL DEFAULT 0,
            material_cost NUMERIC(14, 2) NOT NULL DEFAULT 0,
            staff_payout NUMERIC(14, 2) NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_staff_metrics (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            staff_name TEXT NOT NULL,
            role TEXT,
            revenue NUMERIC(14, 2) NOT NULL DEFAULT 0,
            visits_count INTEGER NOT NULL DEFAULT 0,
            booked_minutes INTEGER NOT NULL DEFAULT 0,
            available_minutes INTEGER NOT NULL DEFAULT 0,
            no_show_count INTEGER NOT NULL DEFAULT 0,
            rebooking_count INTEGER NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_workplaces (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            name TEXT NOT NULL,
            type TEXT NOT NULL DEFAULT 'other',
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_workplace_metrics (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            workplace_id TEXT,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            available_minutes INTEGER NOT NULL DEFAULT 0,
            booked_minutes INTEGER NOT NULL DEFAULT 0,
            revenue NUMERIC(14, 2) NOT NULL DEFAULT 0,
            gross_profit NUMERIC(14, 2) NOT NULL DEFAULT 0,
            source TEXT NOT NULL DEFAULT 'manual',
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_snapshots (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            period_start DATE NOT NULL,
            period_end DATE NOT NULL,
            calculated_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            data_quality_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_import_batches (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            source_type TEXT NOT NULL DEFAULT 'file',
            status TEXT NOT NULL DEFAULT 'pending',
            file_name TEXT,
            file_hash TEXT,
            rows_total INTEGER NOT NULL DEFAULT 0,
            rows_imported INTEGER NOT NULL DEFAULT 0,
            rows_skipped INTEGER NOT NULL DEFAULT 0,
            rows_failed INTEGER NOT NULL DEFAULT 0,
            mapping_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            error_log JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            completed_at TIMESTAMPTZ
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_crm_connections (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            provider TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'disconnected',
            display_name TEXT,
            auth_data_encrypted TEXT,
            settings_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            last_sync_at TIMESTAMPTZ,
            sync_status TEXT,
            error_log JSONB NOT NULL DEFAULT '[]'::jsonb,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_kpi_thresholds (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            profile TEXT NOT NULL DEFAULT 'service_business',
            metric_key TEXT NOT NULL,
            green_min NUMERIC(10, 2),
            green_max NUMERIC(10, 2),
            yellow_min NUMERIC(10, 2),
            yellow_max NUMERIC(10, 2),
            red_rule TEXT,
            label TEXT,
            unit TEXT,
            is_active BOOLEAN NOT NULL DEFAULT TRUE,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS finance_action_logs (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            recommendation_code TEXT NOT NULL,
            action_key TEXT NOT NULL,
            action_bucket TEXT NOT NULL,
            action_text TEXT NOT NULL,
            status TEXT NOT NULL DEFAULT 'pending',
            period_start DATE,
            period_end DATE,
            completed_at TIMESTAMPTZ,
            created_by TEXT,
            created_at TIMESTAMPTZ DEFAULT NOW(),
            updated_at TIMESTAMPTZ DEFAULT NOW()
        )
        """
    )
    op.execute("ALTER TABLE finance_entries ADD COLUMN IF NOT EXISTS import_batch_id TEXT")
    op.execute("ALTER TABLE finance_entries ADD COLUMN IF NOT EXISTS external_id TEXT")
    op.execute("ALTER TABLE finance_entries ADD COLUMN IF NOT EXISTS duplicate_key TEXT")
    op.execute("ALTER TABLE finance_service_metrics ADD COLUMN IF NOT EXISTS import_batch_id TEXT")
    op.execute("ALTER TABLE finance_service_metrics ADD COLUMN IF NOT EXISTS external_id TEXT")
    op.execute("ALTER TABLE finance_service_metrics ADD COLUMN IF NOT EXISTS duplicate_key TEXT")
    op.execute("ALTER TABLE finance_staff_metrics ADD COLUMN IF NOT EXISTS import_batch_id TEXT")
    op.execute("ALTER TABLE finance_staff_metrics ADD COLUMN IF NOT EXISTS external_id TEXT")
    op.execute("ALTER TABLE finance_staff_metrics ADD COLUMN IF NOT EXISTS duplicate_key TEXT")
    op.execute("ALTER TABLE finance_workplace_metrics ADD COLUMN IF NOT EXISTS import_batch_id TEXT")
    op.execute("ALTER TABLE finance_workplace_metrics ADD COLUMN IF NOT EXISTS external_id TEXT")
    op.execute("ALTER TABLE finance_workplace_metrics ADD COLUMN IF NOT EXISTS duplicate_key TEXT")
    op.execute("CREATE INDEX IF NOT EXISTS idx_finance_entries_business_date ON finance_entries(business_id, date)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_finance_service_metrics_business_period ON finance_service_metrics(business_id, period_start, period_end)"
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_finance_staff_metrics_business_period ON finance_staff_metrics(business_id, period_start, period_end)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_finance_workplaces_business ON finance_workplaces(business_id, is_active)")
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_finance_workplace_metrics_business_period ON finance_workplace_metrics(business_id, period_start, period_end)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_finance_snapshots_business_period ON finance_snapshots(business_id, period_start, period_end)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_finance_import_batches_business ON finance_import_batches(business_id, created_at DESC)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_finance_crm_connections_business ON finance_crm_connections(business_id, provider, status)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_crm_connections_business_provider ON finance_crm_connections(business_id, provider)"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_finance_kpi_thresholds_business ON finance_kpi_thresholds(business_id, is_active)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_kpi_thresholds_business_metric ON finance_kpi_thresholds(business_id, metric_key) WHERE is_active = TRUE"
    )
    op.execute("CREATE INDEX IF NOT EXISTS idx_finance_action_logs_business ON finance_action_logs(business_id, updated_at DESC)")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_action_logs_business_action ON finance_action_logs(business_id, action_key)"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_entries_duplicate_key ON finance_entries(business_id, duplicate_key) WHERE duplicate_key IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_service_metrics_duplicate_key ON finance_service_metrics(business_id, duplicate_key) WHERE duplicate_key IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_staff_metrics_duplicate_key ON finance_staff_metrics(business_id, duplicate_key) WHERE duplicate_key IS NOT NULL"
    )
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS uq_finance_workplace_metrics_duplicate_key ON finance_workplace_metrics(business_id, duplicate_key) WHERE duplicate_key IS NOT NULL"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS uq_finance_workplace_metrics_duplicate_key")
    op.execute("DROP INDEX IF EXISTS uq_finance_action_logs_business_action")
    op.execute("DROP INDEX IF EXISTS idx_finance_action_logs_business")
    op.execute("DROP INDEX IF EXISTS uq_finance_kpi_thresholds_business_metric")
    op.execute("DROP INDEX IF EXISTS idx_finance_kpi_thresholds_business")
    op.execute("DROP INDEX IF EXISTS uq_finance_crm_connections_business_provider")
    op.execute("DROP INDEX IF EXISTS idx_finance_crm_connections_business")
    op.execute("DROP INDEX IF EXISTS uq_finance_staff_metrics_duplicate_key")
    op.execute("DROP INDEX IF EXISTS uq_finance_service_metrics_duplicate_key")
    op.execute("DROP INDEX IF EXISTS uq_finance_entries_duplicate_key")
    op.execute("DROP INDEX IF EXISTS idx_finance_import_batches_business")
    op.execute("DROP INDEX IF EXISTS idx_finance_snapshots_business_period")
    op.execute("DROP INDEX IF EXISTS idx_finance_workplace_metrics_business_period")
    op.execute("DROP INDEX IF EXISTS idx_finance_workplaces_business")
    op.execute("DROP INDEX IF EXISTS idx_finance_staff_metrics_business_period")
    op.execute("DROP INDEX IF EXISTS idx_finance_service_metrics_business_period")
    op.execute("DROP INDEX IF EXISTS idx_finance_entries_business_date")
    op.execute("DROP TABLE IF EXISTS finance_snapshots")
    op.execute("DROP TABLE IF EXISTS finance_action_logs")
    op.execute("DROP TABLE IF EXISTS finance_kpi_thresholds")
    op.execute("DROP TABLE IF EXISTS finance_crm_connections")
    op.execute("DROP TABLE IF EXISTS finance_import_batches")
    op.execute("DROP TABLE IF EXISTS finance_workplace_metrics")
    op.execute("DROP TABLE IF EXISTS finance_workplaces")
    op.execute("DROP TABLE IF EXISTS finance_staff_metrics")
    op.execute("DROP TABLE IF EXISTS finance_service_metrics")
    op.execute("DROP TABLE IF EXISTS finance_entries")
