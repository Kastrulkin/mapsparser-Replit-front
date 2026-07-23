"""extend operator actions for scope-aware mobile previews

Revision ID: 20260723_002
Revises: 20260723_001
"""

from alembic import op


revision = "20260723_002"
down_revision = "20260723_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE operatoractions ALTER COLUMN business_id DROP NOT NULL")
    op.execute("ALTER TABLE operatoractions ADD COLUMN IF NOT EXISTS scope_type TEXT NOT NULL DEFAULT 'business'")
    op.execute("ALTER TABLE operatoractions ADD COLUMN IF NOT EXISTS scope_id TEXT")
    op.execute("ALTER TABLE operatoractions ADD COLUMN IF NOT EXISTS target_business_ids_json JSONB NOT NULL DEFAULT '[]'::jsonb")
    op.execute("ALTER TABLE operatoractions ADD COLUMN IF NOT EXISTS preview_json JSONB NOT NULL DEFAULT '{}'::jsonb")
    op.execute("ALTER TABLE operatoractions ADD COLUMN IF NOT EXISTS estimated_credits INTEGER NOT NULL DEFAULT 0")
    op.execute("ALTER TABLE operatoractions ADD COLUMN IF NOT EXISTS external_effects BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE operatoractions ADD COLUMN IF NOT EXISTS is_mass_action BOOLEAN NOT NULL DEFAULT FALSE")
    op.execute("ALTER TABLE operatoractions ADD COLUMN IF NOT EXISTS expires_at TIMESTAMPTZ")
    op.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS idx_operatoractions_user_idempotency "
        "ON operatoractions(user_id, idempotency_key)"
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_operatoractions_user_idempotency")
    op.execute("ALTER TABLE operatoractions DROP COLUMN IF EXISTS expires_at")
    op.execute("ALTER TABLE operatoractions DROP COLUMN IF EXISTS is_mass_action")
    op.execute("ALTER TABLE operatoractions DROP COLUMN IF EXISTS external_effects")
    op.execute("ALTER TABLE operatoractions DROP COLUMN IF EXISTS estimated_credits")
    op.execute("ALTER TABLE operatoractions DROP COLUMN IF EXISTS preview_json")
    op.execute("ALTER TABLE operatoractions DROP COLUMN IF EXISTS target_business_ids_json")
    op.execute("ALTER TABLE operatoractions DROP COLUMN IF EXISTS scope_id")
    op.execute("ALTER TABLE operatoractions DROP COLUMN IF EXISTS scope_type")
