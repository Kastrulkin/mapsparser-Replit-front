#!/usr/bin/env python3
"""
Миграция: Добавление недостающих индексов для оптимизации производительности
Этап 1 из плана оптимизации БД
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from safe_db_utils import safe_migrate, get_db_connection

def migrate_add_missing_indexes(cursor):
    """Добавить недостающие индексы для оптимизации запросов"""
    
    print("🔄 Начинаю добавление индексов...")
    
    indexes = [
        ("idx_user_sessions_token", "CREATE INDEX IF NOT EXISTS idx_user_sessions_token ON UserSessions(token)"),
        ("idx_user_sessions_expires", "CREATE INDEX IF NOT EXISTS idx_user_sessions_expires ON UserSessions(expires_at)"),
        ("idx_businesses_active", "CREATE INDEX IF NOT EXISTS idx_businesses_active ON Businesses(is_active)"),
        ("idx_businesses_subscription_status", "CREATE INDEX IF NOT EXISTS idx_businesses_subscription_status ON Businesses(subscription_status)"),
        ("idx_bookings_status", "CREATE INDEX IF NOT EXISTS idx_bookings_status ON Bookings(status)"),
        ("idx_bookings_business_status", "CREATE INDEX IF NOT EXISTS idx_bookings_business_status ON Bookings(business_id, status)"),
        ("idx_ext_reviews_published_at", "CREATE INDEX IF NOT EXISTS idx_ext_reviews_published_at ON ExternalBusinessReviews(published_at)"),
        ("idx_ext_reviews_business_published", "CREATE INDEX IF NOT EXISTS idx_ext_reviews_business_published ON ExternalBusinessReviews(business_id, published_at)"),
        ("idx_chatgpt_requests_business_status", "CREATE INDEX IF NOT EXISTS idx_chatgpt_requests_business_status ON ChatGPTRequests(business_id, response_status)"),
        ("idx_token_usage_business_created", "CREATE INDEX IF NOT EXISTS idx_token_usage_business_created ON TokenUsage(business_id, created_at)"),
    ]
    
    created_count = 0
    skipped_count = 0
    
    for index_name, sql in indexes:
        try:
            cursor.execute(sql)
            created_count += 1
            print(f"✅ Создан индекс: {index_name}")
        except Exception as e:
            print(f"⚠️ Ошибка при создании индекса {index_name}: {e}")
            skipped_count += 1
    
    print(f"📊 Итого: создано {created_count} индексов, пропущено {skipped_count}")
    return created_count, skipped_count

if __name__ == "__main__":
    print("🔄 Запуск миграции: добавление недостающих индексов...")
    
    success = safe_migrate(
        migrate_add_missing_indexes,
        "Добавление недостающих индексов для оптимизации производительности"
    )
    
    if success:
        print("✅ Миграция выполнена успешно!")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'")
        all_indexes = [row[0] for row in cursor.fetchall()]
        print(f"📊 Всего индексов с префиксом idx_: {len(all_indexes)}")
        print(f"📋 Индексы: {sorted(all_indexes)}")
        conn.close()
        
        sys.exit(0)
    else:
        print("❌ Миграция завершилась с ошибкой")
        sys.exit(1)

