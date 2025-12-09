#!/usr/bin/env python3
"""
Миграция базы данных для добавления поля is_superadmin
"""
from safe_db_utils import get_db_connection
import sqlite3
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def migrate_database():
    """Добавить поле is_superadmin в таблицу Users"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли уже поле is_superadmin
        cursor.execute("PRAGMA table_info(Users)")
        columns = [column[1] for column in cursor.fetchall()]
        
        if 'is_superadmin' not in columns:
            print("📝 Добавляем поле is_superadmin в таблицу Users...")
            cursor.execute("ALTER TABLE Users ADD COLUMN is_superadmin BOOLEAN DEFAULT 0")
            print("✅ Поле is_superadmin добавлено")
        else:
            print("✅ Поле is_superadmin уже существует")
        
        # Проверяем, существует ли таблица Businesses
        cursor.execute("""
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name='Businesses'
        """)
        
        if not cursor.fetchone():
            print("📝 Создаем таблицу Businesses...")
            cursor.execute("""
                CREATE TABLE Businesses (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    description TEXT,
                    industry TEXT,
                    owner_id TEXT NOT NULL,
                    is_active BOOLEAN DEFAULT 1,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (owner_id) REFERENCES Users (id) ON DELETE CASCADE
                )
            """)
            print("✅ Таблица Businesses создана")
        else:
            print("✅ Таблица Businesses уже существует")
        
        conn.commit()
        print("🎉 Миграция завершена успешно!")
        return True
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        return False
    
    finally:
        conn.close()

if __name__ == "__main__":
    print("🔄 Выполняем миграцию базы данных...")
    success = migrate_database()
    
    if success:
        print("\n✅ Миграция завершена!")
    else:
        print("\n❌ Миграция не удалась.")
        sys.exit(1)
