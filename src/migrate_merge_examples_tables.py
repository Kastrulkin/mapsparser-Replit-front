#!/usr/bin/env python3
"""
Миграция: Объединение таблиц Examples в одну таблицу UserExamples
Этап 3 из плана оптимизации БД
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from safe_db_utils import safe_migrate, get_db_connection

ALLOWED_TABLES = {'UserNewsExamples', 'UserReviewExamples', 'UserServiceExamples', 'UserExamples'}

def migrate_merge_examples_tables(cursor):
    """Объединить таблицы UserNewsExamples, UserReviewExamples, UserServiceExamples в UserExamples"""
    
    print("🔄 Начинаю объединение таблиц Examples...")
    
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    existing_tables = {row[0] for row in cursor.fetchall()}
    
    source_tables = {
        'UserNewsExamples': 'news',
        'UserReviewExamples': 'review',
        'UserServiceExamples': 'service'
    }
    
    total_count_before = 0
    for table_name, example_type in source_tables.items():
        if table_name not in existing_tables:
            print(f"⚠️ Таблица {table_name} не найдена, пропускаю")
            continue
        
        if table_name not in ALLOWED_TABLES:
            raise ValueError(f"Неразрешенная таблица: {table_name}")
        
        cursor.execute("SELECT COUNT(*) FROM " + table_name)
        count = cursor.fetchone()[0]
        total_count_before += count
        print(f"📊 Записей в {table_name}: {count}")
    
    if 'UserExamples' not in existing_tables:
        print("📋 Создаю таблицу UserExamples...")
        from core.db_helpers import ensure_user_examples_table
        ensure_user_examples_table(cursor)
        print("✅ Таблица UserExamples создана")
    else:
        print("⚠️ Таблица UserExamples уже существует")
    
    migrated_count = 0
    
    for table_name, example_type in source_tables.items():
        if table_name not in existing_tables:
            continue
        
        print(f"📋 Переношу данные из {table_name} (type={example_type})...")
        cursor.execute("""
            INSERT INTO UserExamples (id, user_id, example_type, example_text, created_at)
            SELECT id, user_id, ?, example_text, created_at 
            FROM """ + table_name + """
            WHERE NOT EXISTS (
                SELECT 1 FROM UserExamples WHERE UserExamples.id = """ + table_name + """.id
            )
        """, (example_type,))
        
        count = cursor.rowcount
        migrated_count += count
        print(f"✅ Перенесено записей из {table_name}: {count}")
    
    print(f"📊 Итого перенесено записей: {migrated_count} (было: {total_count_before})")
    
    for table_name in source_tables.keys():
        if table_name not in existing_tables:
            continue
        
        if table_name not in ALLOWED_TABLES:
            raise ValueError(f"Неразрешенная таблица: {table_name}")
        
        print(f"📋 Удаляю таблицу {table_name}...")
        cursor.execute("DROP TABLE IF EXISTS " + table_name)
        print(f"✅ Таблица {table_name} удалена")

if __name__ == "__main__":
    print("🔄 Запуск миграции: объединение таблиц Examples...")
    
    success = safe_migrate(
        migrate_merge_examples_tables,
        "Объединение таблиц Examples в одну таблицу UserExamples"
    )
    
    if success:
        print("✅ Миграция выполнена успешно!")
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute("SELECT COUNT(*) FROM UserExamples")
        total_count = cursor.fetchone()[0]
        print(f"📊 Всего записей в UserExamples: {total_count}")
        
        cursor.execute("SELECT example_type, COUNT(*) FROM UserExamples GROUP BY example_type")
        for row in cursor.fetchall():
            print(f"📋 {row[0]}: {row[1]} записей")
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        
        removed = ['UserNewsExamples', 'UserReviewExamples', 'UserServiceExamples']
        for table in removed:
            if table in tables:
                print(f"⚠️ Таблица {table} все еще существует!")
            else:
                print(f"✅ Таблица {table} удалена")
        
        conn.close()
        
        sys.exit(0)
    else:
        print("❌ Миграция завершилась с ошибкой")
        sys.exit(1)

