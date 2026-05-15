"""add average ticket module tables

Revision ID: 20260515_001
Revises: 20260507_add_service_optimization_trace_columns
Create Date: 2026-05-15
"""

from alembic import op


revision = "20260515_001"
down_revision = "20260514_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS averageticketmatrices (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            status TEXT NOT NULL DEFAULT 'draft',
            source_services_hash TEXT,
            matrix_json JSONB NOT NULL DEFAULT '{}'::jsonb,
            generated_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        "CREATE INDEX IF NOT EXISTS idx_averageticketmatrices_business_id ON averageticketmatrices(business_id, generated_at DESC)"
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS averageticketevents (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            matrix_id TEXT REFERENCES averageticketmatrices(id) ON DELETE SET NULL,
            link_id TEXT,
            package_id TEXT,
            booking_id TEXT,
            main_service_id TEXT REFERENCES userservices(id) ON DELETE SET NULL,
            addon_service_id TEXT REFERENCES userservices(id) ON DELETE SET NULL,
            event_type TEXT NOT NULL,
            event_date DATE DEFAULT CURRENT_DATE,
            amount NUMERIC(12, 2),
            master_id TEXT,
            client_name TEXT,
            notes TEXT,
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_averageticketevents_business_date
        ON averageticketevents(business_id, event_date DESC, created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_averageticketevents_booking
        ON averageticketevents(business_id, booking_id)
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS averageticketpackages (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL REFERENCES businesses(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            service_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
            service_names JSONB NOT NULL DEFAULT '[]'::jsonb,
            base_total NUMERIC(12, 2) DEFAULT 0,
            package_price NUMERIC(12, 2),
            bonus_text TEXT,
            positioning TEXT,
            script TEXT,
            status TEXT NOT NULL DEFAULT 'draft',
            created_by TEXT REFERENCES users(id) ON DELETE SET NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_averageticketpackages_business_status
        ON averageticketpackages(business_id, status)
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_averageticketpackages_business_status")
    op.execute("DROP TABLE IF EXISTS averageticketpackages")
    op.execute("DROP INDEX IF EXISTS idx_averageticketevents_booking")
    op.execute("DROP INDEX IF EXISTS idx_averageticketevents_business_date")
    op.execute("DROP TABLE IF EXISTS averageticketevents")
    op.execute("DROP INDEX IF EXISTS idx_averageticketmatrices_business_id")
    op.execute("DROP TABLE IF EXISTS averageticketmatrices")
