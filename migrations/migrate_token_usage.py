#!/usr/bin/env python3
"""
Миграция для создания таблицы TokenUsage
Хранит информацию об использовании токенов GigaChat для каждого запроса
"""
import sys
import os
import sqlite3
from safe_db_utils import safe_migrate, get_db_path, backup_database

def migrate_token_usage(cursor):
    """Миграция для создания таблицы TokenUsage"""
    print("🔄 Создание таблицы TokenUsage...")
    
    try:
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS TokenUsage (
                id TEXT PRIMARY KEY,
                business_id TEXT,
                user_id TEXT,
                task_type TEXT NOT NULL,
                model TEXT NOT NULL,
                prompt_tokens INTEGER DEFAULT 0,
                completion_tokens INTEGER DEFAULT 0,
                total_tokens INTEGER DEFAULT 0,
                endpoint TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (business_id) REFERENCES Businesses(id) ON DELETE SET NULL,
                FOREIGN KEY (user_id) REFERENCES Users(id) ON DELETE SET NULL
            )
        """)
        
        # Индексы для быстрого поиска
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_token_usage_business_id 
            ON TokenUsage(business_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_token_usage_user_id 
            ON TokenUsage(user_id)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_token_usage_created_at 
            ON TokenUsage(created_at)
        """)
        
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_token_usage_task_type 
            ON TokenUsage(task_type)
        """)
        
        print("  ✅ Таблица TokenUsage создана")
        print("  ✅ Индексы созданы")
        
    except sqlite3.OperationalError as e:
        if 'duplicate' in str(e).lower() or 'already exists' in str(e).lower():
            print("  ℹ️  Таблица TokenUsage уже существует")
        else:
            print(f"  ⚠️  Ошибка при создании TokenUsage: {e}")
            raise

def main():
    print("=" * 60)
    print("🚀 Миграция: Создание таблицы TokenUsage")
    print("=" * 60)
    
    db_path = get_db_path()
    print(f"📁 Используем базу данных: {db_path}")

    success = safe_migrate(
        migrate_token_usage,
        "Создание таблицы TokenUsage для отслеживания использования токенов GigaChat"
    )
    
    if success:
        print("\n✅ Миграция завершена успешно!")
        print("📝 Все существующие данные сохранены!")
        print("💾 Бэкап создан автоматически в db_backups/")
    else:
        print("\n❌ Миграция не удалась.")
        print("💾 База данных восстановлена из бэкапа")
        sys.exit(1)

if __name__ == "__main__":
    main()

