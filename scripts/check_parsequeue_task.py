#!/usr/bin/env python3
"""
Проверить задачу в parsequeue по id (например e8ac5d69-e0f9-446f-83aa-3aa1b3e817f4).
Запуск: из корня проекта с настроенным DATABASE_URL или из контейнера app:
  python scripts/check_parsequeue_task.py [task_id]
  docker compose exec app python scripts/check_parsequeue_task.py e8ac5d69-e0f9-446f-83aa-3aa1b3e817f4
"""
import os
import sys

def main():
    task_id = (sys.argv[1] if len(sys.argv) > 1 else "").strip()
    if not task_id:
        print("Использование: python scripts/check_parsequeue_task.py <task_id>")
        sys.exit(1)

    # PostgreSQL
    try:
        from pg_db_utils import get_db_connection
    except ImportError:
        print("Ошибка: pg_db_utils не найден. Запускайте из контейнера app или с PYTHONPATH.")
        sys.exit(2)

    conn = get_db_connection()
    cur = conn.cursor()
    try:
        cur.execute("""
            SELECT id, business_id, task_type, source, status, user_id, url,
                   error_message, created_at, updated_at, account_id
            FROM parsequeue
            WHERE id = %s
        """, (task_id,))
        row = cur.fetchone()
        if not row:
            print(f"Задача {task_id} не найдена в parsequeue.")
            cur.execute("SELECT id, status, task_type, created_at FROM parsequeue ORDER BY created_at DESC LIMIT 5")
            rows = cur.fetchall()
            print("Последние 5 задач в очереди:")
            for r in rows:
                print(" ", dict(r))
            return
        d = dict(row)
        print("Задача найдена:")
        for k, v in d.items():
            print(f"  {k}: {v}")
        print()
        cur.execute("SELECT status, COUNT(*) AS cnt FROM parsequeue GROUP BY status")
        for r in cur.fetchall():
            print(f"  Всего в статусе {r['status']}: {r['cnt']}")
        # Кто впереди в очереди (pending по created_at)
        cur.execute("""
            SELECT id, business_id, task_type, status, created_at
            FROM parsequeue WHERE status = 'pending' ORDER BY created_at ASC LIMIT 10
        """)
        pending = cur.fetchall()
        print("\n  Ожидающие (pending), первые 10 по очереди:")
        for r in pending:
            mark = " <-- эта" if r["id"] == task_id else ""
            print(f"    {r['id']} {r['task_type']} {r['created_at']}{mark}")
    finally:
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
