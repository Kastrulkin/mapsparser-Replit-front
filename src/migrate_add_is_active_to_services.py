#!/usr/bin/env python3
"""
Миграция: добавление колонки is_active в таблицу UserServices
"""
from safe_db_utils import safe_migrate

def migrate_add_is_active():
    """Добавить колонку is_active в таблицу UserServices"""
    
    def migration_func(cursor):
        print("Добавление колонки is_active в UserServices...")
        
        try:
            cursor.execute("""
                ALTER TABLE UserServices 
                ADD COLUMN is_active INTEGER DEFAULT 1
            """)
            print("✅ Колонка is_active добавлена (по умолчанию 1 - активна)")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                print("⚠️ Колонка is_active уже существует")
            else:
                raise
    
    safe_migrate(migration_func, "Add is_active column to UserServices")

if __name__ == "__main__":
    migrate_add_is_active()
    print("\n✅ Миграция завершена успешно!")
