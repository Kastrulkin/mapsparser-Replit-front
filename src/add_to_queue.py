#!/usr/bin/env python3
"""
Скрипт для добавления заявки в очередь парсинга
"""
import sqlite3
import uuid
from datetime import datetime

def get_db_connection():
    """Получить соединение с SQLite базой данных"""
    conn = sqlite3.connect("reports.db")
    conn.row_factory = sqlite3.Row
    return conn

def add_to_queue(url: str, user_id: str):
    """Добавить заявку в очередь парсинга"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Создаем новую заявку
    queue_id = str(uuid.uuid4())
    
    cursor.execute("""
        INSERT INTO ParseQueue (id, url, user_id, status, created_at)
        VALUES (?, ?, ?, 'pending', ?)
    """, (queue_id, url, user_id, datetime.now().isoformat()))
    
    conn.commit()
    conn.close()
    
    print(f"Заявка {queue_id} добавлена в очередь для URL: {url}")
    return queue_id

if __name__ == "__main__":
    import sys
    
    if len(sys.argv) != 3:
        print("Использование: python add_to_queue.py <URL> <USER_ID>")
        sys.exit(1)
    
    url = sys.argv[1]
    user_id = sys.argv[2]
    
    add_to_queue(url, user_id)
