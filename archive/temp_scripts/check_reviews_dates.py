#!/usr/bin/env python3
"""Скрипт для проверки отзывов и дат"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from safe_db_utils import get_db_connection

business_id = '533c1300-8a54-43a8-aa1f-69a8ed9c24ba'

print("=" * 60)
print("ПРОВЕРКА ОТЗЫВОВ И ДАТ ДЛЯ ОЛИВЕРА")
print("=" * 60)

conn = get_db_connection()
cursor = conn.cursor()

# Проверить статистику отзывов
cursor.execute("""
    SELECT COUNT(*) as total,
           COUNT(CASE WHEN published_at IS NOT NULL THEN 1 END) as with_date,
           COUNT(CASE WHEN response_text IS NOT NULL AND response_text != '' THEN 1 END) as with_response
    FROM ExternalBusinessReviews
    WHERE business_id = ?
""", (business_id,))
row = cursor.fetchone()
print(f"\nСтатистика отзывов:")
print(f"  Всего: {row[0]}")
print(f"  С датами: {row[1]}")
print(f"  С ответами: {row[2]}")

# Показать последние 5 отзывов
print(f"\nПоследние 5 отзывов:")
cursor.execute("""
    SELECT author_name, rating, published_at, response_text, created_at
    FROM ExternalBusinessReviews
    WHERE business_id = ?
    ORDER BY created_at DESC
    LIMIT 5
""", (business_id,))
rows = cursor.fetchall()
for idx, r in enumerate(rows, 1):
    print(f"  {idx}. Автор: {r[0]}, Рейтинг: {r[1]}, Дата: {r[2]}, Ответ: {'Да' if r[3] else 'Нет'}, Создан: {r[4]}")

# Проверить задачи в очереди
print(f"\nЗадачи в очереди:")
cursor.execute("""
    SELECT id, status, task_type, created_at, updated_at, error_message
    FROM ParseQueue
    WHERE business_id = ?
    ORDER BY updated_at DESC
    LIMIT 5
""", (business_id,))
rows = cursor.fetchall()
for row in rows:
    print(f"  ID: {row[0]}")
    print(f"  Статус: {row[1]}")
    print(f"  Тип: {row[2]}")
    print(f"  Создано: {row[3]}")
    print(f"  Обновлено: {row[4]}")
    if len(row) > 5 and row[5]:
        print(f"  Ошибка: {row[5]}")
    print()

conn.close()
print("=" * 60)

