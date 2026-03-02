#!/bin/sh
# Ждём готовности Postgres, применяем миграции, затем запускаем переданную команду.
set -e

POSTGRES_USER="${POSTGRES_USER:-local}"
POSTGRES_DB="${POSTGRES_DB:-local}"

echo "Waiting for Postgres at postgres:5432..."
until pg_isready -h postgres -p 5432 -U "$POSTGRES_USER" -d "$POSTGRES_DB"; do
  sleep 2
done
echo "Postgres is ready."

echo "Running migrations..."
python3 - <<'PY'
import os
import subprocess

import psycopg2


dsn = os.getenv("DATABASE_URL")
if not dsn:
    user = os.getenv("POSTGRES_USER", "local")
    password = os.getenv("POSTGRES_PASSWORD", "local")
    db = os.getenv("POSTGRES_DB", "local")
    dsn = f"postgresql://{user}:{password}@postgres:5432/{db}"

lock_id = 883741
conn = psycopg2.connect(dsn)
conn.autocommit = True
cur = conn.cursor()

try:
    print(f"Acquiring migration advisory lock {lock_id}...")
    cur.execute("SELECT pg_advisory_lock(%s)", (lock_id,))
    print("Migration lock acquired.")
    subprocess.check_call(["flask", "db", "upgrade"])
finally:
    try:
        cur.execute("SELECT pg_advisory_unlock(%s)", (lock_id,))
        print("Migration lock released.")
    except Exception as unlock_error:
        print(f"Warning: failed to release migration lock cleanly: {unlock_error}")
    try:
        cur.close()
    except Exception:
        pass
    try:
        conn.close()
    except Exception:
        pass
PY
echo "Migrations done."

exec "$@"
