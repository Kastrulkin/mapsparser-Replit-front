#!/usr/bin/env python3
"""
Миграция: Добавление поля chatgpt_context в таблицы Businesses и UserServices
"""
from safe_db_utils import get_db_connection, safe_migrate

def migrate():
    """Добавить поле chatgpt_context в Businesses и UserServices"""
    
    def add_chatgpt_context_columns(cursor):
        # Проверяем, существует ли поле chatgpt_context в Businesses
        cursor.execute("PRAGMA table_info(Businesses)")
        businesses_columns = [col[1] for col in cursor.fetchall()]
        
        if 'chatgpt_context' not in businesses_columns:
            print("📝 Добавляем поле chatgpt_context в таблицу Businesses...")
            cursor.execute("""
                ALTER TABLE Businesses 
                ADD COLUMN chatgpt_context TEXT
            """)
            print("✅ Поле chatgpt_context добавлено в Businesses")
        else:
            print("✅ Поле chatgpt_context уже существует в Businesses")
        
        # Проверяем, существует ли поле chatgpt_context в UserServices
        cursor.execute("PRAGMA table_info(UserServices)")
        services_columns = [col[1] for col in cursor.fetchall()]
        
        if 'chatgpt_context' not in services_columns:
            print("📝 Добавляем поле chatgpt_context в таблицу UserServices...")
            cursor.execute("""
                ALTER TABLE UserServices 
                ADD COLUMN chatgpt_context TEXT
            """)
            print("✅ Поле chatgpt_context добавлено в UserServices")
        else:
            print("✅ Поле chatgpt_context уже существует в UserServices")
    
    safe_migrate(
        add_chatgpt_context_columns,
        "Добавление поля chatgpt_context в Businesses и UserServices"
    )

if __name__ == "__main__":
    migrate()

