#!/usr/bin/env python3
"""
Миграция: Добавление поля optimized_description в таблицу UserServices
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from safe_db_utils import safe_migrate, get_db_connection

def migrate():
    """Добавить поле optimized_description в UserServices"""
    
    def apply_migration(conn):
        cursor = conn.cursor()
        
        # Проверяем, есть ли уже поле
        cursor.execute("PRAGMA table_info(UserServices)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'optimized_description' not in columns:
            print("📝 Добавляем поле optimized_description в UserServices...")
            cursor.execute("""
                ALTER TABLE UserServices 
                ADD COLUMN optimized_description TEXT
            """)
            print("✅ Поле optimized_description добавлено")
        else:
            print("✅ Поле optimized_description уже существует")
        
        conn.commit()
    
    safe_migrate(apply_migration, "add_optimized_description_to_userservices")

if __name__ == "__main__":
    migrate()

