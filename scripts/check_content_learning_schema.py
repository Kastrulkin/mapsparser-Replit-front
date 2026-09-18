#!/usr/bin/env python3
"""Read-only schema gate for the first runtime-DDL retirement slice."""
import os
import sys
from pathlib import Path

import psycopg2


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from core.readiness import content_schema_missing


def main():
    dsn = os.environ.get("DATABASE_URL")
    conn = psycopg2.connect(dsn) if dsn else psycopg2.connect(
        host=os.getenv("POSTGRES_HOST", "postgres"), port=os.getenv("POSTGRES_PORT", "5432"),
        user=os.getenv("POSTGRES_USER", "local"), password=os.getenv("POSTGRES_PASSWORD", "local"),
        dbname=os.getenv("POSTGRES_DB", "local"))
    schema_name = os.environ.get("LOCALOS_SCHEMA_NAME", "public")
    try:
        cursor = conn.cursor()
        try:
            missing, missing_indexes = content_schema_missing(cursor, schema_name)
        finally:
            cursor.close()
        if missing or missing_indexes:
            print({"missing_columns": missing, "missing_indexes": missing_indexes}, file=sys.stderr)
            return 1
        print("content_learning_schema=ok")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
