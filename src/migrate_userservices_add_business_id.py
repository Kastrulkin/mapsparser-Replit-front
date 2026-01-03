#!/usr/bin/env python3
"""
Миграция: Добавление колонки business_id в таблицу UserServices
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from safe_db_utils import safe_migrate, get_db_connection
import sqlite3

def migrate_userservices_add_business_id(cursor):
    """Добавить колонку business_id в таблицу UserServices"""
    
    # Проверяем текущую структуру
    cursor.execute("PRAGMA table_info(UserServices)")
    columns = [col[1] for col in cursor.fetchall()]
    
    if 'business_id' in columns:
        print("✅ Колонка business_id уже существует, миграция не требуется")
        return
    
    print("🔄 Начинаю миграцию UserServices: добавление business_id...")
    
    # Добавляем колонку business_id
    cursor.execute("ALTER TABLE UserServices ADD COLUMN business_id TEXT")
    
    # Пытаемся заполнить business_id для существующих записей
    # Находим business_id по user_id из таблицы Businesses
    cursor.execute("""
        UPDATE UserServices
        SET business_id = (
            SELECT id FROM Businesses 
            WHERE owner_id = UserServices.user_id 
            LIMIT 1
        )
        WHERE business_id IS NULL
    """)
    
    updated_count = cursor.rowcount
    print(f"✅ Обновлено записей с business_id: {updated_count}")
    
    # Для записей, где не удалось найти business_id, оставляем NULL
    cursor.execute("SELECT COUNT(*) FROM UserServices WHERE business_id IS NULL")
    null_count = cursor.fetchone()[0]
    if null_count > 0:
        print(f"⚠️ Осталось записей без business_id: {null_count}")

if __name__ == "__main__":
    print("🔄 Запуск миграции UserServices: добавление business_id...")
    
    success = safe_migrate(
        migrate_userservices_add_business_id,
        "Добавление колонки business_id в таблицу UserServices"
    )
    
    if success:
        print("✅ Миграция выполнена успешно!")
        sys.exit(0)
    else:
        print("❌ Миграция завершилась с ошибкой")
        sys.exit(1)

