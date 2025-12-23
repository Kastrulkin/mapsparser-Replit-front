#!/usr/bin/env python3
"""
Миграция: Добавление поля is_agent_paused в таблицу AIAgentConversations
"""
import sys
import os
import sqlite3
from safe_db_utils import safe_migrate, get_db_path

def migrate_is_agent_paused(cursor):
    """Добавление поля is_agent_paused"""
    print("🔄 Добавление поля is_agent_paused в таблицу AIAgentConversations...")
    try:
        cursor.execute('ALTER TABLE AIAgentConversations ADD COLUMN is_agent_paused INTEGER DEFAULT 0')
        print("  ✅ Поле is_agent_paused добавлено")
    except sqlite3.OperationalError as e:
        if 'duplicate column' in str(e).lower():
            print("  ℹ️  Поле is_agent_paused уже существует")
        else:
            print(f"  ⚠️  Ошибка при добавлении is_agent_paused: {e}")

def main():
    print("=" * 60)
    print("🚀 Миграция: Добавление поля is_agent_paused")
    print("=" * 60)
    
    db_path = get_db_path()
    print(f"📁 Используем базу данных: {db_path}")

    success = safe_migrate(
        migrate_is_agent_paused,
        "Добавление поля is_agent_paused для остановки агента в чате"
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


