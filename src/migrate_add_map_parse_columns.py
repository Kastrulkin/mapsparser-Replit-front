#!/usr/bin/env python3
"""
Миграция: Добавление колонок services_count и products в таблицу MapParseResults
"""
try:
    from safe_db_utils import get_db_connection
except ImportError:
    import sys
    import os
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from safe_db_utils import get_db_connection

def migrate():
    print("🔄 Запуск миграции: добавление services_count и products в MapParseResults...")
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем структуру таблицы
        cursor.execute("PRAGMA table_info(MapParseResults)")
        columns = [row[1] for row in cursor.fetchall()]
        
        # 1. services_count
        if 'services_count' not in columns:
            print("➕ Добавление колонки services_count...")
            cursor.execute("ALTER TABLE MapParseResults ADD COLUMN services_count INTEGER DEFAULT 0")
        else:
            print("✓ Колонка services_count уже существует")
            
        # 2. products (JSON)
        if 'products' not in columns:
            print("➕ Добавление колонки products...")
            cursor.execute("ALTER TABLE MapParseResults ADD COLUMN products TEXT")
        else:
            print("✓ Колонка products уже существует")
            
        conn.commit()
        print("✅ Миграция успешно завершена")
        
    except Exception as e:
        print(f"❌ Ошибка миграции: {e}")
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    migrate()
