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
import time
from pathlib import Path

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
    cur.execute("SELECT version_num FROM alembic_version LIMIT 1")
    row = cur.fetchone()
    current_db_revision = row[0] if row else None

    versions_dir = Path("/app/alembic_migrations/versions")
    available_migration_files = sorted(path.name for path in versions_dir.glob("*.py"))
    print(f"DB revision before upgrade: {current_db_revision or 'none'}")
    print(f"Available migration files: {len(available_migration_files)}")

    attempts = 3
    for attempt in range(1, attempts + 1):
        print(f"Running flask db upgrade (attempt {attempt}/{attempts})...")
        result = subprocess.run(
            ["flask", "db", "upgrade"],
            capture_output=True,
            text=True,
            check=False,
        )

        if result.stdout:
            print(result.stdout, end="")
        if result.stderr:
            print(result.stderr, end="")

        if result.returncode == 0:
            break

        revision_missing = "Can't locate revision identified by" in (result.stderr or "")
        if revision_missing and attempt < attempts:
            print("Migration revision lookup failed early. Sleeping before retry...")
            time.sleep(3)
            continue

        raise subprocess.CalledProcessError(
            result.returncode,
            result.args,
            output=result.stdout,
            stderr=result.stderr,
        )
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
