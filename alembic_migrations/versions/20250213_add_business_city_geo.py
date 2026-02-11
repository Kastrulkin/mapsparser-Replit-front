"""add city, geo_lat, geo_lon to businesses

Revision ID: 20250213_001
Revises: 20250212_002
Create Date: 2025-02-13

"""
from alembic import op


revision = "20250213_001"
down_revision = "20250212_002"
branch_labels = None
depends_on = None


def upgrade():
    op.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS city TEXT")
    op.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS geo_lat DOUBLE PRECISION")
    op.execute("ALTER TABLE businesses ADD COLUMN IF NOT EXISTS geo_lon DOUBLE PRECISION")


def downgrade():
    op.execute("ALTER TABLE businesses DROP COLUMN IF EXISTS city")
    op.execute("ALTER TABLE businesses DROP COLUMN IF EXISTS geo_lat")
    op.execute("ALTER TABLE businesses DROP COLUMN IF EXISTS geo_lon")
