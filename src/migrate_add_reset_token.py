#!/usr/bin/env python3
"""
Безопасная миграция: добавление колонок reset_token и reset_token_expires в Users
"""
from safe_db_utils import safe_migrate, get_db_connection

def add_reset_token_columns(cursor):
    """Добавить колонки для восстановления пароля"""
    # Проверяем существующие колонки
    cursor.execute("PRAGMA table_info(Users)")
    columns = [row[1] for row in cursor.fetchall()]
    
    # Добавляем reset_token
    if 'reset_token' not in columns:
        print("➕ Добавляю поле reset_token в Users...")
        cursor.execute("""
            ALTER TABLE Users 
            ADD COLUMN reset_token TEXT
        """)
        print("✅ Поле reset_token добавлено")
    else:
        print("ℹ️  Поле reset_token уже существует")
    
    # Добавляем reset_token_expires
    if 'reset_token_expires' not in columns:
        print("➕ Добавляю поле reset_token_expires в Users...")
        cursor.execute("""
            ALTER TABLE Users 
            ADD COLUMN reset_token_expires TIMESTAMP
        """)
        print("✅ Поле reset_token_expires добавлено")
    else:
        print("ℹ️  Поле reset_token_expires уже существует")

if __name__ == "__main__":
    print("🔄 Начинаю миграцию: добавление колонок для восстановления пароля")
    success = safe_migrate(add_reset_token_columns, "Добавление reset_token и reset_token_expires в Users")
    
    if success:
        print("✅ Миграция завершена успешно!")
    else:
        print("❌ Миграция не удалась. Проверьте логи выше.")

