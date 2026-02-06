#!/usr/bin/env python3
"""
Миграция: добавление колонки workflow в таблицу AIAgents
"""
from safe_db_utils import safe_migrate

def migrate_add_workflow():
    """Добавить колонку workflow в таблицу AIAgents"""
    
    def migration_func(cursor):
        print("Добавление колонки workflow в AIAgents...")
        cursor.execute("""
            ALTER TABLE AIAgents 
            ADD COLUMN workflow TEXT DEFAULT NULL
        """)
        print("✅ Колонка workflow добавлена")
    
    safe_migrate(migration_func, "Add workflow column to AIAgents")

if __name__ == "__main__":
    migrate_add_workflow()
    print("\n✅ Миграция завершена успешно!")
