#!/usr/bin/env python3
"""
Миграция: добавление колонки workflow в таблицу AIAgents
"""
import sqlite3
import sys
from pathlib import Path
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
    
    safe_migrate(
        db_path="src/reports.db",
        migration_name="Add workflow column to AIAgents",
        migration_func=migration_func
    )

if __name__ == "__main__":
    migrate_add_workflow()
    print("\n✅ Миграция завершена успешно!")
