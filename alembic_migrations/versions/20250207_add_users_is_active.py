"""add users.is_active for account blocking

Revision ID: 20250207_004
Revises: 20250207_003
Create Date: 2025-02-07

"""
from alembic import op

revision = "20250207_004"
down_revision = "20250207_003"
branch_labels = None
depends_on = None


def upgrade():
    # Добавляем колонку is_active: блокировка пользователя (например, при неоплате).
    # Существующие пользователи считаются активными (TRUE).
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE
    """)
    op.execute("""
        UPDATE users SET is_active = TRUE WHERE is_active IS NULL
    """)


def downgrade():
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_active")
