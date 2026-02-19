"""expand businesses table with rich fields

Revision ID: 20250210_001
Revises: 20250207_009
Create Date: 2025-02-10

"""
from alembic import op


revision = "20250210_001"
down_revision = "20250207_009"
branch_labels = None
depends_on = None


def upgrade():
    # Расширяем таблицу businesses дополнительными полями (идемпотентно)
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS description TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS industry TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS phone TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS email TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS website TEXT
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS rating NUMERIC
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS reviews_count INTEGER
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS categories JSONB
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS hours JSONB
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS hours_full JSONB
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS geo JSONB
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS external_ids JSONB
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS last_parsed_at TIMESTAMP
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS subscription_tier TEXT DEFAULT 'trial'
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS subscription_status TEXT DEFAULT 'active'
        """
    )

    # Индексы (идемпотентно)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_businesses_owner_id
        ON businesses(owner_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_businesses_network_id
        ON businesses(network_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_businesses_last_parsed_at
        ON businesses(last_parsed_at)
        """
    )


def downgrade():
    # Удаляем добавленные индексы
    op.execute(
        """
        DROP INDEX IF EXISTS idx_businesses_last_parsed_at
        """
    )
    op.execute(
        """
        DROP INDEX IF EXISTS idx_businesses_network_id
        """
    )
    # idx_businesses_owner_id создавался и в предыдущей миграции, поэтому здесь не трогаем,
    # чтобы не ломать обратную совместимость.

    # Удаляем только колонки, добавленные в этой миграции
    op.execute(
        """
        ALTER TABLE businesses
        DROP COLUMN IF EXISTS subscription_status,
        DROP COLUMN IF EXISTS subscription_tier,
        DROP COLUMN IF EXISTS last_parsed_at,
        DROP COLUMN IF EXISTS external_ids,
        DROP COLUMN IF EXISTS geo,
        DROP COLUMN IF EXISTS hours_full,
        DROP COLUMN IF EXISTS hours,
        DROP COLUMN IF EXISTS categories,
        DROP COLUMN IF EXISTS reviews_count,
        DROP COLUMN IF EXISTS rating,
        DROP COLUMN IF EXISTS website,
        DROP COLUMN IF EXISTS email,
        DROP COLUMN IF EXISTS phone,
        DROP COLUMN IF EXISTS industry,
        DROP COLUMN IF EXISTS description
        """
    )

