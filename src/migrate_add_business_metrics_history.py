#!/usr/bin/env python3
"""
Миграция: Добавить таблицу BusinessMetricsHistory для хранения истории метрик
"""
from safe_db_utils import safe_migrate

def migrate_add_business_metrics_history():
    """Создать таблицу BusinessMetricsHistory"""
    
    def migration_func(cursor):
        print("Creating BusinessMetricsHistory table...")
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS BusinessMetricsHistory (
                id TEXT PRIMARY KEY,
                business_id TEXT NOT NULL,
                metric_date DATE NOT NULL,
                rating FLOAT,
                reviews_count INTEGER,
                photos_count INTEGER,
                news_count INTEGER,
                source TEXT DEFAULT 'manual',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id)
            )
        """)
        print("✅ Table BusinessMetricsHistory created")
        
        # Создаем индексы
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_metrics_history_business_date 
            ON BusinessMetricsHistory(business_id, metric_date DESC)
        """)
        print("✅ Indexes created")
        
        # Заполняем существующие данные из MapParseResults
        print("Migrating existing data from MapParseResults...")
        cursor.execute("""
            INSERT INTO BusinessMetricsHistory (
                id, business_id, metric_date, rating, reviews_count, 
                photos_count, news_count, source, created_at
            )
            SELECT 
                'hist_' || id,
                business_id,
                DATE(created_at),
                CAST(rating AS FLOAT),
                reviews_count,
                photos_count,
                news_count,
                'parsing',
                created_at
            FROM MapParseResults
            WHERE business_id IS NOT NULL
            AND NOT EXISTS (
                SELECT 1 FROM BusinessMetricsHistory bmh 
                WHERE bmh.business_id = MapParseResults.business_id 
                AND bmh.metric_date = DATE(MapParseResults.created_at)
            )
        """)
        migrated_count = cursor.rowcount
        print(f"✅ Migrated {migrated_count} records from MapParseResults")

    safe_migrate(
        migration_func,
        "Add BusinessMetricsHistory table and migrate existing data"
    )

if __name__ == "__main__":
    migrate_add_business_metrics_history()
    print("\n✅ Migration completed successfully!")
