from __future__ import annotations

from typing import Any


def _table_available(cursor: Any, table_name: str) -> bool:
    cursor.execute("SELECT to_regclass(%s) AS table_name", (table_name,))
    row = cursor.fetchone() or {}
    value = row.get("table_name") if hasattr(row, "get") else row[0]
    return bool(value)


def load_public_offer_row(cursor: Any, slug: str) -> Any:
    sources = (
        (
            "partnershippublicoffers",
            """
            SELECT slug, page_json, updated_at
            FROM partnershippublicoffers
            WHERE slug = %s AND is_active = TRUE
            LIMIT 1
            """,
        ),
        (
            "adminprospectingleadpublicoffers",
            """
            SELECT slug, page_json, generated_json, published_json, updated_at
            FROM adminprospectingleadpublicoffers
            WHERE slug = %s AND is_active = TRUE
            LIMIT 1
            """,
        ),
        (
            "publicreportrequests",
            """
            SELECT slug, page_json, updated_at
            FROM publicreportrequests
            WHERE slug = %s AND status = 'completed'
            LIMIT 1
            """,
        ),
    )
    for table_name, query in sources:
        if not _table_available(cursor, table_name):
            continue
        cursor.execute(query, (slug,))
        row = cursor.fetchone()
        if row:
            return row
    return None
