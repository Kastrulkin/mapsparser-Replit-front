#!/usr/bin/env python3
"""Скрипт для проверки статуса парсера для бизнеса"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from safe_db_utils import get_db_connection

business_id = '533c1300-8a54-43a8-aa1f-69a8ed9c24ba'

print("=" * 60)
print("ПРОВЕРКА СТАТУСА ПАРСЕРА ДЛЯ ОЛИВЕРА")
print("=" * 60)

conn = get_db_connection()
cursor = conn.cursor()

# 1. Проверить задачи в очереди
print("\n1. Задачи в очереди ParseQueue:")
cursor.execute("""
    SELECT id, status, task_type, url, created_at, updated_at, retry_after
    FROM ParseQueue
    WHERE business_id = ?
    ORDER BY created_at DESC
    LIMIT 5
""", (business_id,))
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"   ID: {row[0]}")
        print(f"   Статус: {row[1]}")
        print(f"   Тип: {row[2]}")
        print(f"   URL: {row[3]}")
        print(f"   Создано: {row[4]}")
        print(f"   Обновлено: {row[5]}")
        print(f"   Retry after: {row[6]}")
        print()
else:
    print("   Нет задач в очереди")

# 2. Проверить последние результаты парсинга
print("\n2. Последние результаты парсинга (MapParseResults):")
cursor.execute("""
    SELECT id, rating, reviews_count, unanswered_reviews_count, news_count, photos_count, created_at
    FROM MapParseResults
    WHERE business_id = ?
    ORDER BY created_at DESC
    LIMIT 3
""", (business_id,))
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"   ID: {row[0]}")
        print(f"   Рейтинг: {row[1]}")
        print(f"   Отзывов: {row[2]}")
        print(f"   Без ответов: {row[3]}")
        print(f"   Новостей: {row[4]}")
        print(f"   Фото: {row[5]}")
        print(f"   Дата: {row[6]}")
        print()
else:
    print("   Нет результатов парсинга")

# 3. Проверить отзывы в ExternalBusinessReviews
print("\n3. Отзывы в ExternalBusinessReviews:")
cursor.execute("""
    SELECT COUNT(*) as total,
           COUNT(CASE WHEN response_text IS NOT NULL AND response_text != '' THEN 1 END) as with_response,
           COUNT(CASE WHEN published_at IS NOT NULL THEN 1 END) as with_date
    FROM ExternalBusinessReviews
    WHERE business_id = ?
""", (business_id,))
row = cursor.fetchone()
if row:
    print(f"   Всего отзывов: {row[0]}")
    print(f"   С ответами организации: {row[1]}")
    print(f"   С датами: {row[2]}")

# 4. Проверить последние 3 отзыва с датами и ответами
print("\n4. Последние 3 отзыва (с датами и ответами):")
cursor.execute("""
    SELECT author_name, rating, text, response_text, published_at, created_at
    FROM ExternalBusinessReviews
    WHERE business_id = ?
    ORDER BY published_at DESC, created_at DESC
    LIMIT 3
""", (business_id,))
rows = cursor.fetchall()
if rows:
    for idx, row in enumerate(rows, 1):
        print(f"   Отзыв #{idx}:")
        print(f"   Автор: {row[0]}")
        print(f"   Рейтинг: {row[1]}")
        print(f"   Текст: {row[2][:100] if row[2] else 'N/A'}...")
        print(f"   Ответ организации: {row[3][:100] if row[3] else 'Нет ответа'}...")
        print(f"   Дата публикации: {row[4]}")
        print(f"   Дата создания записи: {row[5]}")
        print()
else:
    print("   Нет отзывов в БД")

# 5. Проверить активные задачи (pending, processing)
print("\n5. Активные задачи в очереди (pending/processing):")
cursor.execute("""
    SELECT COUNT(*) as count, status
    FROM ParseQueue
    WHERE business_id = ? AND status IN ('pending', 'processing')
    GROUP BY status
""", (business_id,))
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f"   Статус '{row[1]}': {row[0]} задач")
else:
    print("   Нет активных задач")

conn.close()
print("\n" + "=" * 60)

