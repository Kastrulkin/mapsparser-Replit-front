"""add businessprofiles table for client-info owner data

Revision ID: 20250207_009
Revises: 20250207_008
Create Date: 2025-02-07

"""
from alembic import op


revision = "20250207_009"
down_revision = "20250207_008"
branch_labels = None
depends_on = None


def upgrade():
    # Таблица профилей бизнеса (контактные данные для /api/client-info)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS businessprofiles (
            business_id TEXT PRIMARY KEY,
            contact_name TEXT,
            contact_phone TEXT,
            contact_email TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            CONSTRAINT fk_businessprofiles_business_id
                FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE
        )
        """
    )


def downgrade():
    op.execute("DROP TABLE IF EXISTS businessprofiles")

