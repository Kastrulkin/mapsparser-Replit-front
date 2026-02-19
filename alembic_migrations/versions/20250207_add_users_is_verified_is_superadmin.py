"""add users.is_verified and users.is_superadmin (auth and access control)

Revision ID: 20250207_005
Revises: 20250207_004
Create Date: 2025-02-07

"""
from alembic import op

revision = "20250207_005"
down_revision = "20250207_004"
branch_labels = None
depends_on = None


def upgrade():
    # is_verified: верификация пользователя (email и т.п.), по умолчанию TRUE
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_verified BOOLEAN NOT NULL DEFAULT TRUE
    """)
    op.execute("""
        UPDATE users SET is_verified = TRUE WHERE is_verified IS NULL
    """)
    # is_superadmin: доступ ко всем бизнесам и админ-функциям, по умолчанию FALSE
    op.execute("""
        ALTER TABLE users
        ADD COLUMN IF NOT EXISTS is_superadmin BOOLEAN NOT NULL DEFAULT FALSE
    """)
    op.execute("""
        UPDATE users SET is_superadmin = FALSE WHERE is_superadmin IS NULL
    """)


def downgrade():
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_superadmin")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS is_verified")
