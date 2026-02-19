#!/usr/bin/env python3
"""Проверка полной истории парсинга для Оливера"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'src'))

from safe_db_utils import get_db_connection

business_id = '533c1300-8a54-43a8-aa1f-69a8ed9c24ba'

print('=' * 60)
print('ПОЛНАЯ ИСТОРИЯ ПАРСИНГА ДЛЯ ОЛИВЕРА')
print('=' * 60)

conn = get_db_connection()
cursor = conn.cursor()

# Проверить, есть ли бизнес в БД
cursor.execute('SELECT id, name FROM Businesses WHERE id = %s', (business_id,))
business = cursor.fetchone()
if business:
    print(f'\n✅ Бизнес найден: {business[1]} (ID: {business[0]})')
else:
    print(f'\n❌ Бизнес с ID {business_id} не найден в БД')
    conn.close()
    exit(1)

# Все задачи (включая done/error)
print('\n📋 Все задачи в ParseQueue (последние 10):')
cursor.execute('''
    SELECT id, status, task_type, url, created_at, error_message
    FROM ParseQueue
    WHERE business_id = ?
    ORDER BY created_at DESC
    LIMIT 10
''', (business_id,))
rows = cursor.fetchall()
if rows:
    print(f'   Найдено {len(rows)} задач:\n')
    for idx, row in enumerate(rows, 1):
        print(f'   Задача #{idx}:')
        print(f'     ID: {row[0][:36]}...')
        print(f'     Статус: {row[1]}')
        print(f'     Тип: {row[2] if row[2] else "N/A"}')
        print(f'     URL: {row[3][:60] if row[3] else "N/A"}...')
        print(f'     Создано: {row[4]}')
        if row[5]:
            print(f'     Ошибка: {row[5][:100]}...')
        print()
else:
    print('   ❌ Нет задач в ParseQueue для этого бизнеса')

# Статистика по статусам
print('\n📊 Статистика по статусам:')
cursor.execute('''
    SELECT status, COUNT(*) as count
    FROM ParseQueue
    WHERE business_id = ?
    GROUP BY status
''', (business_id,))
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(f'   {row[0]}: {row[1]} задач')
else:
    print('   Нет данных')

conn.close()
print('\n' + '=' * 60)
