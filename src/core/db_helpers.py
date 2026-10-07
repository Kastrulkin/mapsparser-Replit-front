"""Small read-only schema guards shared by legacy database callers."""

from typing import Any, Iterable


def assert_schema_columns(cursor: Any, table_name: str, column_names: Iterable[str]) -> None:
    """Fail clearly when Alembic has not prepared a runtime table.

    Application connections intentionally use this check instead of creating or
    changing tables.  It keeps migration failures visible and allows the app and
    workers to run with DML-only database roles.
    """
    required_columns = tuple(column_names)
    cursor.execute(
        """
        SELECT COALESCE(array_agg(column_name::text), ARRAY[]::text[]) AS columns
        FROM information_schema.columns
        WHERE table_schema = current_schema()
          AND table_name = %s
          AND column_name = ANY(%s)
        """,
        (table_name, list(required_columns)),
    )
    row = cursor.fetchone()
    if isinstance(row, dict):
        found_value = row.get("columns")
    elif isinstance(row, (tuple, list)) and row:
        found_value = row[0]
    else:
        found_value = None
    if isinstance(found_value, str):
        found_value = found_value.strip("{}").split(",") if found_value else []
    found_columns = {str(column_name) for column_name in (found_value or [])}
    missing_columns = [column_name for column_name in required_columns if column_name not in found_columns]
    if missing_columns:
        missing = ", ".join(missing_columns)
        raise RuntimeError(
            f"Database schema is missing required columns on {table_name}: {missing}. "
            "Run the Alembic migrations before starting LocalOS."
        )


def ensure_user_examples_table(cursor: Any) -> None:
    """Check the Alembic-owned ``userexamples`` table before using it."""
    assert_schema_columns(
        cursor,
        "userexamples",
        ("id", "user_id", "example_type", "example_text", "created_at"),
    )
