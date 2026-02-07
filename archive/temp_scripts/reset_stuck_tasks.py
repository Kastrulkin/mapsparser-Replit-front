#!/usr/bin/env python3
"""Сброс зависших задач в pending статус"""
import sys
import os
sys.path.insert(0, 'src')

from safe_db_utils import get_db_connection
from datetime import datetime, timedelta

conn = get_db_connection()
cursor = conn.cursor()

# Находим задачи в processing, которые обновлялись больше 10 минут назад
cutoff_time = (datetime.now() - timedelta(minutes=10)).isoformat()

cursor.execute("""
    SELECT id, updated_at, task_type, business_id
    FROM ParseQueue
    WHERE status = 'processing'
    AND updated_at < ?
""", (cutoff_time,))

stuck_tasks = cursor.fetchall()

if stuck_tasks:
    print(f"Найдено зависших задач: {len(stuck_tasks)}")
    for task in stuck_tasks:
        task_id, updated_at, task_type, business_id = task
        print(f"  - ID: {task_id}, Тип: {task_type}, Обновлено: {updated_at}")
        
        # Сбрасываем в pending
        cursor.execute("""
            UPDATE ParseQueue
            SET status = 'pending',
                updated_at = CURRENT_TIMESTAMP
            WHERE id = ?
        """, (task_id,))
    
    conn.commit()
    print(f"✅ Сброшено {len(stuck_tasks)} задач в pending")
else:
    print("✅ Зависших задач не найдено")

cursor.close()
conn.close()

