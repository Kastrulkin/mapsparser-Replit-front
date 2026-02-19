#!/usr/bin/env python3
"""
Проверка полной схемы PostgreSQL (public).
Использует DATABASE_URL. Запуск: из корня проекта с установленным PYTHONPATH
или из контейнера: docker compose exec app python scripts/check_postgres_schema.py
"""
import sys
import os

# Корень проекта и src для импорта pg_db_utils
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SRC = os.path.join(ROOT, "src")
for p in (ROOT, SRC):
    if p not in sys.path:
        sys.path.insert(0, p)
os.chdir(ROOT)

def main():
    try:
        from pg_db_utils import get_db_connection
    except Exception as e:
        print("❌ Не удалось подключиться к Postgres (нужен DATABASE_URL):", e)
        return 1

    conn = get_db_connection()
    cur = conn.cursor()

    # Все таблицы в public
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public' AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    rows = cur.fetchall()
    tables = [r.get("table_name") if hasattr(r, "get") else r[0] for r in rows if r]

    print("=== Схема PostgreSQL (schema=public) ===\n")
    for table in tables:
        cur.execute("""
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            ORDER BY ordinal_position
        """, (table,))
        cols = cur.fetchall()
        print(f"📋 {table}")
        for row in cols:
            if hasattr(row, "get"):
                cname, dtype = row.get("column_name"), row.get("data_type")
                nullable, default = row.get("is_nullable"), row.get("column_default")
            else:
                cname, dtype, nullable, default = row[0], row[1], row[2], row[3]
            nn = "NOT NULL" if nullable == "NO" else "NULL"
            def_str = f" DEFAULT {default}" if default else ""
            print(f"   • {cname}: {dtype} {nn}{def_str}")
        print()

    cur.close()
    conn.close()
    print(f"Всего таблиц: {len(tables)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
