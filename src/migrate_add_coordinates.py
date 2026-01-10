"""
Миграция: Добавление географических координат в таблицу Businesses
Дата: 2026-01-10
"""
import sqlite3
import os
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(__file__), 'reports.db')
BACKUP_DIR = os.path.join(os.path.dirname(__file__), '..', 'db_backups')

def safe_migrate():
    """Безопасная миграция с бэкапом"""
    # Создаем директорию для бэкапов если не существует
    os.makedirs(BACKUP_DIR, exist_ok=True)
    
    # Создаем бэкап
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = os.path.join(BACKUP_DIR, f'reports_{timestamp}.db.backup')
    
    print(f"💾 Создаём бэкап: {backup_path}")
    os.system(f'cp "{DB_PATH}" "{backup_path}"')
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    try:
        # Проверяем существование колонок
        cursor.execute("PRAGMA table_info(Businesses)")
        columns = [col[1] for col in cursor.fetchall()]
        
        if 'latitude' in columns and 'longitude' in columns:
            print("✅ Колонки 'latitude' и 'longitude' уже существуют в Businesses")
            return
        
        print("🔄 Выполняю миграцию: Add geographic coordinates to Businesses")
        
        # Добавляем колонки
        if 'latitude' not in columns:
            cursor.execute("ALTER TABLE Businesses ADD COLUMN latitude REAL")
            print("✅ Добавлена колонка 'latitude'")
        
        if 'longitude' not in columns:
            cursor.execute("ALTER TABLE Businesses ADD COLUMN longitude REAL")
            print("✅ Добавлена колонка 'longitude'")
        
        # Создаем индекс для быстрого поиска по координатам
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_businesses_coordinates 
            ON Businesses(latitude, longitude)
        """)
        print("✅ Создан индекс idx_businesses_coordinates")
        
        conn.commit()
        print(f"✅ Миграция выполнена успешно! Бэкап: {backup_path}")
        print("\n✅ Migration completed successfully!")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка миграции: {e}")
        print(f"💾 Восстановите из бэкапа: {backup_path}")
        raise
    finally:
        conn.close()

if __name__ == '__main__':
    safe_migrate()
