"""Store the owner handoff and its one-time invitation."""
from alembic import op

revision = "20261105_prepared_cabinet"
down_revision = "20261102_manual_review_identity"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS prepared_cabinets (
            business_id TEXT PRIMARY KEY REFERENCES businesses(id) ON DELETE CASCADE,
            owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            materials JSONB NOT NULL,
            seen JSONB NOT NULL DEFAULT '{}'::jsonb,
            invite_hash TEXT UNIQUE,
            invite_expires_at TIMESTAMPTZ,
            activated_at TIMESTAMPTZ
        )
    """)


def downgrade():
    op.execute("DROP TABLE IF EXISTS prepared_cabinets")
