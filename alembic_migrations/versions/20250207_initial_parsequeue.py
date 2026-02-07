"""initial: users, businesses, parsequeue for worker

Revision ID: 20250207_001
Revises:
Create Date: 2025-02-07

"""
from alembic import op
import sqlalchemy as sa

revision = "20250207_001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Минимальные users и businesses для FK; runtime использует lowercase имена в Postgres
    op.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT,
            name TEXT,
            phone TEXT,
            password_hash TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS businesses (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL,
            name TEXT,
            business_type TEXT,
            address TEXT,
            working_hours TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("""
        CREATE TABLE IF NOT EXISTS parsequeue (
            id TEXT PRIMARY KEY,
            url TEXT,
            user_id TEXT NOT NULL,
            business_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            task_type TEXT DEFAULT 'parse_card',
            account_id TEXT,
            source TEXT,
            retry_after TIMESTAMP,
            error_message TEXT,
            captcha_required INTEGER DEFAULT 0,
            captcha_url TEXT,
            captcha_session_id TEXT,
            captcha_started_at TEXT,
            captcha_status TEXT,
            resume_requested INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_parsequeue_status ON parsequeue(status)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_parsequeue_business_id ON parsequeue(business_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_parsequeue_user_id ON parsequeue(user_id)")
    op.execute("CREATE INDEX IF NOT EXISTS idx_parsequeue_created_at ON parsequeue(created_at)")


def downgrade():
    op.execute("DROP TABLE IF EXISTS parsequeue")
    op.execute("DROP TABLE IF EXISTS businesses")
    op.execute("DROP TABLE IF EXISTS users")
