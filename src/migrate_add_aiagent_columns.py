#!/usr/bin/env python3
"""
Миграция: добавление колонок task, identity, speech_style в таблицу AIAgents
"""
from safe_db_utils import safe_migrate

def migrate_add_aiagent_columns():
    """Добавить недостающие колонки в таблицу AIAgents"""
    
    def migration_func(cursor):
        print("Добавление колонок в AIAgents...")
        
        # Добавляем task
        try:
            cursor.execute("ALTER TABLE AIAgents ADD COLUMN task TEXT DEFAULT NULL")
            print("✅ Колонка task добавлена")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                print("⚠️ Колонка task уже существует")
            else:
                raise
        
        # Добавляем identity
        try:
            cursor.execute("ALTER TABLE AIAgents ADD COLUMN identity TEXT DEFAULT NULL")
            print("✅ Колонка identity добавлена")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                print("⚠️ Колонка identity уже существует")
            else:
                raise
        
        # Добавляем speech_style
        try:
            cursor.execute("ALTER TABLE AIAgents ADD COLUMN speech_style TEXT DEFAULT NULL")
            print("✅ Колонка speech_style добавлена")
        except Exception as e:
            if "duplicate column" in str(e).lower():
                print("⚠️ Колонка speech_style уже существует")
            else:
                raise
    
    safe_migrate(migration_func, "Add task, identity, speech_style columns to AIAgents")

if __name__ == "__main__":
    migrate_add_aiagent_columns()
    print("\n✅ Миграция завершена успешно!")
