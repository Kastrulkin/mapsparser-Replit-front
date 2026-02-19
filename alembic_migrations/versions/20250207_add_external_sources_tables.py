"""add external sources tables (externalbusiness*)

Revision ID: 20250207_008
Revises: 20250207_007
Create Date: 2025-02-07

"""
from alembic import op


revision = "20250207_008"
down_revision = "20250207_007"
branch_labels = None
depends_on = None


def upgrade():
    # 1) Таблица externalbusinessaccounts (аккаунты внешних источников)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS externalbusinessaccounts (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            source TEXT NOT NULL,
            external_id TEXT,
            display_name TEXT,
            auth_data_encrypted TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            last_sync_at TIMESTAMP,
            last_error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Внешний ключ на businesses.id (ON DELETE CASCADE)
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints tc
                WHERE tc.constraint_name = 'fk_externalbusinessaccounts_business_id'
                  AND tc.table_name = 'externalbusinessaccounts'
                  AND tc.constraint_type = 'FOREIGN KEY'
            ) THEN
                ALTER TABLE externalbusinessaccounts
                ADD CONSTRAINT fk_externalbusinessaccounts_business_id
                FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE;
            END IF;
        END$$;
        """
    )

    # Индексы для externalbusinessaccounts
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_external_accounts_business
        ON externalbusinessaccounts(business_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_external_accounts_source
        ON externalbusinessaccounts(source)
        """
    )

    # 2) Таблица externalbusinessreviews (нормализованные отзывы)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS externalbusinessreviews (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            account_id TEXT,
            source TEXT NOT NULL,
            external_review_id TEXT,
            rating INTEGER,
            author_name TEXT,
            author_profile_url TEXT,
            text TEXT,
            response_text TEXT,
            response_at TIMESTAMP,
            published_at TIMESTAMP,
            lang TEXT,
            raw_payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Внешние ключи для externalbusinessreviews
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints tc
                WHERE tc.constraint_name = 'fk_externalbusinessreviews_business_id'
                  AND tc.table_name = 'externalbusinessreviews'
                  AND tc.constraint_type = 'FOREIGN KEY'
            ) THEN
                ALTER TABLE externalbusinessreviews
                ADD CONSTRAINT fk_externalbusinessreviews_business_id
                FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE;
            END IF;
        END$$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints tc
                WHERE tc.constraint_name = 'fk_externalbusinessreviews_account_id'
                  AND tc.table_name = 'externalbusinessreviews'
                  AND tc.constraint_type = 'FOREIGN KEY'
            ) THEN
                ALTER TABLE externalbusinessreviews
                ADD CONSTRAINT fk_externalbusinessreviews_account_id
                FOREIGN KEY (account_id) REFERENCES externalbusinessaccounts(id) ON DELETE SET NULL;
            END IF;
        END$$;
        """
    )

    # Индексы для externalbusinessreviews
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ext_reviews_business
        ON externalbusinessreviews(business_id)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ext_reviews_source
        ON externalbusinessreviews(source)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ext_reviews_published_at
        ON externalbusinessreviews(published_at)
        """
    )

    # 3) Таблица externalbusinessstats (агрегированная статистика)
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS externalbusinessstats (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            account_id TEXT,
            source TEXT NOT NULL,
            date TEXT NOT NULL,
            views_total INTEGER,
            clicks_total INTEGER,
            actions_total INTEGER,
            rating REAL,
            reviews_total INTEGER,
            raw_payload TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # Внешние ключи для externalbusinessstats
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints tc
                WHERE tc.constraint_name = 'fk_externalbusinessstats_business_id'
                  AND tc.table_name = 'externalbusinessstats'
                  AND tc.constraint_type = 'FOREIGN KEY'
            ) THEN
                ALTER TABLE externalbusinessstats
                ADD CONSTRAINT fk_externalbusinessstats_business_id
                FOREIGN KEY (business_id) REFERENCES businesses(id) ON DELETE CASCADE;
            END IF;
        END$$;
        """
    )
    op.execute(
        """
        DO $$
        BEGIN
            IF NOT EXISTS (
                SELECT 1
                FROM information_schema.table_constraints tc
                WHERE tc.constraint_name = 'fk_externalbusinessstats_account_id'
                  AND tc.table_name = 'externalbusinessstats'
                  AND tc.constraint_type = 'FOREIGN KEY'
            ) THEN
                ALTER TABLE externalbusinessstats
                ADD CONSTRAINT fk_externalbusinessstats_account_id
                FOREIGN KEY (account_id) REFERENCES externalbusinessaccounts(id) ON DELETE SET NULL;
            END IF;
        END$$;
        """
    )

    # Индексы для externalbusinessstats
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ext_stats_business_date
        ON externalbusinessstats(business_id, date)
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS idx_ext_stats_source
        ON externalbusinessstats(source)
        """
    )


def downgrade():
    # Удаляем индексы и ограничения, затем таблицы (в обратном порядке зависимостей)
    op.execute("DROP INDEX IF EXISTS idx_ext_stats_source")
    op.execute("DROP INDEX IF EXISTS idx_ext_stats_business_date")
    op.execute(
        """
        ALTER TABLE externalbusinessstats
        DROP CONSTRAINT IF EXISTS fk_externalbusinessstats_account_id
        """
    )
    op.execute(
        """
        ALTER TABLE externalbusinessstats
        DROP CONSTRAINT IF EXISTS fk_externalbusinessstats_business_id
        """
    )
    op.execute("DROP TABLE IF EXISTS externalbusinessstats")

    op.execute("DROP INDEX IF EXISTS idx_ext_reviews_published_at")
    op.execute("DROP INDEX IF EXISTS idx_ext_reviews_source")
    op.execute("DROP INDEX IF EXISTS idx_ext_reviews_business")
    op.execute(
        """
        ALTER TABLE externalbusinessreviews
        DROP CONSTRAINT IF EXISTS fk_externalbusinessreviews_account_id
        """
    )
    op.execute(
        """
        ALTER TABLE externalbusinessreviews
        DROP CONSTRAINT IF EXISTS fk_externalbusinessreviews_business_id
        """
    )
    op.execute("DROP TABLE IF EXISTS externalbusinessreviews")

    op.execute("DROP INDEX IF EXISTS idx_external_accounts_source")
    op.execute("DROP INDEX IF EXISTS idx_external_accounts_business")
    op.execute(
        """
        ALTER TABLE externalbusinessaccounts
        DROP CONSTRAINT IF EXISTS fk_externalbusinessaccounts_business_id
        """
    )
    op.execute("DROP TABLE IF EXISTS externalbusinessaccounts")

