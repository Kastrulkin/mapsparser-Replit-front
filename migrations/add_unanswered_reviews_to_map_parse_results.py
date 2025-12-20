#!/usr/bin/env python3
"""
Миграция: Добавление колонки unanswered_reviews_count в MapParseResults
"""
from safe_db_utils import safe_migrate, get_db_connection

def migrate():
    """Добавить колонку unanswered_reviews_count"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    try:
        # Проверяем, существует ли колонка
        cursor.execute("PRAGMA table_info(MapParseResults)")
        columns = [row[1] for row in cursor.fetchall()]
        
        if 'unanswered_reviews_count' not in columns:
            print("➕ Добавляю колонку unanswered_reviews_count...")
            cursor.execute("""
                ALTER TABLE MapParseResults 
                ADD COLUMN unanswered_reviews_count INTEGER DEFAULT 0
            """)
            conn.commit()
            print("✅ Колонка unanswered_reviews_count добавлена")
        else:
            print("✅ Колонка unanswered_reviews_count уже существует")
        
    except Exception as e:
        conn.rollback()
        print(f"❌ Ошибка миграции: {e}")
        raise
    finally:
        conn.close()

if __name__ == "__main__":
    safe_migrate(migrate, "add_unanswered_reviews_to_map_parse_results")

