#!/usr/bin/env python3
"""
Миграция: Добавление поля optimized_name в таблицу UserServices
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from safe_db_utils import safe_migrate

def migrate():
    """Добавить поле optimized_name в UserServices"""
    
    def apply_migration(cursor):
        # Проверяем, есть ли уже поле
        cursor.execute("PRAGMA table_info(UserServices)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'optimized_name' not in columns:
            print("📝 Добавляем поле optimized_name в UserServices...")
            cursor.execute("""
                ALTER TABLE UserServices 
                ADD COLUMN optimized_name TEXT
            """)
            print("✅ Поле optimized_name добавлено")
        else:
            print("✅ Поле optimized_name уже существует")
    
    safe_migrate(apply_migration, "add_optimized_name_to_userservices")

if __name__ == "__main__":
    migrate()

