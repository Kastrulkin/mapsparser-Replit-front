#!/usr/bin/env python3
"""
Миграция: Добавление колонки analysis_json в MapParseResults
"""
from safe_db_utils import safe_migrate, get_db_connection

def migrate():
    """Добавить колонку analysis_json"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли колонка
        cursor.execute("PRAGMA table_info(MapParseResults)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'analysis_json' not in columns:
            print("➕ Добавляю колонку analysis_json...")
            cursor.execute("""
                ALTER TABLE MapParseResults 
                ADD COLUMN analysis_json TEXT
            """)
            conn.commit()
            print("✅ Колонка analysis_json добавлена")
        else:
            print("✅ Колонка analysis_json уже существует")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка миграции: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    safe_migrate(migrate, "add_analysis_json_to_map_parse_results")

