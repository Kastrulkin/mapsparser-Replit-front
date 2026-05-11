"""add registration consent and email verification fields

Revision ID: 20260511_001
Revises: 20260507_001
Create Date: 2026-05-11
"""

from alembic import op


revision = "20260511_001"
down_revision = "20260507_001"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS email_verified_at TIMESTAMP")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS personal_data_consent_at TIMESTAMP")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS personal_data_consent_version TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS privacy_accepted_at TIMESTAMP")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS terms_accepted_at TIMESTAMP")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS consent_ip TEXT")
    op.execute("ALTER TABLE users ADD COLUMN IF NOT EXISTS consent_user_agent TEXT")
    op.execute("ALTER TABLE users ALTER COLUMN is_verified SET DEFAULT FALSE")
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_users_verification_token
        ON users(verification_token)
        WHERE verification_token IS NOT NULL
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_users_personal_data_consent_at
        ON users(personal_data_consent_at)
        """
    )
    op.execute(
        """
        UPDATE users
        SET verification_token = md5(random()::text || clock_timestamp()::text || id::text)
            || md5(random()::text || email::text || clock_timestamp()::text),
            updated_at = COALESCE(updated_at, CURRENT_TIMESTAMP)
        WHERE is_active IS TRUE
          AND (password_hash IS NULL OR TRIM(password_hash) = '')
          AND (verification_token IS NULL OR TRIM(verification_token) = '')
        """
    )


def downgrade():
    op.execute("DROP INDEX IF EXISTS idx_users_personal_data_consent_at")
    op.execute("DROP INDEX IF EXISTS idx_users_verification_token")
    op.execute("ALTER TABLE users ALTER COLUMN is_verified SET DEFAULT TRUE")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS consent_user_agent")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS consent_ip")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS terms_accepted_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS privacy_accepted_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS personal_data_consent_version")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS personal_data_consent_at")
    op.execute("ALTER TABLE users DROP COLUMN IF EXISTS email_verified_at")
