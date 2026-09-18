"""Bounded, read-only application readiness checks."""
from functools import lru_cache
import os
from pathlib import Path

import psycopg2
from alembic.config import Config
from alembic.script import ScriptDirectory


ROOT = Path(__file__).resolve().parents[2]
CONNECT_TIMEOUT_SECONDS = 2
STATEMENT_TIMEOUT_MILLISECONDS = 1500
LOCK_TIMEOUT_MILLISECONDS = 250
REQUIRED_COLUMNS = {
    "contentplans": {"id", "business_id", "scope_type", "plan_status", "created_at", "updated_at"},
    "contentplanitems": {"id", "plan_id", "business_id", "status", "seo_views", "metadata_json", "created_at", "updated_at"},
    "usernews": {"id", "user_id", "generated_text", "business_id", "updated_at", "original_generated_text", "edited_before_approve", "prompt_key", "prompt_version"},
    "ailearningevents": {"id", "capability", "event_type", "metadata_json", "created_at"},
}
REQUIRED_INDEXES = {
    "idx_ailearningevents_created_at",
    "idx_ailearningevents_capability_intent",
    "idx_ailearningevents_user_business",
}


@lru_cache(maxsize=1)
def expected_heads() -> frozenset[str]:
    configuration = Config(str(ROOT / "alembic.ini"))
    configuration.set_main_option("script_location", str(ROOT / "alembic_migrations"))
    return frozenset(ScriptDirectory.from_config(configuration).get_heads())


def compatible_revisions() -> set[str]:
    return {
        value.strip()
        for value in os.getenv("LOCALOS_COMPATIBLE_SCHEMA_REVISIONS", "").split(",")
        if value.strip()
    }


def _row_value(row, key: str, index: int):
    if hasattr(row, "get"):
        return row.get(key)
    if row:
        return row[index]
    return None


def revision_is_compatible(cursor, expected: frozenset[str] | None = None) -> bool:
    expected = expected_heads() if expected is None else expected
    cursor.execute("SELECT to_regclass('alembic_version')")
    if not _row_value(cursor.fetchone(), "to_regclass", 0):
        return False
    cursor.execute("SELECT version_num FROM alembic_version")
    actual = {_row_value(row, "version_num", 0) for row in cursor.fetchall()}
    actual.discard(None)
    compatible = compatible_revisions()
    return actual == set(expected) or bool(compatible) and len(actual) == 1 and actual.issubset(compatible)


def content_schema_missing(cursor, schema_name: str) -> tuple[dict[str, list[str]], list[str]]:
    cursor.execute(
        """SELECT table_name, column_name FROM information_schema.columns
            WHERE table_schema=%s AND table_name = ANY(%s)""",
        (schema_name, list(REQUIRED_COLUMNS)),
    )
    found: dict[str, set[str]] = {}
    for table_name, column_name in cursor.fetchall():
        found.setdefault(table_name, set()).add(column_name)
    missing = {
        table: sorted(required - found.get(table, set()))
        for table, required in REQUIRED_COLUMNS.items()
        if required - found.get(table, set())
    }
    cursor.execute(
        "SELECT indexname FROM pg_indexes WHERE schemaname=%s AND indexname = ANY(%s)",
        (schema_name, list(REQUIRED_INDEXES)),
    )
    indexes = {row[0] for row in cursor.fetchall()}
    return missing, sorted(REQUIRED_INDEXES - indexes)


def database_ready(connect=None) -> bool:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        return False
    connect = psycopg2.connect if connect is None else connect
    connection = None
    cursor = None
    is_ready = False
    try:
        connection = connect(database_url, connect_timeout=CONNECT_TIMEOUT_SECONDS)
        cursor = connection.cursor()
        cursor.execute("BEGIN READ ONLY")
        cursor.execute("SET LOCAL statement_timeout = %s", (f"{STATEMENT_TIMEOUT_MILLISECONDS}ms",))
        cursor.execute("SET LOCAL lock_timeout = %s", (f"{LOCK_TIMEOUT_MILLISECONDS}ms",))
        cursor.execute("SELECT 1")
        if _row_value(cursor.fetchone(), "?column?", 0) == 1 and revision_is_compatible(cursor):
            missing, missing_indexes = content_schema_missing(cursor, os.getenv("LOCALOS_SCHEMA_NAME", "public"))
            is_ready = not missing and not missing_indexes
    except Exception:
        is_ready = False
    finally:
        if cursor is not None:
            try:
                cursor.close()
            except Exception:
                is_ready = False
        if connection is not None:
            try:
                connection.close()
            except Exception:
                is_ready = False
    return is_ready
