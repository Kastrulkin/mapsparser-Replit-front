"""add usersessions table for auth (login tokens)

Revision ID: 20250207_006
Revises: 20250207_005
Create Date: 2025-02-07

"""
from alembic import op

revision = "20250207_006"
down_revision = "20250207_005"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("""
        CREATE TABLE IF NOT EXISTS usersessions (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            token TEXT UNIQUE NOT NULL,
            expires_at TIMESTAMP NOT NULL,
            ip_address TEXT,
            user_agent TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_usersessions_token ON usersessions(token)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_usersessions_expires_at ON usersessions(expires_at)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_usersessions_user_id ON usersessions(user_id)")


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_usersessions_user_id")
    op.execute("DROP INDEX IF EXISTS idx_usersessions_expires_at")
    op.execute("DROP INDEX IF EXISTS idx_usersessions_token")
    op.execute("DROP TABLE IF EXISTS usersessions")
