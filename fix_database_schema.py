#!/usr/bin/env python3
"""
Скрипт для исправления схемы базы данных - добавление колонки retry_after
"""
import sqlite3

def fix_database_schema():
    """Добавляем недостающие колонки в ParseQueue"""
    conn = sqlite3.connect("reports.db")
    cursor = conn.cursor()
    
    print("=== Исправление схемы ParseQueue ===")
    
    # Проверяем текущую структуру
    cursor.execute("PRAGMA table_info(ParseQueue)")
    columns = [col[1] for col in cursor.fetchall()]
    print(f"Текущие колонки: {columns}")
    
    # Добавляем retry_after если её нет
    if 'retry_after' not in columns:
        try:
            cursor.execute("ALTER TABLE ParseQueue ADD COLUMN retry_after TIMESTAMP")
            print("✅ Добавлена колонка retry_after")
        except sqlite3.OperationalError as e:
            print(f"❌ Ошибка добавления retry_after: {e}")
    else:
        print("✅ Колонка retry_after уже существует")
    
    # Проверяем обновленную структуру
    cursor.execute("PRAGMA table_info(ParseQueue)")
    updated_columns = [col[1] for col in cursor.fetchall()]
    print(f"Обновленные колонки: {updated_columns}")
    
    conn.commit()
    conn.close()
    print("✅ Схема базы данных исправлена!")

if __name__ == "__main__":
    fix_database_schema()
