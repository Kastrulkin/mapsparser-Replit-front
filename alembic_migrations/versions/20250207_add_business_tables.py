"""add business related tables

Revision ID: 20250207_002
Revises: 20250207_001
Create Date: 2025-02-07

"""
from alembic import op

revision = "20250207_002"
down_revision = "20250207_001"
branch_labels = None
depends_on = None


def upgrade():
    # Индекс по owner_id (существующая таблица businesses — только индекс)
    op.execute("CREATE INDEX IF NOT EXISTS idx_businesses_owner_id ON businesses(owner_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS userservices (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            user_id TEXT,
            name TEXT NOT NULL,
            description TEXT,
            category TEXT,
            keywords JSONB,
            price TEXT,
            is_active BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_userservices_business_id ON userservices(business_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS financialtransactions (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            amount NUMERIC(10,2) NOT NULL,
            description TEXT,
            transaction_type TEXT NOT NULL CHECK (transaction_type IN ('income', 'expense')),
            transaction_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_financialtransactions_business_id ON financialtransactions(business_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS financialmetrics (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            metric_name TEXT NOT NULL,
            metric_value NUMERIC(10,2) NOT NULL,
            period TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_financialmetrics_business_id ON financialmetrics(business_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS cards (
            id TEXT PRIMARY KEY,
            business_id TEXT,
            user_id TEXT,
            url TEXT,
            title TEXT,
            address TEXT,
            phone TEXT,
            site TEXT,
            rating REAL,
            reviews_count INTEGER,
            categories TEXT,
            overview TEXT,
            products TEXT,
            news TEXT,
            photos TEXT,
            features_full TEXT,
            competitors TEXT,
            hours TEXT,
            hours_full TEXT,
            report_path TEXT,
            seo_score INTEGER,
            ai_analysis JSONB,
            recommendations JSONB,
            version INTEGER DEFAULT 1,
            is_latest BOOLEAN DEFAULT TRUE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_cards_business_id ON cards(business_id)")

    op.execute("""
        CREATE TABLE IF NOT EXISTS screenshot_analyses (
            id TEXT PRIMARY KEY,
            business_id TEXT NOT NULL,
            screenshot_path TEXT,
            analysis_result JSONB,
            analysis_type TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    op.execute("CREATE INDEX IF NOT EXISTS idx_screenshot_analyses_business_id ON screenshot_analyses(business_id)")


def downgrade():
    # Удаляем только объекты, созданные в этой миграции. users, businesses, parsequeue не трогаем.
    op.execute("DROP INDEX IF EXISTS idx_screenshot_analyses_business_id")
    op.execute("DROP TABLE IF EXISTS screenshot_analyses")
    op.execute("DROP INDEX IF EXISTS idx_cards_business_id")
    op.execute("DROP TABLE IF EXISTS cards")
    op.execute("DROP INDEX IF EXISTS idx_financialmetrics_business_id")
    op.execute("DROP TABLE IF EXISTS financialmetrics")
    op.execute("DROP INDEX IF EXISTS idx_financialtransactions_business_id")
    op.execute("DROP TABLE IF EXISTS financialtransactions")
    op.execute("DROP INDEX IF EXISTS idx_userservices_business_id")
    op.execute("DROP TABLE IF EXISTS userservices")
    op.execute("DROP INDEX IF EXISTS idx_businesses_owner_id")
