#!/usr/bin/env python3
"""Read-only schema gate for the first runtime-DDL retirement slice."""
import os
import sys

import psycopg2


REQUIRED_COLUMNS = {
    "contentplans": {"id", "business_id", "scope_type", "plan_status", "created_at", "updated_at"},
    "contentplanitems": {"id", "plan_id", "business_id", "status", "seo_views", "metadata_json", "created_at", "updated_at"},
    "usernews": {"id", "user_id", "generated_text", "business_id", "updated_at", "original_generated_text", "edited_before_approve", "prompt_key", "prompt_version"},
    "ailearningevents": {"id", "capability", "event_type", "metadata_json", "created_at"},
}
REQUIRED_INDEXES = {"idx_ailearningevents_created_at", "idx_ailearningevents_capability_intent", "idx_ailearningevents_user_business"}


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
            cursor.execute("""SELECT table_name, column_name FROM information_schema.columns
                WHERE table_schema=%s AND table_name = ANY(%s)""", (schema_name, list(REQUIRED_COLUMNS)))
            found = {}
            for table_name, column_name in cursor.fetchall():
                found.setdefault(table_name, set()).add(column_name)
            missing = {table: sorted(required - found.get(table, set())) for table, required in REQUIRED_COLUMNS.items() if required - found.get(table, set())}
            cursor.execute("SELECT indexname FROM pg_indexes WHERE schemaname=%s AND indexname = ANY(%s)", (schema_name, list(REQUIRED_INDEXES)))
            indexes = {row[0] for row in cursor.fetchall()}
        finally:
            cursor.close()
        missing_indexes = sorted(REQUIRED_INDEXES - indexes)
        if missing or missing_indexes:
            print({"missing_columns": missing, "missing_indexes": missing_indexes}, file=sys.stderr)
            return 1
        print("content_learning_schema=ok")
        return 0
    finally:
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
