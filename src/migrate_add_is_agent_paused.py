#!/usr/bin/env python3
"""
Миграция: добавление колонки is_agent_paused в таблицу AIAgentConversations
"""
from safe_db_utils import safe_migrate

def migrate_add_is_agent_paused():
    """Добавить колонку is_agent_paused в таблицу AIAgentConversations"""
    
    def migration_func(cursor):
        print("Добавление колонки is_agent_paused в AIAgentConversations...")
        
        try:
            cursor.execute("""
                ALTER TABLE AIAgentConversations 
                ADD COLUMN is_agent_paused INTEGER DEFAULT 0
            """)
            print("✅ Колонка is_agent_paused добавлена (по умолчанию 0 - агент активен)")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                print("⚠️ Колонка is_agent_paused уже существует")
            else:
                raise
    
    safe_migrate(migration_func, "Add is_agent_paused column to AIAgentConversations")

if __name__ == "__main__":
    migrate_add_is_agent_paused()
    print("\n✅ Миграция завершена успешно!")
