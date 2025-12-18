#!/usr/bin/env python3
"""
Безопасная миграция: создание таблицы ParseQueue для очереди парсинга карт
"""
import sys
import os
sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'src'))

from safe_db_utils import safe_migrate, get_db_path

def create_parse_queue_table(cursor):
    """Создать таблицу ParseQueue для очереди парсинга"""
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS ParseQueue (
            id TEXT PRIMARY KEY,
            url TEXT NOT NULL,
            user_id TEXT NOT NULL,
            business_id TEXT,
            status TEXT NOT NULL DEFAULT 'pending',
            retry_after TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (user_id) REFERENCES Users (id) ON DELETE CASCADE,
            FOREIGN KEY (business_id) REFERENCES Businesses (id) ON DELETE CASCADE
        )
    """)
    print("✅ Таблица ParseQueue создана/проверена")
    
    # Создаем индексы для быстрого поиска
    try:
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_parsequeue_status ON ParseQueue(status)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_parsequeue_business_id ON ParseQueue(business_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_parsequeue_user_id ON ParseQueue(user_id)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_parsequeue_created_at ON ParseQueue(created_at)")
        print("✅ Индексы созданы/проверены")
    except Exception as e:
        print(f"ℹ️  Индексы уже существуют или не удалось создать: {e}")

if __name__ == "__main__":
    print("🔄 Начинаю миграцию: создание таблицы ParseQueue")
    print("=" * 60)
    
    db_path = get_db_path()
    print(f"📁 Используем базу данных: {db_path}")
    print()
    
    success = safe_migrate(create_parse_queue_table, "Создание таблицы ParseQueue")
    
    if success:
        print()
        print("=" * 60)
        print("✅ Миграция завершена успешно!")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("❌ Миграция не удалась. Проверьте логи выше.")
        print("=" * 60)
        sys.exit(1)

