"""add consent-gated material download requests

Revision ID: 20260813_001
Revises: 20260810_003_founder
Create Date: 2026-08-13
"""

from alembic import op


revision = "20260813_001"
down_revision = "20260810_003_founder"
branch_labels = None
depends_on = None


def upgrade():
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS materialdownloadrequests (
            id UUID PRIMARY KEY,
            email TEXT NOT NULL,
            material_slug TEXT NOT NULL,
            source_language TEXT NOT NULL DEFAULT 'ru',
            personal_data_consent BOOLEAN NOT NULL DEFAULT FALSE,
            personal_data_consent_version TEXT NOT NULL,
            personal_data_consent_at TIMESTAMPTZ NOT NULL,
            consent_ip TEXT,
            consent_user_agent TEXT,
            downloaded_at TIMESTAMPTZ,
            created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
            CONSTRAINT ck_material_download_consent CHECK (personal_data_consent = TRUE)
        )
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_material_download_requests_email_created
        ON materialdownloadrequests(LOWER(email), created_at DESC)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_material_download_requests_ip_created
        ON materialdownloadrequests(consent_ip, created_at DESC)
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS materialdownloadrequests")
