#!/usr/bin/env python3
"""
Безопасная миграция для добавления поля ai_agent_language в таблицу Businesses
Использует safe_db_utils для защиты данных
"""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from safe_db_utils import safe_migrate, get_db_path
import sqlite3

def migrate_ai_agent_language(cursor):
    """Миграция для добавления поля ai_agent_language"""
    
    print("🔄 Добавление поля ai_agent_language в таблицу Businesses...")
    
    # Проверяем, существует ли уже поле
    cursor.execute("PRAGMA table_info(Businesses)")
    columns = [row[1] for row in cursor.fetchall()]
    
    if 'ai_agent_language' in columns:
        print("  ℹ️  Поле ai_agent_language уже существует")
        return
    
    # Добавляем поле ai_agent_language
    try:
        cursor.execute("""
            ALTER TABLE Businesses 
            ADD COLUMN ai_agent_language TEXT DEFAULT NULL
        """)
        print("  ✅ Поле ai_agent_language добавлено")
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ℹ️  Поле ai_agent_language уже существует")
        else:
            print(f"  ⚠️  Ошибка при добавлении ai_agent_language: {e}")
            raise

def main():
    """Главная функция миграции"""
    print("=" * 60)
    print("🚀 Миграция: Добавление поля ai_agent_language")
    print("=" * 60)
    
    db_path = get_db_path()
    print(f"📁 Используем базу данных: {db_path}")
    
    success = safe_migrate(
        migrate_ai_agent_language,
        "Добавление поля ai_agent_language для выбора языка ИИ агента"
    )
    
    if success:
        print("\n✅ Миграция завершена успешно!")
        print("📝 Все существующие данные сохранены!")
        print("💾 Бэкап создан автоматически в db_backups/")
    else:
        print("\n❌ Миграция не удалась.")
        print("💾 База данных восстановлена из бэкапа")
        sys.exit(1)
    
    return 0

if __name__ == '__main__':
    exit(main())

