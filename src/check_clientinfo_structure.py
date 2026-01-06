#!/usr/bin/env python3
"""
Проверка структуры таблицы ClientInfo
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from safe_db_utils import get_db_connection

conn = get_db_connection()
cursor = conn.cursor()

# Проверяем структуру таблицы
cursor.execute("PRAGMA table_info(ClientInfo)")
columns_info = cursor.fetchall()
columns = [col[1] for col in columns_info]

print("=" * 60)
print("СТРУКТУРА ТАБЛИЦЫ ClientInfo:")
print("=" * 60)
for col in columns_info:
    print(f"  {col[1]:20} {col[2]:15} PK={col[5]}")
print("=" * 60)
print(f"Колонки: {columns}")
print(f"Есть business_id: {'business_id' in columns}")
print("=" * 60)

# Проверяем PRIMARY KEY
cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='ClientInfo'")
table_sql = cursor.fetchone()
if table_sql:
    print(f"SQL создания таблицы:")
    print(table_sql[0])
    print("=" * 60)
    has_composite_pk = "PRIMARY KEY (user_id, business_id)" in table_sql[0] or "PRIMARY KEY(user_id,business_id)" in table_sql[0]
    print(f"Составной PRIMARY KEY (user_id, business_id): {has_composite_pk}")
else:
    print("❌ Таблица ClientInfo не найдена!")

# Проверяем данные
cursor.execute("SELECT COUNT(*) FROM ClientInfo")
count = cursor.fetchone()[0]
print(f"Записей в таблице: {count}")

conn.close()

