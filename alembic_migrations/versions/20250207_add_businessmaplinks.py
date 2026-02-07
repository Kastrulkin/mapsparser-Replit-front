"""add businessmaplinks for /api/client-info

Revision ID: 20250207_003
Revises: 20250207_002
Create Date: 2025-02-07

"""
from alembic import op

revision = "20250207_003"
down_revision = "20250207_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS businessmaplinks (
            id TEXT PRIMARY KEY,
            user_id TEXT,
            business_id TEXT,
            url TEXT,
            map_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_businessmaplinks_business_id ON businessmaplinks(business_id)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_businessmaplinks_business_id")
    op.execute("DROP TABLE IF EXISTS businessmaplinks")
