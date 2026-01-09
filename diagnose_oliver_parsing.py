#!/usr/bin/env python3
"""Диагностика и исправление проблем парсинга для Оливера"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from safe_db_utils import get_db_connection
from datetime import datetime, timedelta

business_id = '533c1300-8a54-43a8-aa1f-69a8ed9c24ba'

print('=' * 60)
print('ДИАГНОСТИКА ПАРСИНГА ДЛЯ ОЛИВЕРА')
print('=' * 60)

conn = get_db_connection()
cursor = conn.cursor()

# Проверяем наличие колонок
cursor.execute("PRAGMA table_info(ParseQueue)")
parsequeue_columns = [row[1] for row in cursor.fetchall()]
has_updated_at = 'updated_at' in parsequeue_columns

# 1. Проверить задачу с ошибкой
print('\n1. Задача с ошибкой:')
if has_updated_at:
    cursor.execute("""
        SELECT id, status, error_message, created_at, updated_at
        FROM ParseQueue
        WHERE business_id = ? AND status = 'error'
        ORDER BY created_at DESC
        LIMIT 1
    """, (business_id,))
else:
    cursor.execute("""
        SELECT id, status, error_message, created_at
        FROM ParseQueue
        WHERE business_id = ? AND status = 'error'
        ORDER BY created_at DESC
        LIMIT 1
    """, (business_id,))
error_task = cursor.fetchone()
if error_task:
    print(f"   ID: {error_task[0]}")
    print(f"   Статус: {error_task[1]}")
    print(f"   Ошибка: {error_task[2]}")
    print(f"   Создано: {error_task[3]}")
    if has_updated_at and len(error_task) > 4:
        print(f"   Обновлено: {error_task[4]}")
else:
    print("   Нет задач с ошибками")

# 2. Проверить зависшие задачи
print('\n2. Зависшие задачи (processing более 10 минут):')
if has_updated_at:
    cutoff_time = (datetime.now() - timedelta(minutes=10)).isoformat()
    cursor.execute("""
        SELECT id, updated_at, task_type, created_at
        FROM ParseQueue
        WHERE business_id = ? 
        AND status = 'processing'
        AND updated_at < ?
        ORDER BY updated_at ASC
    """, (business_id, cutoff_time))
else:
    # Если нет updated_at, считаем зависшими все processing задачи старше 1 часа
    cutoff_time = (datetime.now() - timedelta(hours=1)).isoformat()
    cursor.execute("""
        SELECT id, created_at, task_type, created_at
        FROM ParseQueue
        WHERE business_id = ? 
        AND status = 'processing'
        AND created_at < ?
        ORDER BY created_at ASC
    """, (business_id, cutoff_time))
stuck_tasks = cursor.fetchall()
if stuck_tasks:
    print(f"   Найдено {len(stuck_tasks)} зависших задач:")
    for task in stuck_tasks:
        if has_updated_at:
            task_id, updated_at, task_type, created_at = task
            age = datetime.now() - datetime.fromisoformat(updated_at)
            print(f"   - ID: {task_id[:36]}...")
            print(f"     Тип: {task_type}")
            print(f"     Создано: {created_at}")
            print(f"     Обновлено: {updated_at} ({age.total_seconds()/3600:.1f} часов назад)")
        else:
            task_id, created_at, task_type, _ = task
            age = datetime.now() - datetime.fromisoformat(created_at)
            print(f"   - ID: {task_id[:36]}...")
            print(f"     Тип: {task_type}")
            print(f"     Создано: {created_at} ({age.total_seconds()/3600:.1f} часов назад)")
        print()
else:
    print("   ✅ Зависших задач не найдено")

# 3. Проверить отзывы без дат
print('\n3. Статистика отзывов:')
cursor.execute("""
    SELECT 
        COUNT(*) as total,
        COUNT(CASE WHEN published_at IS NOT NULL THEN 1 END) as with_date,
        COUNT(CASE WHEN response_text IS NOT NULL AND response_text != '' THEN 1 END) as with_response,
        MIN(created_at) as first_review,
        MAX(created_at) as last_review
    FROM ExternalBusinessReviews
    WHERE business_id = ?
""", (business_id,))
stats = cursor.fetchone()
if stats:
    print(f"   Всего отзывов: {stats[0]}")
    print(f"   С датами: {stats[1]} ({stats[1]/stats[0]*100:.1f}%)")
    print(f"   С ответами: {stats[2]} ({stats[2]/stats[0]*100:.1f}%)")
    print(f"   Первый отзыв: {stats[3]}")
    print(f"   Последний отзыв: {stats[4]}")

# 4. Проверить последние отзывы (сырые данные)
print('\n4. Последние 3 отзыва (детально):')
cursor.execute("""
    SELECT author_name, rating, text, response_text, published_at, response_at, created_at
    FROM ExternalBusinessReviews
    WHERE business_id = ?
    ORDER BY created_at DESC
    LIMIT 3
""", (business_id,))
reviews = cursor.fetchall()
for idx, review in enumerate(reviews, 1):
    print(f"   Отзыв #{idx}:")
    print(f"     Автор: {review[0]}")
    print(f"     Рейтинг: {review[1]}")
    print(f"     Текст: {review[2][:80] if review[2] else 'N/A'}...")
    print(f"     Ответ: {'Да' if review[3] else 'Нет'}")
    print(f"     Дата публикации: {review[4] or 'НЕТ'}")
    print(f"     Дата ответа: {review[5] or 'НЕТ'}")
    print(f"     Создан в БД: {review[6]}")
    print()

# 5. Проверить, есть ли pending задачи
print('\n5. Задачи в очереди:')
cursor.execute("""
    SELECT status, COUNT(*) as count
    FROM ParseQueue
    WHERE business_id = ?
    GROUP BY status
""", (business_id,))
status_counts = cursor.fetchall()
if status_counts:
    for status, count in status_counts:
        print(f"   {status}: {count} задач")
else:
    print("   Нет задач в очереди")

conn.close()
print('\n' + '=' * 60)
print('РЕКОМЕНДАЦИИ:')
print('=' * 60)
if stuck_tasks:
    print('\n⚠️  Нужно сбросить зависшие задачи:')
    print('   python3 reset_stuck_tasks.py')
if error_task:
    print('\n⚠️  Есть задача с ошибкой - проверьте error_message выше')
if stats and stats[1] == 0:
    print('\n⚠️  Даты отзывов не парсятся (0 из {} имеют даты)'.format(stats[0]))
    print('   Нужно проверить логи worker и код парсинга дат')
print()
