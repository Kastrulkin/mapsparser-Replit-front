#!/usr/bin/env python3
"""
Миграция: Добавить колонку tasks в GrowthStages (если отсутствует)
"""
import sqlite3
import os

def migrate_add_tasks_column():
    """Добавить колонку tasks в GrowthStages"""
    db_path = os.path.join(os.path.dirname(__file__), 'reports.db')
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    try:
        # Проверяем, есть ли колонка
        cursor.execute("PRAGMA table_info(GrowthStages);")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'tasks' in columns:
            print("✅ Колонка 'tasks' уже существует в GrowthStages")
            return
        
        print("Adding 'tasks' column to GrowthStages...")
        cursor.execute("""
            ALTER TABLE GrowthStages 
            ADD COLUMN tasks TEXT DEFAULT NULL
        """)
        conn.commit()
        print("✅ Колонка 'tasks' успешно добавлена")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    migrate_add_tasks_column()
    print("\n✅ Миграция завершена!")
