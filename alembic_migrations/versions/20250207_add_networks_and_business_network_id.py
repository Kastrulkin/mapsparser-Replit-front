"""add networks table and businesses.network_id

Revision ID: 20250207_007
Revises: 20250207_006
Create Date: 2025-02-07

"""
from alembic import op

revision = "20250207_007"
down_revision = "20250207_006"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Таблица networks (идемпотентно: IF NOT EXISTS)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS networks (
            id TEXT PRIMARY KEY,
            owner_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            description TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Индекс по owner_id (если его ещё нет)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_networks_owner_id ON networks(owner_id)
        """
    )

    # 2) Колонка businesses.network_id (идемпотентно)
    op.execute(
        """
        ALTER TABLE businesses
        ADD COLUMN IF NOT EXISTS network_id TEXT
        """
    )

    # 3) Внешний ключ businesses.network_id -> networks.id (ON DELETE SET NULL)
    # Добавляем только если такого ограничения ещё нет.
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints tc
                WHERE tc.constraint_name = 'fk_businesses_network_id_networks'
                  AND tc.table_name = 'businesses'
                  AND tc.constraint_type = 'FOREIGN KEY'
            ) THEN
                ALTER TABLE businesses
                ADD CONSTRAINT fk_businesses_network_id_networks
                FOREIGN KEY (network_id) REFERENCES networks(id) ON DELETE SET NULL;
            END IF;
        END$$;
        """
    )

    # 4) Индекс по businesses.network_id (для быстрых выборок по сети)
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_businesses_network_id ON businesses(network_id)
        """
    )


def downgrade():
    # Удаляем индекс и внешний ключ, затем колонку и таблицу.
    op.execute(
        """
        DROP INDEX IF EXISTS idx_businesses_network_id
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        DROP CONSTRAINT IF EXISTS fk_businesses_network_id_networks
        """
    )
    op.execute(
        """
        ALTER TABLE businesses
        DROP COLUMN IF EXISTS network_id
        """
    )
    op.execute(
        """
        DROP INDEX IF EXISTS idx_networks_owner_id
        """
    )
    op.execute(
        """
        DROP TABLE IF EXISTS networks
        """
    )

